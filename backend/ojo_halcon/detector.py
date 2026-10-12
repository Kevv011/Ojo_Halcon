from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import BallConfig


@dataclass(frozen=True)
class BallDetection:
    center: tuple[int, int]
    radius: float
    area: float
    circularity: float


def build_hsv_mask(
    frame: np.ndarray,
    config: BallConfig,
    roi: list[list[int]] | None = None,
) -> np.ndarray:
    """Crea una máscara HSV, incluyendo rangos que cruzan el rojo (0/179)."""
    if roi and len(roi) >= 3:
        # Procesar solo el rectángulo que contiene la ROI ahorra trabajo por frame.
        points = np.array(roi, dtype=np.int32)
        x, y, width, height = cv2.boundingRect(points)
        x = max(0, x)
        y = max(0, y)
        width = min(width, frame.shape[1] - x)
        height = min(height, frame.shape[0] - y)
        full_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        if width <= 0 or height <= 0:
            return full_mask

        cropped = frame[y : y + height, x : x + width]
        cropped_mask = _threshold_and_clean(cropped, config)
        local_points = points - np.array([x, y], dtype=np.int32)
        polygon_mask = np.zeros(cropped_mask.shape, dtype=np.uint8)
        cv2.fillPoly(polygon_mask, [local_points], 255)
        full_mask[y : y + height, x : x + width] = cv2.bitwise_and(
            cropped_mask, polygon_mask
        )
        return full_mask

    return _threshold_and_clean(frame, config)


def _threshold_and_clean(frame: np.ndarray, config: BallConfig) -> np.ndarray:
    """Aplica el rango de color y limpia pequeñas imperfecciones."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array(config.hsv_lower, dtype=np.uint8)
    upper = np.array(config.hsv_upper, dtype=np.uint8)

    if config.hsv_lower[0] <= config.hsv_upper[0]:
        mask = cv2.inRange(hsv, lower, upper)
    else:
        lower_red = np.array([0, lower[1], lower[2]], dtype=np.uint8)
        upper_red = np.array([upper[0], upper[1], upper[2]], dtype=np.uint8)
        lower_wrap = np.array([lower[0], lower[1], lower[2]], dtype=np.uint8)
        upper_wrap = np.array([179, upper[1], upper[2]], dtype=np.uint8)
        mask = cv2.bitwise_or(
            cv2.inRange(hsv, lower_red, upper_red),
            cv2.inRange(hsv, lower_wrap, upper_wrap),
        )

    kernel_size = max(1, config.morphology_kernel)
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def detect_ball(mask: np.ndarray, config: BallConfig) -> BallDetection | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[np.ndarray, float, float]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if not config.min_area <= area <= config.max_area:
            continue
        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0:
            continue
        # 1.0 representa un círculo ideal; valores bajos suelen ser ruido alargado.
        circularity = float(4 * np.pi * area / (perimeter * perimeter))
        if circularity >= config.min_circularity:
            candidates.append((contour, area, circularity))
    if not candidates:
        return None

    contour, area, circularity = max(candidates, key=lambda item: item[1])
    (x, y), radius = cv2.minEnclosingCircle(contour)
    return BallDetection(
        center=(round(x), round(y)),
        radius=radius,
        area=area,
        circularity=circularity,
    )
