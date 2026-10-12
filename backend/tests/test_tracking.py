import unittest

from ojo_halcon.config import TrackingConfig
from ojo_halcon.detector import BallDetection
from ojo_halcon.tracking import BallTracker


def detection(x: int, y: int, radius: float = 20) -> BallDetection:
    return BallDetection(
        center=(x, y),
        radius=radius,
        area=1200,
        circularity=0.9,
    )


class TrackingTests(unittest.TestCase):
    def test_smooths_position_and_radius(self) -> None:
        tracker = BallTracker(TrackingConfig(smoothing_alpha=0.5))
        tracker.update(detection(100, 100, 20), timestamp=1.0)

        result = tracker.update(detection(120, 80, 30), timestamp=2.0)

        self.assertEqual(result.center, (110.0, 90.0))
        self.assertEqual(result.radius, 25.0)
        self.assertTrue(result.detected)

    def test_holds_track_during_brief_losses_then_resets(self) -> None:
        tracker = BallTracker(TrackingConfig(max_lost_frames=2))
        tracker.update(detection(100, 100), timestamp=1.0)

        first_loss = tracker.update(None, timestamp=1.1)
        second_loss = tracker.update(None, timestamp=1.2)
        expired = tracker.update(None, timestamp=1.3)

        self.assertTrue(first_loss.held)
        self.assertTrue(second_loss.held)
        self.assertEqual(second_loss.center, (100.0, 100.0))
        self.assertFalse(expired.held)
        self.assertIsNone(expired.center)

    def test_rejects_an_impossible_jump(self) -> None:
        tracker = BallTracker(TrackingConfig(max_jump_px=50, max_lost_frames=2))
        tracker.update(detection(100, 100), timestamp=1.0)

        result = tracker.update(detection(300, 300), timestamp=1.1)

        self.assertFalse(result.detected)
        self.assertTrue(result.held)
        self.assertEqual(result.center, (100.0, 100.0))

    def test_loss_expires_by_time_even_if_frame_budget_remains(self) -> None:
        tracker = BallTracker(
            TrackingConfig(max_lost_frames=10, max_lost_seconds=0.25)
        )
        tracker.update(detection(100, 100), timestamp=1.0)

        expired = tracker.update(None, timestamp=1.3)

        self.assertFalse(expired.held)
        self.assertIsNone(expired.center)

    def test_history_is_bounded(self) -> None:
        tracker = BallTracker(
            TrackingConfig(history_size=3, smoothing_alpha=1.0, max_jump_px=100)
        )
        for index in range(5):
            result = tracker.update(detection(100 + index, 100), timestamp=float(index + 1))

        self.assertEqual(len(result.history), 3)
        self.assertEqual(result.history[-1], (104, 100))


if __name__ == "__main__":
    unittest.main()
