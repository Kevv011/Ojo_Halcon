from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config import GameConfig
from .geometry import BallRelation, GeometryResult


class GameState(str, Enum):
    WAITING = "ESPERANDO JUGADA"
    ANALYZING = "ANALIZANDO"
    GOAL = "GOAL"
    NO_GOAL = "NO GOAL"


@dataclass(frozen=True)
class GameSnapshot:
    state: GameState
    play_id: int
    reason: str
    state_elapsed: float
    approach_speed: float
    crossed_observations: int
    waiting_for_removal: bool


class GameController:
    """Decide una jugada usando tiempos reales, independiente de los FPS."""

    def __init__(
        self,
        config: GameConfig,
        initial_play_id: int = 0,
        initial_timestamp: float = 0.0,
    ) -> None:
        self.config = config
        self._play_id = max(0, initial_play_id)
        self.reset(initial_timestamp)

    def reset(self, timestamp: float) -> GameSnapshot:
        self._state = GameState.WAITING
        self._state_since = timestamp
        self._reason = "Esperando que el balon se aproxime desde el exterior"
        self._last_distance: float | None = None
        self._last_distance_at: float | None = None
        self._last_detection_at: float | None = None
        self._seen_before_at: float | None = None
        self._approach_speed = 0.0
        self._crossed_since: float | None = None
        self._crossed_observations = 0
        self._stationary_since: float | None = None
        self._outside_since: float | None = None
        self._reached_line = False
        self._absent_since: float | None = None
        return self._snapshot(timestamp, waiting_for_removal=False)

    def update(
        self,
        geometry: GeometryResult | None,
        detected: bool,
        track_speed: float,
        timestamp: float,
    ) -> GameSnapshot:
        valid = (
            detected
            and geometry is not None
            and geometry.relation is not BallRelation.UNCALIBRATED
        )
        if valid and geometry is not None:
            self._record_detection(geometry, timestamp)

        if self._state is GameState.WAITING:
            self._update_waiting(geometry if valid else None, track_speed, timestamp)
        elif self._state is GameState.ANALYZING:
            self._update_analyzing(geometry if valid else None, track_speed, timestamp)
        else:
            self._update_result(detected, timestamp)

        waiting_for_removal = (
            self._state in (GameState.GOAL, GameState.NO_GOAL)
            and timestamp - self._state_since >= self.config.result_display_seconds
            and detected
        )
        return self._snapshot(timestamp, waiting_for_removal)

    def _record_detection(self, geometry: GeometryResult, timestamp: float) -> None:
        if self._last_distance is not None and self._last_distance_at is not None:
            elapsed = max(timestamp - self._last_distance_at, 1e-6)
            instant_speed = (geometry.signed_distance - self._last_distance) / elapsed
            self._approach_speed = 0.4 * instant_speed + 0.6 * self._approach_speed
        self._last_distance = geometry.signed_distance
        self._last_distance_at = timestamp
        self._last_detection_at = timestamp
        self._absent_since = None
        # También recuerda tiros que se aproximan por fuera de los postes.
        if geometry.leading_edge < 0:
            self._seen_before_at = timestamp

    def _update_waiting(
        self,
        geometry: GeometryResult | None,
        track_speed: float,
        timestamp: float,
    ) -> None:
        if geometry is None:
            self._reason = "Esperando detectar el balon"
            return
        saw_before_recently = (
            self._seen_before_at is not None
            and timestamp - self._seen_before_at <= self.config.before_memory_seconds
        )
        near_line = geometry.signed_distance >= -self.config.activation_distance_px
        approaching = (
            self._approach_speed >= self.config.min_approach_speed_px_s
            and track_speed >= self.config.stationary_speed_px_s
        )
        reached_line = geometry.leading_edge >= 0 or geometry.relation in (
            BallRelation.TOUCHING,
            BallRelation.PARTIAL,
            BallRelation.CROSSED,
        )
        if not saw_before_recently:
            self._reason = "Inicia el tiro desde fuera y muevelo hacia la linea"
            return
        if not near_line:
            self._reason = "Balon detectado; acercalo a la linea"
            return
        if not (approaching or reached_line):
            self._reason = "Mueve el balon hacia la porteria"
            return
        if saw_before_recently and near_line and (approaching or reached_line):
            self._play_id += 1
            self._state = GameState.ANALYZING
            self._state_since = timestamp
            self._reason = "Balon acercandose a la linea"
            self._crossed_since = None
            self._crossed_observations = 0
            self._stationary_since = None
            self._outside_since = None
            self._reached_line = reached_line
            self._update_analyzing(geometry, track_speed, timestamp)

    def _update_analyzing(
        self,
        geometry: GeometryResult | None,
        track_speed: float,
        timestamp: float,
    ) -> None:
        if timestamp - self._state_since >= self.config.analysis_timeout_seconds:
            self._finish(GameState.NO_GOAL, "Tiempo de analisis agotado", timestamp)
            return

        if geometry is None:
            if (
                self._last_detection_at is not None
                and timestamp - self._last_detection_at
                >= self.config.max_detection_gap_seconds
            ):
                self._finish(GameState.NO_GOAL, "Balon perdido antes del cruce", timestamp)
            return

        if geometry.relation is BallRelation.OUTSIDE_MOUTH:
            # Solo es NO GOAL cuando todo el balón cruzó el plano por un lateral.
            if geometry.trailing_edge > 0:
                if self._outside_since is None:
                    self._outside_since = timestamp
                elif timestamp - self._outside_since >= self.config.outside_mouth_seconds:
                    self._finish(
                        GameState.NO_GOAL,
                        "Cruzo por fuera de los postes",
                        timestamp,
                    )
                return
            self._outside_since = None
        else:
            self._outside_since = None

        if geometry.leading_edge >= 0 or geometry.relation in (
            BallRelation.TOUCHING,
            BallRelation.PARTIAL,
        ):
            self._reached_line = True

        if geometry.relation is BallRelation.CROSSED:
            if self._crossed_since is None:
                self._crossed_since = timestamp
                self._crossed_observations = 1
            else:
                self._crossed_observations += 1
            crossed_long_enough = (
                timestamp - self._crossed_since
                >= self.config.goal_confirmation_seconds
            )
            enough_observations = (
                self._crossed_observations >= self.config.min_goal_observations
            )
            if crossed_long_enough and enough_observations:
                self._finish(GameState.GOAL, "Cruce completo confirmado", timestamp)
            return
        self._crossed_since = None
        self._crossed_observations = 0

        if (
            self._reached_line
            and geometry.leading_edge < 0
            and self._approach_speed <= -self.config.min_approach_speed_px_s
        ):
            self._finish(GameState.NO_GOAL, "Balon retrocedio sin cruzar", timestamp)
            return

        if geometry.relation in (
            BallRelation.BEFORE,
            BallRelation.TOUCHING,
            BallRelation.PARTIAL,
            BallRelation.OUTSIDE_MOUTH,
        ) and track_speed <= self.config.stationary_speed_px_s:
            if self._stationary_since is None:
                self._stationary_since = timestamp
            elif (
                timestamp - self._stationary_since
                >= self.config.no_goal_stationary_seconds
            ):
                self._finish(GameState.NO_GOAL, "Balon detenido sin cruzar", timestamp)
        else:
            self._stationary_since = None

    def _update_result(self, detected: bool, timestamp: float) -> None:
        if detected:
            self._absent_since = None
        elif self._absent_since is None:
            self._absent_since = timestamp

        result_finished = (
            timestamp - self._state_since >= self.config.result_display_seconds
        )
        absent_long_enough = (
            self._absent_since is not None
            and timestamp - self._absent_since >= self.config.rearm_absence_seconds
        )
        if result_finished and absent_long_enough:
            self.reset(timestamp)

    def _finish(self, state: GameState, reason: str, timestamp: float) -> None:
        self._state = state
        self._state_since = timestamp
        self._reason = reason
        self._absent_since = None

    def _snapshot(self, timestamp: float, waiting_for_removal: bool) -> GameSnapshot:
        return GameSnapshot(
            state=self._state,
            play_id=self._play_id,
            reason=self._reason,
            state_elapsed=max(0.0, timestamp - self._state_since),
            approach_speed=self._approach_speed,
            crossed_observations=self._crossed_observations,
            waiting_for_removal=waiting_for_removal,
        )
