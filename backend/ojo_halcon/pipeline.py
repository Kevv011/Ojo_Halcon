from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from .config import AppConfig
from .detector import BallDetection, build_hsv_mask, detect_ball
from .game import GameController, GameSnapshot
from .geometry import GeometryResult, classify_ball_against_line
from .tracking import BallTracker, TrackSnapshot


@dataclass(frozen=True)
class FrameAnalysis:
    """Resultado completo de procesar un frame."""

    mask: np.ndarray
    detection: BallDetection | None
    track: TrackSnapshot
    geometry: GeometryResult | None
    game: GameSnapshot


class VisionPipeline:
    """Canal único de detección usado por calibración y API."""

    def __init__(
        self,
        config: AppConfig,
        initial_play_id: int = 0,
        initial_timestamp: float | None = None,
    ) -> None:
        self.config = config
        self.tracker = BallTracker(config.tracking)
        now = time.perf_counter() if initial_timestamp is None else initial_timestamp
        self.game = GameController(
            config.game,
            initial_play_id=initial_play_id,
            initial_timestamp=now,
        )

    def process(
        self,
        frame: np.ndarray,
        timestamp: float | None = None,
    ) -> FrameAnalysis:
        now = time.perf_counter() if timestamp is None else timestamp
        mask = build_hsv_mask(frame, self.config.ball, self.config.roi)
        detection = detect_ball(mask, self.config.ball)
        track = self.tracker.update(detection, now)
        geometry = self._geometry(track)
        game = self.game.update(geometry, track.detected, track.speed, now)
        return FrameAnalysis(mask, detection, track, geometry, game)

    def reset(self, timestamp: float | None = None) -> GameSnapshot:
        now = time.perf_counter() if timestamp is None else timestamp
        self.tracker.reset()
        return self.game.reset(now)

    def _geometry(self, track: TrackSnapshot) -> GeometryResult | None:
        if track.center is None or track.radius is None:
            return None
        return classify_ball_against_line(
            track.center,
            track.radius,
            self.config.goal_line,
            self.config.goal_side_point,
            self.config.geometry,
        )
