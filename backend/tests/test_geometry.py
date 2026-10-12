import unittest

from ojo_halcon.config import GeometryConfig
from ojo_halcon.geometry import BallRelation, classify_ball_against_line


class GeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.line = [[0, 100], [200, 100]]
        self.goal_side = [100, 150]
        self.config = GeometryConfig(line_tolerance_px=2)

    def classify(self, center: tuple[float, float], radius: float = 10):
        return classify_ball_against_line(
            center,
            radius,
            self.line,
            self.goal_side,
            self.config,
        )

    def test_classifies_before_touching_partial_and_crossed(self) -> None:
        self.assertEqual(self.classify((100, 70)).relation, BallRelation.BEFORE)
        self.assertEqual(self.classify((100, 90)).relation, BallRelation.TOUCHING)
        self.assertEqual(self.classify((100, 100)).relation, BallRelation.PARTIAL)
        self.assertEqual(self.classify((100, 113)).relation, BallRelation.CROSSED)

    def test_rejects_ball_not_fully_between_posts(self) -> None:
        result = self.classify((5, 113))

        self.assertEqual(result.relation, BallRelation.OUTSIDE_MOUTH)
        self.assertFalse(result.inside_mouth)

    def test_line_direction_does_not_change_goal_side(self) -> None:
        result = classify_ball_against_line(
            (100, 113),
            10,
            list(reversed(self.line)),
            self.goal_side,
            self.config,
        )

        self.assertEqual(result.relation, BallRelation.CROSSED)
        self.assertGreater(result.signed_distance, 0)

    def test_diagonal_line_uses_perpendicular_distance(self) -> None:
        result = classify_ball_against_line(
            (30, 70),
            5,
            [[0, 0], [100, 100]],
            [0, 100],
            self.config,
        )

        self.assertEqual(result.relation, BallRelation.CROSSED)
        self.assertAlmostEqual(result.signed_distance, 28.284, places=3)

    def test_requires_goal_side_calibration(self) -> None:
        result = classify_ball_against_line(
            (100, 113), 10, self.line, None, self.config
        )

        self.assertEqual(result.relation, BallRelation.UNCALIBRATED)


if __name__ == "__main__":
    unittest.main()
