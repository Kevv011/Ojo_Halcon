from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .config import GeometryConfig


class BallRelation(str, Enum):
    UNCALIBRATED = "SIN CALIBRAR"
    OUTSIDE_MOUTH = "FUERA DE LOS POSTES"
    BEFORE = "ANTES"
    TOUCHING = "TOCANDO"
    PARTIAL = "PARCIAL"
    CROSSED = "CRUZADO"


@dataclass(frozen=True)
class GeometryResult:
    relation: BallRelation
    signed_distance: float = 0.0
    leading_edge: float = 0.0
    trailing_edge: float = 0.0
    along_line: float = 0.0
    inside_mouth: bool = False


def classify_ball_against_line(
    center: tuple[float, float],
    radius: float,
    goal_line: list[list[int]] | None,
    goal_side_point: list[int] | None,
    config: GeometryConfig,
) -> GeometryResult:
    """Clasifica el balón; el lado del punto de gol siempre es positivo."""
    if not goal_line or len(goal_line) != 2 or not goal_side_point:
        return GeometryResult(BallRelation.UNCALIBRATED)

    ax, ay = (float(value) for value in goal_line[0])
    bx, by = (float(value) for value in goal_line[1])
    cx, cy = center
    gx, gy = (float(value) for value in goal_side_point)
    dx, dy = bx - ax, by - ay
    line_length = math.hypot(dx, dy)
    if line_length <= 1e-6:
        return GeometryResult(BallRelation.UNCALIBRATED)

    # El producto cruz indica a qué lado de la línea está cada punto.
    goal_cross = dx * (gy - ay) - dy * (gx - ax)
    if abs(goal_cross) <= 1e-6:
        return GeometryResult(BallRelation.UNCALIBRATED)
    side_sign = 1.0 if goal_cross > 0 else -1.0
    ball_cross = dx * (cy - ay) - dy * (cx - ax)
    signed_distance = side_sign * ball_cross / line_length

    # Posición paralela a la línea para verificar que pase entre los postes.
    along_line = ((cx - ax) * dx + (cy - ay) * dy) / line_length
    required_margin = max(0.0, radius + config.post_margin_px)
    inside_mouth = required_margin <= along_line <= line_length - required_margin

    leading_edge = signed_distance + radius
    trailing_edge = signed_distance - radius
    tolerance = max(0.0, config.line_tolerance_px)

    if not inside_mouth:
        relation = BallRelation.OUTSIDE_MOUTH
    elif leading_edge < -tolerance:
        relation = BallRelation.BEFORE
    elif abs(leading_edge) <= tolerance:
        relation = BallRelation.TOUCHING
    elif trailing_edge <= tolerance:
        relation = BallRelation.PARTIAL
    else:
        relation = BallRelation.CROSSED

    return GeometryResult(
        relation=relation,
        signed_distance=signed_distance,
        leading_edge=leading_edge,
        trailing_edge=trailing_edge,
        along_line=along_line,
        inside_mouth=inside_mouth,
    )
