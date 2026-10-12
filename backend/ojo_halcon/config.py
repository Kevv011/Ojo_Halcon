from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Indica que un archivo o parámetro de configuración no es utilizable."""


@dataclass
class CameraConfig:
    width: int = 1280  # Ancho solicitado a la webcam.
    height: int = 720  # Alto solicitado a la webcam.
    fps: int = 30  # Fotogramas por segundo solicitados.
    use_mjpg: bool = True  # Compresión de webcam que suele mejorar los FPS.
    buffer_size: int = 1  # Reduce el retraso usando solo el frame más reciente.


@dataclass
class BallConfig:
    hsv_lower: list[int] = field(default_factory=lambda: [95, 110, 80])  # Color mínimo aceptado.
    hsv_upper: list[int] = field(default_factory=lambda: [125, 255, 255])  # Color máximo aceptado.
    min_area: float = 250  # Descarta manchas pequeñas.
    max_area: float = 50_000  # Descarta regiones demasiado grandes.
    morphology_kernel: int = 5  # Limpia ruido y huecos de la máscara.
    min_circularity: float = 0.45  # Rechaza objetos muy alargados.


@dataclass
class TrackingConfig:
    smoothing_alpha: float = 0.35  # Suaviza centro y radio; menor = más estable.
    velocity_alpha: float = 0.30  # Suaviza la velocidad calculada.
    max_lost_frames: int = 3  # Frames que se conserva una detección perdida.
    max_lost_seconds: float = 0.50  # Evita que esa pérdida dure demasiado a bajos FPS.
    history_size: int = 24  # Cantidad de puntos dibujados en la trayectoria.
    max_jump_px: float = 250  # Salto máximo permitido entre frames.


@dataclass
class GeometryConfig:
    line_tolerance_px: float = 3  # Margen para absorber ruido junto a la línea.
    post_margin_px: float = 0  # Separación adicional exigida junto a los postes.


@dataclass
class GameConfig:
    activation_distance_px: float = 220  # Distancia desde la que inicia el análisis.
    min_approach_speed_px_s: float = 12  # Velocidad mínima hacia la portería.
    before_memory_seconds: float = 2.0  # Recuerda que el balón venía del exterior.
    goal_confirmation_seconds: float = 0.20  # Tiempo mínimo completamente cruzado.
    min_goal_observations: int = 2  # Detecciones reales requeridas para confirmar.
    no_goal_stationary_seconds: float = 1.0  # Espera antes de fallar un balón detenido.
    stationary_speed_px_s: float = 12  # Por debajo se considera casi detenido.
    analysis_timeout_seconds: float = 3.0  # Duración máxima de una jugada.
    max_detection_gap_seconds: float = 0.50  # Pérdida máxima durante una jugada.
    outside_mouth_seconds: float = 0.35  # Confirma que salió por un lateral.
    result_display_seconds: float = 4.0  # Tiempo mínimo visible del resultado.
    rearm_absence_seconds: float = 0.8  # Ausencia necesaria para una nueva jugada.


@dataclass
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    ball: BallConfig = field(default_factory=BallConfig)
    goal_line: list[list[int]] | None = None  # Dos extremos de la línea de gol.
    goal_side_point: list[int] | None = None  # Punto que identifica el interior.
    roi: list[list[int]] | None = None  # Polígono donde se permite detectar.
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    geometry: GeometryConfig = field(default_factory=GeometryConfig)
    game: GameConfig = field(default_factory=GameConfig)

    @classmethod
    def load(cls, path: Path, require_exists: bool = False) -> "AppConfig":
        if not path.exists():
            if require_exists:
                raise ConfigError(f"No existe el archivo de configuración: {path}")
            return cls()
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ConfigError(f"No se pudo leer la configuración {path}: {error}") from error
        if not isinstance(data, dict):
            raise ConfigError("La raíz de la configuración debe ser un objeto JSON")
        try:
            config = cls(
                camera=CameraConfig(**data.get("camera", {})),
                ball=BallConfig(**data.get("ball", {})),
                goal_line=data.get("goal_line"),
                goal_side_point=data.get("goal_side_point"),
                roi=data.get("roi"),
                tracking=TrackingConfig(**data.get("tracking", {})),
                geometry=GeometryConfig(**data.get("geometry", {})),
                game=GameConfig(**data.get("game", {})),
            )
        except (TypeError, ValueError) as error:
            raise ConfigError(f"Estructura de configuración inválida: {error}") from error
        config.validate()
        return config

    def validate(self) -> None:
        """Valida rangos que podrían bloquear o volver incoherente el sistema."""
        errors: list[str] = []
        if not _positive_int(self.camera.width) or not _positive_int(self.camera.height):
            errors.append("camera.width y camera.height deben ser positivos")
        if not _positive_number(self.camera.fps):
            errors.append("camera.fps debe ser positivo")
        if not _positive_int(self.camera.buffer_size):
            errors.append("camera.buffer_size debe ser al menos 1")
        if not isinstance(self.camera.use_mjpg, bool):
            errors.append("camera.use_mjpg debe ser true o false")

        lower_errors = _hsv_errors("ball.hsv_lower", self.ball.hsv_lower)
        upper_errors = _hsv_errors("ball.hsv_upper", self.ball.hsv_upper)
        errors.extend(lower_errors)
        errors.extend(upper_errors)
        if not lower_errors and not upper_errors and (
            self.ball.hsv_lower[1] > self.ball.hsv_upper[1]
            or self.ball.hsv_lower[2] > self.ball.hsv_upper[2]
        ):
            errors.append("ball.hsv_lower no puede superar hsv_upper en S o V")
        if (
            not _positive_number(self.ball.min_area)
            or not _positive_number(self.ball.max_area)
            or self.ball.max_area <= self.ball.min_area
        ):
            errors.append("ball.max_area debe ser mayor que ball.min_area > 0")
        if not _positive_int(self.ball.morphology_kernel):
            errors.append("ball.morphology_kernel debe ser al menos 1")
        if not _number_in_range(self.ball.min_circularity, 0, 1):
            errors.append("ball.min_circularity debe estar entre 0 y 1")

        if not _number_in_range(self.tracking.smoothing_alpha, 0, 1, lower_open=True):
            errors.append("tracking.smoothing_alpha debe estar entre 0 y 1")
        if not _number_in_range(self.tracking.velocity_alpha, 0, 1, lower_open=True):
            errors.append("tracking.velocity_alpha debe estar entre 0 y 1")
        if not _nonnegative_int(self.tracking.max_lost_frames):
            errors.append("tracking.max_lost_frames no puede ser negativo")
        if not _positive_number(self.tracking.max_lost_seconds):
            errors.append("tracking.max_lost_seconds debe ser positivo")
        if not _positive_int(self.tracking.history_size):
            errors.append("tracking.history_size debe ser al menos 1")
        if not _positive_number(self.tracking.max_jump_px):
            errors.append("tracking.max_jump_px debe ser positivo")

        if not _nonnegative_number(
            self.geometry.line_tolerance_px
        ) or not _nonnegative_number(self.geometry.post_margin_px):
            errors.append("los márgenes de geometry no pueden ser negativos")

        positive_game_values = {
            "activation_distance_px": self.game.activation_distance_px,
            "min_approach_speed_px_s": self.game.min_approach_speed_px_s,
            "before_memory_seconds": self.game.before_memory_seconds,
            "goal_confirmation_seconds": self.game.goal_confirmation_seconds,
            "no_goal_stationary_seconds": self.game.no_goal_stationary_seconds,
            "stationary_speed_px_s": self.game.stationary_speed_px_s,
            "analysis_timeout_seconds": self.game.analysis_timeout_seconds,
            "max_detection_gap_seconds": self.game.max_detection_gap_seconds,
            "outside_mouth_seconds": self.game.outside_mouth_seconds,
            "result_display_seconds": self.game.result_display_seconds,
            "rearm_absence_seconds": self.game.rearm_absence_seconds,
        }
        for name, value in positive_game_values.items():
            if not _positive_number(value):
                errors.append(f"game.{name} debe ser positivo")
        if not _positive_int(self.game.min_goal_observations):
            errors.append("game.min_goal_observations debe ser al menos 1")

        errors.extend(self._geometry_errors())
        if errors:
            raise ConfigError("; ".join(errors))

    @property
    def calibration_ready(self) -> bool:
        return not self.calibration_errors()

    def calibration_errors(self) -> list[str]:
        errors: list[str] = []
        if self.goal_line is None:
            errors.append("falta goal_line")
        if self.goal_side_point is None:
            errors.append("falta goal_side_point")
        if self.roi is None:
            errors.append("falta roi")
        return errors

    def _geometry_errors(self) -> list[str]:
        errors: list[str] = []
        if self.goal_line is not None:
            errors.extend(_points_errors("goal_line", self.goal_line, exact=2))
        if self.goal_side_point is not None:
            errors.extend(_points_errors("goal_side_point", [self.goal_side_point], exact=1))
        if self.roi is not None:
            errors.extend(_points_errors("roi", self.roi, minimum=3))

        all_points: list[tuple[str, list[int]]] = []
        if isinstance(self.goal_line, list):
            all_points.extend(("goal_line", point) for point in self.goal_line)
        if isinstance(self.goal_side_point, list):
            all_points.append(("goal_side_point", self.goal_side_point))
        if isinstance(self.roi, list):
            all_points.extend(("roi", point) for point in self.roi)
        if _positive_int(self.camera.width) and _positive_int(self.camera.height):
            for name, point in all_points:
                if not _valid_point(point):
                    continue
                x, y = point
                if not 0 <= x < self.camera.width or not 0 <= y < self.camera.height:
                    errors.append(f"{name} contiene un punto fuera de la resolución")

        if self.goal_line is not None and not _points_errors(
            "goal_line", self.goal_line, exact=2
        ):
            if math.dist(self.goal_line[0], self.goal_line[1]) < 2:
                errors.append("goal_line debe tener dos extremos diferentes")
            if self.goal_side_point is not None and _valid_point(self.goal_side_point):
                ax, ay = self.goal_line[0]
                bx, by = self.goal_line[1]
                gx, gy = self.goal_side_point
                line_length = max(math.dist((ax, ay), (bx, by)), 1e-6)
                distance = abs((bx - ax) * (gy - ay) - (by - ay) * (gx - ax)) / line_length
                if distance < 1:
                    errors.append("goal_side_point debe estar claramente a un lado de la línea")

        if self.roi is not None and not _points_errors("roi", self.roi, minimum=3):
            area = abs(
                sum(
                    self.roi[index][0] * self.roi[(index + 1) % len(self.roi)][1]
                    - self.roi[(index + 1) % len(self.roi)][0] * self.roi[index][1]
                    for index in range(len(self.roi))
                )
            ) / 2
            if area < 10:
                errors.append("roi debe formar un polígono con área válida")
        return errors

    def save(self, path: Path) -> None:
        self.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def _valid_point(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(
            isinstance(coordinate, int) and not isinstance(coordinate, bool)
            for coordinate in value
        )
    )


def _points_errors(
    name: str,
    points: Any,
    *,
    exact: int | None = None,
    minimum: int | None = None,
) -> list[str]:
    if not isinstance(points, list):
        return [f"{name} debe ser una lista de puntos"]
    if exact is not None and len(points) != exact:
        return [f"{name} debe contener exactamente {exact} puntos"]
    if minimum is not None and len(points) < minimum:
        return [f"{name} debe contener al menos {minimum} puntos"]
    if not all(_valid_point(point) for point in points):
        return [f"cada punto de {name} debe contener dos enteros"]
    return []


def _hsv_errors(name: str, values: Any) -> list[str]:
    if not isinstance(values, list) or len(values) != 3:
        return [f"{name} debe contener tres enteros"]
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return [f"{name} debe contener tres enteros"]
    if not 0 <= values[0] <= 179 or not all(0 <= value <= 255 for value in values[1:]):
        return [f"{name} debe respetar H 0-179 y S/V 0-255"]
    return []


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _positive_number(value: Any) -> bool:
    return _is_number(value) and value > 0


def _nonnegative_number(value: Any) -> bool:
    return _is_number(value) and value >= 0


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _number_in_range(
    value: Any,
    lower: float,
    upper: float,
    *,
    lower_open: bool = False,
) -> bool:
    if not _is_number(value):
        return False
    lower_valid = value > lower if lower_open else value >= lower
    return lower_valid and value <= upper
