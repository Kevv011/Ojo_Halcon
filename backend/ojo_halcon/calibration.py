from __future__ import annotations

import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import AppConfig
from .schemas import CalibrationProcessStatus
from .service import BACKEND_DIR, VisionRuntime


class CalibrationBusyError(RuntimeError):
    """Ya existe una ventana de calibración activa."""


class CalibrationManager:
    """Cede la webcam al calibrador y reactiva la detección al cerrarlo."""

    def __init__(
        self,
        runtime: VisionRuntime,
        config_path: Path,
        process_factory: Callable[..., Any] = subprocess.Popen,
    ) -> None:
        self.runtime = runtime
        self.config_path = config_path.resolve()
        self._process_factory = process_factory
        self._lock = threading.RLock()
        self._process: Any | None = None
        self._worker: threading.Thread | None = None
        self._shutdown_requested = False
        self._status = CalibrationProcessStatus(
            status="idle",
            active=False,
            message="Calibrador cerrado; detección disponible",
        )

    def get_status(self) -> CalibrationProcessStatus:
        with self._lock:
            return self._status.model_copy(deep=True)

    def start(self) -> CalibrationProcessStatus:
        with self._lock:
            if self._status.active:
                raise CalibrationBusyError("La calibración ya está activa")
            self._shutdown_requested = False
            started_at = datetime.now(timezone.utc).isoformat()
            self._status = CalibrationProcessStatus(
                status="stopping",
                active=True,
                message="Liberando la cámara del backend",
                started_at=started_at,
            )
            self._worker = threading.Thread(
                target=self._run,
                name="ojo-halcon-calibration",
                daemon=True,
            )
            self._worker.start()
            return self._status.model_copy(deep=True)

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown_requested = True
            process = self._process
            worker = self._worker
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=5)

    def _run(self) -> None:
        error_message: str | None = None
        try:
            if not self.runtime.stop(timeout=8):
                raise RuntimeError("La cámara no se liberó dentro del tiempo esperado")
            self.runtime.enter_calibration_mode()
            if self._is_shutting_down():
                return

            command = [
                sys.executable,
                "-m",
                "ojo_halcon",
                "--camera",
                str(self.runtime.camera_index),
                "--config",
                str(self.config_path),
            ]
            process = self._process_factory(command, cwd=str(BACKEND_DIR))
            with self._lock:
                self._process = process
                self._status = self._status.model_copy(
                    update={
                        "status": "calibrating",
                        "message": "Calibrador abierto; guarda con S y cierra con Q",
                    }
                )
            return_code = process.wait()
            with self._lock:
                self._process = None
            if self._is_shutting_down():
                return

            self._set_restarting()
            if return_code != 0:
                error_message = f"El calibrador terminó con código {return_code}"
            else:
                config = AppConfig.load(self.config_path, require_exists=True)
                self.runtime.replace_config(config)
        except Exception as error:
            error_message = str(error)
        finally:
            if not self._is_shutting_down():
                self.runtime.start()
                with self._lock:
                    if error_message is None:
                        self._status = CalibrationProcessStatus(
                            status="idle",
                            active=False,
                            message="Calibración cerrada; backend reactivado",
                            started_at=self._status.started_at,
                        )
                    else:
                        self._status = CalibrationProcessStatus(
                            status="error",
                            active=False,
                            message=(
                                "El backend se reactivó con la configuración anterior"
                            ),
                            error=error_message,
                            started_at=self._status.started_at,
                        )

    def _set_restarting(self) -> None:
        with self._lock:
            self._status = self._status.model_copy(
                update={
                    "status": "restarting",
                    "message": "Recargando configuración y reiniciando la cámara",
                }
            )

    def _is_shutting_down(self) -> bool:
        with self._lock:
            return self._shutdown_requested
