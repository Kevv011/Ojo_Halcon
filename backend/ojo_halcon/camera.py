from __future__ import annotations

import cv2

from .config import AppConfig


class CameraError(RuntimeError):
    """Error esperado al abrir o leer una webcam."""


class CameraOpenError(CameraError):
    """La webcam no pudo abrirse."""


class CameraReadError(CameraError):
    """La webcam dejó de entregar imágenes."""


def open_camera(index: int, config: AppConfig) -> cv2.VideoCapture:
    """Abre la webcam con los mismos parámetros en calibración y servidor."""
    camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if config.camera.use_mjpg:
        # MJPG reduce el volumen de datos que entrega la webcam por USB.
        camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.height)
    camera.set(cv2.CAP_PROP_FPS, config.camera.fps)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, config.camera.buffer_size)
    if not camera.isOpened():
        camera.release()
        raise CameraOpenError(
            f"No se pudo abrir la webcam {index}. Prueba --camera 1 o cierra otras apps."
        )
    return camera
