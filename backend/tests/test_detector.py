import unittest

import cv2
import numpy as np

from ojo_halcon.config import BallConfig
from ojo_halcon.detector import build_hsv_mask, detect_ball


class DetectorTests(unittest.TestCase):
    def test_detects_blue_ball_near_expected_position(self) -> None:
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.circle(frame, (180, 90), 24, (255, 0, 0), -1)
        config = BallConfig(min_area=100, max_area=10_000)

        detection = detect_ball(build_hsv_mask(frame, config), config)

        self.assertIsNotNone(detection)
        assert detection is not None
        self.assertLessEqual(abs(detection.center[0] - 180), 1)
        self.assertLessEqual(abs(detection.center[1] - 90), 1)
        self.assertGreater(detection.radius, 20)

    def test_hue_range_can_wrap_around_red(self) -> None:
        frame = np.zeros((160, 240, 3), dtype=np.uint8)
        cv2.circle(frame, (70, 80), 20, (0, 0, 255), -1)
        config = BallConfig(
            hsv_lower=[170, 100, 100],
            hsv_upper=[10, 255, 255],
            min_area=100,
            max_area=10_000,
        )

        detection = detect_ball(build_hsv_mask(frame, config), config)

        self.assertIsNotNone(detection)

    def test_rejects_objects_smaller_than_minimum_area(self) -> None:
        frame = np.zeros((160, 240, 3), dtype=np.uint8)
        cv2.circle(frame, (70, 80), 3, (255, 0, 0), -1)
        config = BallConfig(min_area=250, max_area=10_000)

        detection = detect_ball(build_hsv_mask(frame, config), config)

        self.assertIsNone(detection)

    def test_roi_excludes_matching_objects_outside_play_area(self) -> None:
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.circle(frame, (70, 120), 25, (255, 0, 0), -1)
        cv2.circle(frame, (250, 120), 25, (255, 0, 0), -1)
        config = BallConfig(min_area=100, max_area=10_000)
        roi = [[160, 20], [310, 20], [310, 220], [160, 220]]

        detection = detect_ball(build_hsv_mask(frame, config, roi), config)

        self.assertIsNotNone(detection)
        assert detection is not None
        self.assertLessEqual(abs(detection.center[0] - 250), 1)


if __name__ == "__main__":
    unittest.main()
