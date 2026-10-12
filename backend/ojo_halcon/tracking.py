from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass

from .config import TrackingConfig
from .detector import BallDetection


@dataclass(frozen=True)
class TrackSnapshot:
    center: tuple[float, float] | None
    radius: float | None
    velocity: tuple[float, float]
    speed: float
    detected: bool
    held: bool
    lost_frames: int
    history: tuple[tuple[int, int], ...]


class BallTracker:
    """Suaviza detecciones y conserva brevemente la pista cuando se pierde."""

    def __init__(self, config: TrackingConfig) -> None:
        self.config = config
        self._center: tuple[float, float] | None = None
        self._radius: float | None = None
        self._velocity = (0.0, 0.0)
        self._last_detection_time: float | None = None
        self._lost_frames = 0
        self._history: deque[tuple[int, int]] = deque(maxlen=config.history_size)

    def update(
        self,
        detection: BallDetection | None,
        timestamp: float | None = None,
    ) -> TrackSnapshot:
        now = time.perf_counter() if timestamp is None else timestamp
        if detection is None:
            return self._register_loss(now)

        raw_center = (float(detection.center[0]), float(detection.center[1]))
        if self._center is not None:
            # Evita que la pista salte de pronto hacia otro objeto del mismo color.
            jump = math.dist(self._center, raw_center)
            if jump > self.config.max_jump_px:
                return self._register_loss(now)

        previous_center = self._center
        alpha = self.config.smoothing_alpha
        if previous_center is None:
            self._center = raw_center
            self._radius = float(detection.radius)
            self._velocity = (0.0, 0.0)
        else:
            # Promedio exponencial: reduce el temblor sin guardar todos los frames.
            self._center = (
                alpha * raw_center[0] + (1 - alpha) * previous_center[0],
                alpha * raw_center[1] + (1 - alpha) * previous_center[1],
            )
            previous_radius = self._radius or float(detection.radius)
            self._radius = (
                alpha * float(detection.radius) + (1 - alpha) * previous_radius
            )
            self._update_velocity(previous_center, now)

        self._last_detection_time = now
        self._lost_frames = 0
        self._history.append((round(self._center[0]), round(self._center[1])))
        return self._snapshot(detected=True, held=False)

    def reset(self) -> None:
        self._center = None
        self._radius = None
        self._velocity = (0.0, 0.0)
        self._last_detection_time = None
        self._lost_frames = 0
        self._history.clear()

    def _update_velocity(
        self,
        previous_center: tuple[float, float],
        now: float,
    ) -> None:
        if self._last_detection_time is None or self._center is None:
            return
        elapsed = max(now - self._last_detection_time, 1e-6)
        instantaneous = (
            (self._center[0] - previous_center[0]) / elapsed,
            (self._center[1] - previous_center[1]) / elapsed,
        )
        alpha = self.config.velocity_alpha
        self._velocity = (
            alpha * instantaneous[0] + (1 - alpha) * self._velocity[0],
            alpha * instantaneous[1] + (1 - alpha) * self._velocity[1],
        )

    def _register_loss(self, timestamp: float) -> TrackSnapshot:
        # Limita por frames y tiempo para comportarse bien aunque cambien los FPS.
        within_time = (
            self._last_detection_time is not None
            and timestamp - self._last_detection_time
            <= self.config.max_lost_seconds
        )
        if (
            self._center is not None
            and self._lost_frames < self.config.max_lost_frames
            and within_time
        ):
            self._lost_frames += 1
            return self._snapshot(detected=False, held=True)
        self.reset()
        return self._snapshot(detected=False, held=False)

    def _snapshot(self, detected: bool, held: bool) -> TrackSnapshot:
        speed = math.hypot(*self._velocity)
        return TrackSnapshot(
            center=self._center,
            radius=self._radius,
            velocity=self._velocity,
            speed=speed,
            detected=detected,
            held=held,
            lost_frames=self._lost_frames,
            history=tuple(self._history),
        )
