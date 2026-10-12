from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from .camera import CameraError, CameraReadError, open_camera
from .config import AppConfig
from .game import GameSnapshot, GameState
from .history import PlayHistory
from .pipeline import FrameAnalysis, VisionPipeline
from .preview import CalibrationUI, draw_overlay
from .schemas import (
    CalibrationStatus,
    CameraStatus,
    DetectionStatus,
    GameStatus,
    GeometryStatus,
    HealthResponse,
    PlayRecord,
    PointData,
    SystemState,
)


LOGGER = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY_PATH = BACKEND_DIR / "data" / "plays.jsonl"
JPEG_INTERVAL_SECONDS = 0.25
HEALTH_FRAME_TIMEOUT_SECONDS = 2.0
HISTORY_RETRY_SECONDS = 2.0
RESULT_SNAPSHOT_LIMIT = 20


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateBroadcaster:
    """Entrega el estado más reciente a cada WebSocket sin bloquear la cámara."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, state: SystemState) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        payload = state.model_dump(mode="json")
        loop.call_soon_threadsafe(self._deliver, payload)

    def _deliver(self, payload: dict[str, Any]) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(payload)


class VisionRuntime:
    """Ejecuta OpenCV en segundo plano y conserva el estado consumido por la API."""

    def __init__(
        self,
        config: AppConfig,
        camera_index: int = 0,
        history_path: Path = DEFAULT_HISTORY_PATH,
        config_path: Path | None = None,
        reconnect_seconds: float = 2.0,
    ) -> None:
        config.validate()
        self.config = config
        self.camera_index = camera_index
        self.config_path = (
            config_path or BACKEND_DIR / "config" / "default.json"
        ).resolve()
        self.reconnect_seconds = max(0.1, reconnect_seconds)
        self.history = PlayHistory(history_path)
        self.broadcaster = StateBroadcaster()
        now = time.perf_counter()
        self._pipeline = VisionPipeline(
            config,
            initial_play_id=self.history.last_play_id,
            initial_timestamp=now,
        )
        initial_game = self._pipeline.reset(now)
        self._ui = CalibrationUI(config)
        self._ui.show_mask = False
        self._ui.message = "Backend API activo | Estado por WebSocket /ws"
        self._ui.message_expires_at = float("inf")
        self._lock = threading.RLock()
        self._stop_requested = threading.Event()
        self._reset_requested = threading.Event()
        self._thread: threading.Thread | None = None
        self._service_mode = "detecting"
        self._latest_jpeg: bytes | None = None
        self._result_jpegs: dict[int, bytes] = {}
        self._last_jpeg_at = 0.0
        self._last_frame_at: float | None = None
        self._processing_error: str | None = None
        self._history_error: str | None = None
        self._history_retry_at: dict[tuple[int, str], float] = {}
        self._recorded_results = {
            (record.play_id, record.result)
            for record in self.history.recent(self.history.max_records)
        }
        self._state = SystemState(
            timestamp=utc_now(),
            service_mode=self._service_mode,
            camera=CameraStatus(index=camera_index),
            detection=DetectionStatus(),
            game=self._game_status(initial_game),
            calibration=self._calibration_status(),
        )

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_requested.clear()
        with self._lock:
            self._service_mode = "detecting"
            self._state = self._state.model_copy(
                update={"service_mode": self._service_mode},
                deep=True,
            )
        self._thread = threading.Thread(
            target=self._run,
            name="ojo-halcon-camera",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> bool:
        self._stop_requested.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
        return thread is None or not thread.is_alive()

    def request_reset(self) -> None:
        self._reset_requested.set()

    @property
    def reset_pending(self) -> bool:
        return self._reset_requested.is_set()

    def get_state(self) -> SystemState:
        with self._lock:
            return self._state.model_copy(deep=True)

    def get_latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    def get_result_jpeg(self, play_id: int) -> bytes | None:
        with self._lock:
            return self._result_jpegs.get(play_id)

    def get_configuration(self) -> dict[str, Any]:
        return asdict(self.config)

    def enter_calibration_mode(self) -> None:
        """Publica un estado limpio mientras OpenCV usa la webcam."""
        now = time.perf_counter()
        game = self._pipeline.reset(now)
        with self._lock:
            self._service_mode = "calibrating"
            self._last_frame_at = None
            self._latest_jpeg = None
            self._state = SystemState(
                timestamp=utc_now(),
                service_mode=self._service_mode,
                camera=CameraStatus(index=self.camera_index),
                detection=DetectionStatus(),
                game=self._game_status(game).model_copy(
                    update={"reason": "Calibración de cámara en curso"}
                ),
                calibration=self._calibration_status(),
            )
            state = self._state.model_copy(deep=True)
        self.broadcaster.publish(state)

    def replace_config(self, config: AppConfig) -> None:
        """Instala una calibración nueva cuando el hilo de cámara está detenido."""
        config.validate()
        thread = self._thread
        if thread is not None and thread.is_alive():
            raise RuntimeError("No se puede recargar la calibración con la cámara activa")
        now = time.perf_counter()
        with self._lock:
            play_id = max(self.history.last_play_id, self._state.game.play_id)
            self.config = config
            self._pipeline = VisionPipeline(
                config,
                initial_play_id=play_id,
                initial_timestamp=now,
            )
            game = self._pipeline.reset(now)
            self._ui = CalibrationUI(config)
            self._ui.show_mask = False
            self._ui.message = "Backend API activo | Estado por WebSocket /ws"
            self._ui.message_expires_at = float("inf")
            self._service_mode = "detecting"
            self._processing_error = None
            self._state = SystemState(
                timestamp=utc_now(),
                service_mode=self._service_mode,
                camera=CameraStatus(index=self.camera_index),
                detection=DetectionStatus(),
                game=self._game_status(game),
                calibration=self._calibration_status(),
            )
            state = self._state.model_copy(deep=True)
        self.broadcaster.publish(state)

    def get_health(self) -> HealthResponse:
        now = time.perf_counter()
        with self._lock:
            camera = self._state.camera.model_copy(deep=True)
            last_frame_at = self._last_frame_at
            processing_error = self._processing_error
            history_error = self._history_error
            service_mode = self._service_mode
        frame_age = None if last_frame_at is None else max(0.0, now - last_frame_at)
        thread_alive = self._thread is not None and self._thread.is_alive()
        processing_alive = (
            thread_alive
            and frame_age is not None
            and frame_age <= HEALTH_FRAME_TIMEOUT_SECONDS
        )
        calibration_ready = self.config.calibration_ready
        healthy = (
            camera.connected
            and calibration_ready
            and processing_alive
            and camera.resolution_matches is not False
            and processing_error is None
            and history_error is None
        )
        return HealthResponse(
            status="ok" if healthy else "degraded",
            service_mode=service_mode,
            camera_connected=camera.connected,
            calibration_ready=calibration_ready,
            processing_alive=processing_alive,
            last_frame_age_seconds=(round(frame_age, 3) if frame_age is not None else None),
            camera_error=camera.error,
            processing_error=processing_error,
            history_error=history_error,
            resolution_matches=camera.resolution_matches,
        )

    def _run(self) -> None:
        while not self._stop_requested.is_set():
            camera: cv2.VideoCapture | None = None
            try:
                camera = open_camera(self.camera_index, self.config)
                self._pipeline.reset(time.perf_counter())
                self._capture(camera)
            except CameraError as error:
                LOGGER.warning(
                    "Cámara no disponible: %s; nuevo intento en %.1f s",
                    error,
                    self.reconnect_seconds,
                )
                self._set_runtime_error(str(error), camera_failure=True)
                self._stop_requested.wait(self.reconnect_seconds)
            except Exception as error:
                LOGGER.exception(
                    "Falló el procesamiento; nuevo intento en %.1f s",
                    self.reconnect_seconds,
                )
                self._set_runtime_error(str(error), camera_failure=False)
                self._stop_requested.wait(self.reconnect_seconds)
            finally:
                if camera is not None:
                    camera.release()

    def _capture(self, camera: cv2.VideoCapture) -> None:
        previous_frame_time = time.perf_counter()
        smoothed_fps = 0.0
        while not self._stop_requested.is_set():
            ok, frame = camera.read()
            if not ok:
                raise CameraReadError("La webcam dejó de entregar imágenes")

            now = time.perf_counter()
            if self._reset_requested.is_set():
                self._pipeline.reset(now)
                self._reset_requested.clear()

            elapsed = max(now - previous_frame_time, 1e-6)
            instant_fps = 1.0 / elapsed
            smoothed_fps = (
                instant_fps
                if smoothed_fps == 0
                else 0.1 * instant_fps + 0.9 * smoothed_fps
            )
            previous_frame_time = now

            analysis = self._pipeline.process(frame, now)
            annotated = frame.copy()
            draw_overlay(
                annotated,
                self._ui,
                analysis.detection,
                analysis.track,
                analysis.geometry,
                analysis.game,
                smoothed_fps,
            )
            self._capture_result_snapshot(analysis.game, annotated)
            jpeg = self._encode_snapshot(annotated, now)
            height, width = frame.shape[:2]
            state = self._build_state(analysis, smoothed_fps, width, height)
            with self._lock:
                self._last_frame_at = now
                self._processing_error = None
            # El resultado visible nunca depende de que el disco acepte el historial.
            self._commit(state, jpeg)
            self._record_result(analysis.game, state.timestamp, now)

    def _encode_snapshot(self, frame: Any, timestamp: float) -> bytes | None:
        if timestamp - self._last_jpeg_at < JPEG_INTERVAL_SECONDS:
            return None
        encoded, jpeg = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, 82],
        )
        if not encoded:
            return None
        self._last_jpeg_at = timestamp
        return jpeg.tobytes()

    def _capture_result_snapshot(self, game: GameSnapshot, frame: Any) -> None:
        if game.state not in (GameState.GOAL, GameState.NO_GOAL):
            return
        with self._lock:
            if game.play_id in self._result_jpegs:
                return
        encoded, jpeg = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, 90],
        )
        if not encoded:
            return
        with self._lock:
            self._result_jpegs[game.play_id] = jpeg.tobytes()
            while len(self._result_jpegs) > RESULT_SNAPSHOT_LIMIT:
                oldest_play_id = next(iter(self._result_jpegs))
                self._result_jpegs.pop(oldest_play_id)

    def _build_state(
        self,
        analysis: FrameAnalysis,
        fps: float,
        width: int,
        height: int,
    ) -> SystemState:
        track = analysis.track
        detection = analysis.detection
        geometry = analysis.geometry
        if track.detected:
            detection_label = "DETECTADO"
        elif track.held:
            detection_label = "RECUPERANDO"
        else:
            detection_label = "SIN BALON"

        center = (
            PointData(x=track.center[0], y=track.center[1])
            if track.center is not None
            else None
        )
        geometry_status = (
            GeometryStatus(
                relation=geometry.relation.value,
                signed_distance_px=round(geometry.signed_distance, 2),
                trailing_edge_px=round(geometry.trailing_edge, 2),
                inside_posts=geometry.inside_mouth,
            )
            if geometry is not None
            else None
        )
        resolution_matches = (
            width == self.config.camera.width and height == self.config.camera.height
        )
        return SystemState(
            timestamp=utc_now(),
            service_mode=self._service_mode,
            camera=CameraStatus(
                connected=True,
                fps=round(fps, 2),
                index=self.camera_index,
                width=width,
                height=height,
                resolution_matches=resolution_matches,
            ),
            detection=DetectionStatus(
                status=detection_label,
                center=center,
                radius_px=round(track.radius, 2) if track.radius is not None else None,
                speed_px_s=round(track.speed, 2),
                area_px=round(detection.area, 2) if detection is not None else None,
                circularity=(
                    round(detection.circularity, 3)
                    if detection is not None
                    else None
                ),
            ),
            geometry=geometry_status,
            game=self._game_status(analysis.game),
            calibration=self._calibration_status(),
        )

    def _record_result(
        self,
        game: GameSnapshot,
        decided_at: str,
        now: float | None = None,
    ) -> None:
        if game.state not in (GameState.GOAL, GameState.NO_GOAL):
            return
        key = (game.play_id, game.state.value)
        if key in self._recorded_results:
            return
        current_time = time.perf_counter() if now is None else now
        if current_time < self._history_retry_at.get(key, 0.0):
            return
        try:
            self.history.append(
                PlayRecord(
                    play_id=game.play_id,
                    result=game.state.value,
                    reason=game.reason,
                    decided_at=decided_at,
                    approach_speed_px_s=round(game.approach_speed, 2),
                    crossed_observations=game.crossed_observations,
                )
            )
        except Exception as error:
            LOGGER.exception("No se pudo guardar la jugada %s", game.play_id)
            with self._lock:
                self._history_error = str(error)
            self._history_retry_at[key] = current_time + HISTORY_RETRY_SECONDS
            return
        self._recorded_results.add(key)
        self._history_retry_at.pop(key, None)
        with self._lock:
            self._history_error = None

    def _commit(self, state: SystemState, jpeg: bytes | None) -> None:
        with self._lock:
            self._state = state
            if jpeg is not None:
                self._latest_jpeg = jpeg
        self.broadcaster.publish(state)

    def _set_runtime_error(self, message: str, camera_failure: bool) -> None:
        now = time.perf_counter()
        game = self._pipeline.reset(now)
        reason = (
            "Cámara desconectada; intentando reconectar"
            if camera_failure
            else "Procesamiento detenido; intentando recuperar"
        )
        game_status = self._game_status(game).model_copy(update={"reason": reason})
        with self._lock:
            self._last_frame_at = None
            self._latest_jpeg = None
            if camera_failure:
                self._processing_error = None
            else:
                self._processing_error = message
            self._state = SystemState(
                timestamp=utc_now(),
                service_mode=self._service_mode,
                camera=CameraStatus(
                    connected=False,
                    fps=0.0,
                    index=self.camera_index,
                    error=message if camera_failure else None,
                ),
                detection=DetectionStatus(),
                game=game_status,
                calibration=self._calibration_status(),
            )
            state = self._state.model_copy(deep=True)
        self.broadcaster.publish(state)

    def _calibration_status(self) -> CalibrationStatus:
        errors = self.config.calibration_errors()
        return CalibrationStatus(ready=not errors, errors=errors)

    @staticmethod
    def _game_status(game: GameSnapshot) -> GameStatus:
        return GameStatus(
            state=game.state.value,
            play_id=game.play_id,
            reason=game.reason,
            state_elapsed_seconds=round(game.state_elapsed, 2),
            approach_speed_px_s=round(game.approach_speed, 2),
            crossed_observations=game.crossed_observations,
            waiting_for_removal=game.waiting_for_removal,
        )
