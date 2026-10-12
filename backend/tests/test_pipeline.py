import unittest

import cv2
import numpy as np

from ojo_halcon.config import AppConfig, BallConfig, GameConfig, TrackingConfig
from ojo_halcon.game import GameState
from ojo_halcon.pipeline import VisionPipeline


class VisionPipelineTests(unittest.TestCase):
    def test_synthetic_ball_sequence_reaches_goal(self) -> None:
        config = AppConfig(
            ball=BallConfig(
                hsv_lower=[100, 100, 50],
                hsv_upper=[130, 255, 255],
                min_area=100,
                max_area=2_000,
                morphology_kernel=3,
                min_circularity=0.5,
            ),
            goal_line=[[50, 100], [270, 100]],
            goal_side_point=[160, 150],
            roi=[[0, 0], [319, 0], [319, 239], [0, 239]],
            tracking=TrackingConfig(
                smoothing_alpha=1.0,
                velocity_alpha=1.0,
                max_lost_frames=3,
                history_size=12,
                max_jump_px=100,
            ),
            game=GameConfig(
                min_approach_speed_px_s=1,
                stationary_speed_px_s=0.1,
                goal_confirmation_seconds=0.2,
                min_goal_observations=2,
            ),
        )
        pipeline = VisionPipeline(config, initial_timestamp=0.0)

        snapshots = [
            pipeline.process(self._frame(y), timestamp)
            for y, timestamp in [(60, 0.0), (80, 0.2), (120, 0.4), (125, 0.65)]
        ]

        self.assertTrue(all(item.track.detected for item in snapshots))
        self.assertEqual(snapshots[-1].game.state, GameState.GOAL)

    @staticmethod
    def _frame(y: int) -> np.ndarray:
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.circle(frame, (160, y), 10, (255, 0, 0), -1)
        return frame


if __name__ == "__main__":
    unittest.main()
