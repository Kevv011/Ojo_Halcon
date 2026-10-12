import unittest

from ojo_halcon.config import GameConfig
from ojo_halcon.game import GameController, GameState
from ojo_halcon.geometry import BallRelation, GeometryResult


def geometry(
    relation: BallRelation,
    distance: float,
    inside_mouth: bool = True,
) -> GeometryResult:
    return GeometryResult(
        relation=relation,
        signed_distance=distance,
        leading_edge=distance + 20,
        trailing_edge=distance - 20,
        along_line=100,
        inside_mouth=inside_mouth,
    )


def start_analysis(controller: GameController) -> None:
    controller.update(geometry(BallRelation.BEFORE, -160), True, 30, 0.0)
    result = controller.update(geometry(BallRelation.BEFORE, -130), True, 30, 0.2)
    assert result.state is GameState.ANALYZING


class GameControllerTests(unittest.TestCase):
    def test_initial_elapsed_time_uses_runtime_timestamp(self) -> None:
        controller = GameController(GameConfig(), initial_timestamp=500.0)

        snapshot = controller.update(None, False, 0, 500.25)

        self.assertAlmostEqual(snapshot.state_elapsed, 0.25)

    def test_continues_play_ids_from_persistent_history(self) -> None:
        controller = GameController(GameConfig(), initial_play_id=7)

        start_analysis(controller)

        snapshot = controller.update(
            geometry(BallRelation.CROSSED, 30), True, 30, 0.35
        )
        snapshot = controller.update(
            geometry(BallRelation.CROSSED, 35), True, 20, 0.56
        )
        self.assertEqual(snapshot.play_id, 8)

    def test_stays_waiting_until_ball_approaches(self) -> None:
        controller = GameController(GameConfig())

        first = controller.update(
            geometry(BallRelation.BEFORE, -160), True, 0, 0.0
        )
        second = controller.update(
            geometry(BallRelation.BEFORE, -160), True, 0, 0.3
        )

        self.assertEqual(first.state, GameState.WAITING)
        self.assertEqual(second.state, GameState.WAITING)

    def test_confirms_goal_by_time_and_real_observations(self) -> None:
        controller = GameController(GameConfig())
        start_analysis(controller)

        first_cross = controller.update(
            geometry(BallRelation.CROSSED, 30), True, 30, 0.35
        )
        confirmed = controller.update(
            geometry(BallRelation.CROSSED, 35), True, 20, 0.56
        )

        self.assertEqual(first_cross.state, GameState.ANALYZING)
        self.assertEqual(confirmed.state, GameState.GOAL)
        self.assertEqual(confirmed.play_id, 1)

    def test_stationary_ball_before_crossing_is_no_goal(self) -> None:
        controller = GameController(GameConfig())
        start_analysis(controller)

        controller.update(geometry(BallRelation.PARTIAL, 0), True, 0, 0.35)
        result = controller.update(
            geometry(BallRelation.PARTIAL, 0), True, 0, 1.40
        )

        self.assertEqual(result.state, GameState.NO_GOAL)
        self.assertEqual(result.reason, "Balon detenido sin cruzar")

    def test_lost_ball_during_analysis_is_no_goal(self) -> None:
        controller = GameController(GameConfig())
        start_analysis(controller)

        controller.update(None, False, 0, 0.4)
        result = controller.update(None, False, 0, 0.8)

        self.assertEqual(result.state, GameState.NO_GOAL)
        self.assertEqual(result.reason, "Balon perdido antes del cruce")

    def test_result_rearms_only_after_time_and_ball_removal(self) -> None:
        controller = GameController(GameConfig())
        start_analysis(controller)
        controller.update(geometry(BallRelation.CROSSED, 30), True, 30, 0.35)
        goal = controller.update(
            geometry(BallRelation.CROSSED, 35), True, 20, 0.56
        )

        still_goal = controller.update(None, False, 0, 1.0)
        rearmed = controller.update(None, False, 0, 4.70)

        self.assertEqual(goal.state, GameState.GOAL)
        self.assertEqual(still_goal.state, GameState.GOAL)
        self.assertEqual(rearmed.state, GameState.WAITING)
        self.assertEqual(rearmed.play_id, 1)

    def test_ball_outside_mouth_is_no_goal(self) -> None:
        controller = GameController(GameConfig())
        start_analysis(controller)

        outside = geometry(BallRelation.OUTSIDE_MOUTH, 30, inside_mouth=False)
        controller.update(outside, True, 30, 0.30)
        result = controller.update(outside, True, 30, 0.70)

        self.assertEqual(result.state, GameState.NO_GOAL)
        self.assertEqual(result.reason, "Cruzo por fuera de los postes")

    def test_shot_can_start_and_finish_outside_posts(self) -> None:
        controller = GameController(GameConfig())

        controller.update(
            geometry(BallRelation.OUTSIDE_MOUTH, -160, inside_mouth=False),
            True,
            30,
            0.0,
        )
        analyzing = controller.update(
            geometry(BallRelation.OUTSIDE_MOUTH, -130, inside_mouth=False),
            True,
            30,
            0.2,
        )
        controller.update(
            geometry(BallRelation.OUTSIDE_MOUTH, 30, inside_mouth=False),
            True,
            30,
            0.4,
        )
        result = controller.update(
            geometry(BallRelation.OUTSIDE_MOUTH, 35, inside_mouth=False),
            True,
            30,
            0.8,
        )

        self.assertEqual(analyzing.state, GameState.ANALYZING)
        self.assertEqual(result.state, GameState.NO_GOAL)
        self.assertEqual(result.reason, "Cruzo por fuera de los postes")

    def test_ball_retreating_after_reaching_line_is_no_goal(self) -> None:
        controller = GameController(GameConfig())
        start_analysis(controller)

        controller.update(geometry(BallRelation.PARTIAL, 0), True, 30, 0.30)
        controller.update(geometry(BallRelation.BEFORE, -50), True, 30, 0.50)
        controller.update(geometry(BallRelation.BEFORE, -120), True, 30, 0.70)
        result = controller.update(
            geometry(BallRelation.BEFORE, -180), True, 30, 0.90
        )

        self.assertEqual(result.state, GameState.NO_GOAL)
        self.assertEqual(result.reason, "Balon retrocedio sin cruzar")

    def test_analysis_timeout_is_no_goal(self) -> None:
        controller = GameController(GameConfig())
        start_analysis(controller)

        result = controller.update(
            geometry(BallRelation.BEFORE, -100), True, 30, 3.21
        )

        self.assertEqual(result.state, GameState.NO_GOAL)
        self.assertEqual(result.reason, "Tiempo de analisis agotado")


if __name__ == "__main__":
    unittest.main()
