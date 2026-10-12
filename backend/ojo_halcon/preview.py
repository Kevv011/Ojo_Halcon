from __future__ import annotations

import argparse
import time
from enum import Enum, auto
from pathlib import Path

import cv2
import numpy as np

from .camera import open_camera
from .config import AppConfig, ConfigError
from .detector import BallDetection
from .game import GameSnapshot, GameState
from .geometry import BallRelation, GeometryResult
from .pipeline import VisionPipeline
from .tracking import TrackSnapshot


WINDOW = "Ojo de Halcon - calibracion"
MENU_MESSAGE = (
    "B balon | L linea | G interior | P zona | S guardar | "
    "N reiniciar | R/X borrar | M mascara | Q salir"
)
MESSAGE_DURATION_SECONDS = 4.0
BACKEND_DIR = Path(__file__).resolve().parent.parent


class ClickMode(Enum):
    NONE = auto()
    BALL = auto()
    LINE = auto()
    GOAL_SIDE = auto()
    ROI = auto()


class CalibrationUI:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.mode = ClickMode.NONE
        self.latest_frame: np.ndarray | None = None
        self.line_points: list[list[int]] = list(config.goal_line or [])
        self.roi_points: list[list[int]] = list(config.roi or [])
        self.show_mask = True
        self.message = MENU_MESSAGE
        self.message_expires_at = 0.0

    def set_message(
        self,
        message: str,
        now: float | None = None,
        duration: float = MESSAGE_DURATION_SECONDS,
    ) -> None:
        """Muestra un aviso temporal antes de regresar al menú de teclas."""
        current_time = time.perf_counter() if now is None else now
        self.message = message
        self.message_expires_at = current_time + duration

    def visible_message(self, now: float | None = None) -> str:
        current_time = time.perf_counter() if now is None else now
        if current_time >= self.message_expires_at:
            return MENU_MESSAGE
        return self.message

    def mouse(self, event: int, x: int, y: int, _flags: int, _data: object) -> None:
        if event != cv2.EVENT_LBUTTONDOWN or self.latest_frame is None:
            return
        if self.mode is ClickMode.BALL:
            hsv = cv2.cvtColor(self.latest_frame, cv2.COLOR_BGR2HSV)
            hue, saturation, value = (int(v) for v in hsv[y, x])
            self.config.ball.hsv_lower = [
                (hue - 12) % 180,
                max(40, saturation - 80),
                max(40, value - 80),
            ]
            self.config.ball.hsv_upper = [
                (hue + 12) % 180,
                255,
                255,
            ]
            self.set_message(f"Color HSV seleccionado: {hue}, {saturation}, {value}")
            self.mode = ClickMode.NONE
        elif self.mode is ClickMode.LINE:
            self.line_points.append([x, y])
            if len(self.line_points) == 2:
                self.config.goal_line = self.line_points.copy()
                self.mode = ClickMode.NONE
                self.set_message("Linea definida. Presiona S para guardarla.")
        elif self.mode is ClickMode.GOAL_SIDE:
            self.config.goal_side_point = [x, y]
            self.mode = ClickMode.NONE
            self.set_message("Interior definido. Presiona S para guardarlo.")
        elif self.mode is ClickMode.ROI:
            self.roi_points.append([x, y])
            remaining = 4 - len(self.roi_points)
            if remaining == 0:
                self.config.roi = self.roi_points.copy()
                self.mode = ClickMode.NONE
                self.set_message("Zona definida. Presiona S para guardarla.")
            else:
                self.set_message(
                    f"Zona: faltan {remaining} puntos en orden alrededor del area"
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vista previa y calibracion visual")
    parser.add_argument("--camera", type=int, default=0, help="Indice de la webcam")
    parser.add_argument(
        "--config",
        type=Path,
        default=BACKEND_DIR / "config" / "default.json",
        help="Archivo JSON de calibracion",
    )
    return parser.parse_args()


def draw_overlay(
    frame: np.ndarray,
    ui: CalibrationUI,
    detection: BallDetection | None,
    track: TrackSnapshot,
    geometry: GeometryResult | None,
    game: GameSnapshot,
    fps: float,
) -> None:
    roi_points = ui.config.roi or ui.roi_points
    if roi_points:
        points = np.array(roi_points, dtype=np.int32)
        closed = len(roi_points) >= 3 and ui.config.roi is not None
        cv2.polylines(frame, [points], closed, (255, 255, 0), 2)
        for point in roi_points:
            cv2.circle(frame, tuple(point), 5, (255, 255, 0), -1)

    if ui.config.goal_line:
        p1, p2 = (tuple(point) for point in ui.config.goal_line)
        cv2.line(frame, p1, p2, (0, 255, 255), 3)
    elif ui.line_points:
        cv2.circle(frame, tuple(ui.line_points[0]), 6, (0, 255, 255), -1)

    if ui.config.goal_side_point:
        goal_point = tuple(ui.config.goal_side_point)
        cv2.circle(frame, goal_point, 7, (255, 0, 255), -1)
        cv2.putText(
            frame,
            "INTERIOR",
            (goal_point[0] + 10, goal_point[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 0, 255),
            2,
        )
        if ui.config.goal_line:
            p1, p2 = ui.config.goal_line
            midpoint = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            vector = (goal_point[0] - midpoint[0], goal_point[1] - midpoint[1])
            length = max(float(np.hypot(*vector)), 1.0)
            arrow_end = (
                round(midpoint[0] + 55 * vector[0] / length),
                round(midpoint[1] + 55 * vector[1] / length),
            )
            cv2.arrowedLine(frame, midpoint, arrow_end, (255, 0, 255), 3, tipLength=0.3)

    if len(track.history) >= 2:
        trail = np.array(track.history, dtype=np.int32)
        cv2.polylines(frame, [trail], False, (255, 180, 0), 2)

    if track.center is not None and track.radius is not None:
        center = (round(track.center[0]), round(track.center[1]))
        color = _relation_color(geometry)
        if not track.detected:
            color = (0, 215, 255)
        cv2.circle(frame, center, round(track.radius), color, 3)
        cv2.circle(frame, center, 4, (255, 255, 255), -1)
        cv2.putText(
            frame,
            (
                geometry.relation.value
                if track.detected and geometry is not None
                else f"BALON? perdida {track.lost_frames}"
            ),
            (center[0] + 12, max(25, center[1] - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
        )

    cv2.rectangle(frame, (0, 0), (frame.shape[1], 88), (20, 20, 20), -1)
    cv2.putText(
        frame,
        ui.visible_message(),
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (255, 255, 255),
        1,
    )
    if track.detected:
        status = "DETECTADO"
    elif track.held:
        status = f"RECUPERANDO {track.lost_frames}"
    else:
        status = "SIN BALON"
    details = f"FPS {fps:4.1f} | {status}"
    if track.center is not None and track.radius is not None:
        details += (
            f" | centro=({track.center[0]:.0f},{track.center[1]:.0f})"
            f" radio={track.radius:.1f} velocidad={track.speed:.0f}px/s"
        )
    if detection is not None:
        details += f" area={detection.area:.0f} circ={detection.circularity:.2f}"
    cv2.putText(
        frame,
        details,
        (10, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.54,
        (180, 255, 180),
        1,
    )
    if geometry is None:
        geometry_details = "GEOMETRIA: sin balon"
    elif geometry.relation is BallRelation.UNCALIBRATED:
        geometry_details = "GEOMETRIA: presiona G y haz clic dentro de la zona verde"
    else:
        mouth = "SI" if geometry.inside_mouth else "NO"
        geometry_details = (
            f"POSICION {geometry.relation.value} | distancia={geometry.signed_distance:.1f}px"
            f" | borde posterior={geometry.trailing_edge:.1f}px | entre postes={mouth}"
        )
    cv2.putText(
        frame,
        geometry_details,
        (10, 78),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.54,
        (255, 220, 150),
        1,
    )
    draw_game_panel(frame, game)


def _relation_color(geometry: GeometryResult | None) -> tuple[int, int, int]:
    if geometry is None or geometry.relation is BallRelation.UNCALIBRATED:
        return (0, 255, 0)
    colors = {
        BallRelation.BEFORE: (255, 160, 0),
        BallRelation.TOUCHING: (0, 255, 255),
        BallRelation.PARTIAL: (0, 165, 255),
        BallRelation.CROSSED: (0, 255, 0),
        BallRelation.OUTSIDE_MOUTH: (0, 0, 255),
    }
    return colors.get(geometry.relation, (0, 255, 0))


def draw_game_panel(frame: np.ndarray, game: GameSnapshot) -> None:
    colors = {
        GameState.WAITING: (110, 110, 110),
        GameState.ANALYZING: (0, 185, 255),
        GameState.GOAL: (0, 180, 0),
        GameState.NO_GOAL: (0, 0, 210),
    }
    color = colors[game.state]
    height, width = frame.shape[:2]
    panel_width = min(520, width - 20)
    text_width = panel_width - 36
    reason = (
        "Retira el balon para continuar"
        if game.waiting_for_removal
        else game.reason
    )
    reason_lines = _wrap_text_lines(
        reason,
        text_width,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        1,
    )
    diagnostic_height = 24 if game.state is GameState.ANALYZING else 0
    panel_height = 96 + 20 * len(reason_lines) + diagnostic_height
    top = max(95, height - panel_height - 10)
    cv2.rectangle(frame, (10, top), (10 + panel_width, height - 10), (20, 20, 20), -1)
    cv2.rectangle(frame, (10, top), (10 + panel_width, height - 10), color, 3)
    cv2.putText(
        frame,
        game.state.value,
        (28, top + 42),
        cv2.FONT_HERSHEY_DUPLEX,
        1.05,
        color,
        2,
    )
    play = f"Jugada {game.play_id}" if game.play_id else "Sistema listo"
    cv2.putText(
        frame,
        play,
        (28, top + 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (235, 235, 235),
        1,
    )
    y = top + 94
    for line in reason_lines:
        cv2.putText(
            frame,
            line,
            (28, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (235, 235, 235),
            1,
        )
        y += 20
    if game.state is GameState.ANALYZING:
        cv2.putText(
            frame,
            f"hacia gol={game.approach_speed:.0f}px/s | cruces={game.crossed_observations}",
            (28, y + 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (235, 235, 235),
            1,
        )


def _wrap_text_lines(
    text: str,
    max_width: int,
    font: int,
    scale: float,
    thickness: int,
) -> list[str]:
    """Divide texto para que cada línea quepa dentro del panel de OpenCV."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        width = cv2.getTextSize(candidate, font, scale, thickness)[0][0]
        if width <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def add_mask_preview(frame: np.ndarray, mask: np.ndarray) -> None:
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    mask_bgr = cv2.resize(mask_bgr, (frame.shape[1] // 4, frame.shape[0] // 4))
    cv2.putText(
        mask_bgr,
        "MASCARA",
        (8, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        1,
    )
    h, w = mask_bgr.shape[:2]
    frame[-h:, -w:] = mask_bgr
    cv2.rectangle(
        frame,
        (frame.shape[1] - w, frame.shape[0] - h),
        (frame.shape[1] - 1, frame.shape[0] - 1),
        (255, 255, 255),
        1,
    )


def main() -> None:
    args = parse_args()
    config = AppConfig.load(args.config)
    ui = CalibrationUI(config)
    pipeline = VisionPipeline(config)
    camera = open_camera(args.camera, config)
    previous_frame_time = time.perf_counter()
    smoothed_fps = 0.0

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW, ui.mouse)

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("La webcam dejo de entregar imagenes.")
            ui.latest_frame = frame.copy()

            now = time.perf_counter()
            elapsed = max(now - previous_frame_time, 1e-6)
            instant_fps = 1.0 / elapsed
            smoothed_fps = (
                instant_fps
                if smoothed_fps == 0
                else 0.1 * instant_fps + 0.9 * smoothed_fps
            )
            previous_frame_time = now

            analysis = pipeline.process(frame, now)
            draw_overlay(
                frame,
                ui,
                analysis.detection,
                analysis.track,
                analysis.geometry,
                analysis.game,
                smoothed_fps,
            )

            if ui.show_mask:
                add_mask_preview(frame, analysis.mask)

            cv2.imshow(WINDOW, frame)
            key_code = cv2.waitKey(1) & 0xFF
            if key_code == 27:
                break
            key = chr(key_code).lower() if key_code < 128 else ""
            if key == "q":
                break
            if key == "b":
                pipeline.reset(now)
                ui.mode = ClickMode.BALL
                ui.set_message("Haz clic en el centro del balon")
            elif key == "l":
                pipeline.reset(now)
                ui.mode = ClickMode.LINE
                ui.line_points.clear()
                ui.config.goal_line = None
                ui.set_message("Haz clic en los dos extremos de la linea")
            elif key == "g":
                pipeline.reset(now)
                ui.mode = ClickMode.GOAL_SIDE
                ui.set_message("Haz clic dentro de la zona verde, lejos de la linea")
            elif key == "p":
                pipeline.reset(now)
                ui.mode = ClickMode.ROI
                ui.roi_points.clear()
                ui.config.roi = None
                ui.set_message("Zona: haz 4 clics alrededor del area, en orden")
            elif key == "r":
                pipeline.reset(now)
                ui.line_points.clear()
                ui.config.goal_line = None
                ui.set_message("Linea borrada")
            elif key == "x":
                pipeline.reset(now)
                ui.roi_points.clear()
                ui.config.roi = None
                ui.set_message("Zona de analisis borrada")
            elif key == "m":
                ui.show_mask = not ui.show_mask
                ui.set_message(
                    "Vista de mascara activada"
                    if ui.show_mask
                    else "Vista de mascara oculta"
                )
            elif key == "n":
                pipeline.reset(now)
                ui.set_message("Sistema reiniciado; listo para una nueva jugada")
            elif key == "s":
                if len(ui.line_points) == 2:
                    ui.config.goal_line = ui.line_points
                if len(ui.roi_points) >= 3:
                    ui.config.roi = ui.roi_points
                try:
                    ui.config.save(args.config)
                except ConfigError as error:
                    ui.set_message(f"No se pudo guardar: {error}")
                else:
                    ui.set_message(f"Calibracion guardada en {args.config}")
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
