import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from ojo_halcon.config import AppConfig
from ojo_halcon.detector import BallDetection
from ojo_halcon.game import GameSnapshot, GameState
from ojo_halcon.schemas import CameraStatus, DetectionStatus
from ojo_halcon.service import VisionRuntime


class VisionRuntimeTests(unittest.TestCase):
    def test_captures_exact_result_frame_by_play_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = VisionRuntime(
                AppConfig(),
                history_path=Path(directory) / "plays.jsonl",
            )
            result = GameSnapshot(
                state=GameState.GOAL,
                play_id=7,
                reason="Cruce completo confirmado",
                state_elapsed=0.0,
                approach_speed=80.0,
                crossed_observations=3,
                waiting_for_removal=False,
            )
            frame = np.zeros((120, 160, 3), dtype=np.uint8)

            runtime._capture_result_snapshot(result, frame)

            jpeg = runtime.get_result_jpeg(7)
            self.assertIsNotNone(jpeg)
            self.assertTrue(jpeg.startswith(b"\xff\xd8"))

    def test_records_each_final_decision_only_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = VisionRuntime(
                AppConfig(),
                history_path=Path(directory) / "plays.jsonl",
            )
            result = GameSnapshot(
                state=GameState.GOAL,
                play_id=1,
                reason="Cruce completo confirmado",
                state_elapsed=0.0,
                approach_speed=80.0,
                crossed_observations=3,
                waiting_for_removal=False,
            )

            runtime._record_result(result, "2026-10-11T12:00:00+00:00")
            runtime._record_result(result, "2026-10-11T12:00:01+00:00")

            self.assertEqual(runtime.history.total, 1)
            self.assertEqual(runtime.history.recent(1)[0].result, "GOAL")

    def test_camera_failure_clears_stale_detection_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = VisionRuntime(
                AppConfig(),
                history_path=Path(directory) / "plays.jsonl",
            )
            runtime._state.camera = CameraStatus(connected=True, index=0)
            runtime._state.detection = DetectionStatus(status="DETECTADO")
            runtime._latest_jpeg = b"old frame"
            runtime._pipeline.tracker.update(
                BallDetection(
                    center=(100, 100),
                    radius=20,
                    area=1_000,
                    circularity=0.8,
                ),
                timestamp=1.0,
            )

            runtime._set_runtime_error("desconectada", camera_failure=True)

            state = runtime.get_state()
            self.assertFalse(state.camera.connected)
            self.assertEqual(state.detection.status, "SIN BALON")
            self.assertIsNone(state.geometry)
            self.assertIsNone(runtime.get_latest_jpeg())
            reset_track = runtime._pipeline.tracker.update(None, timestamp=2.0)
            self.assertIsNone(reset_track.center)

    def test_health_is_ok_only_when_runtime_is_fully_ready(self) -> None:
        config = AppConfig(
            goal_line=[[10, 100], [200, 100]],
            goal_side_point=[100, 150],
            roi=[[0, 0], [300, 0], [300, 200], [0, 200]],
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = VisionRuntime(
                config,
                history_path=Path(directory) / "plays.jsonl",
            )
            runtime._state.camera = CameraStatus(
                connected=True,
                index=0,
                width=1280,
                height=720,
                resolution_matches=True,
            )
            runtime._last_frame_at = time.perf_counter()
            runtime._thread = Mock()
            runtime._thread.is_alive.return_value = True

            health = runtime.get_health()

            self.assertEqual(health.status, "ok")
            self.assertTrue(health.calibration_ready)
            self.assertTrue(health.processing_alive)

    def test_history_failure_does_not_escape_or_hide_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = VisionRuntime(
                AppConfig(),
                history_path=Path(directory) / "plays.jsonl",
            )
            result = GameSnapshot(
                state=GameState.GOAL,
                play_id=1,
                reason="Cruce completo confirmado",
                state_elapsed=0.0,
                approach_speed=80.0,
                crossed_observations=3,
                waiting_for_removal=False,
            )

            with self.assertLogs("ojo_halcon.service", level="ERROR"):
                with patch.object(
                    runtime.history,
                    "append",
                    side_effect=OSError("disco lleno"),
                ):
                    runtime._record_result(
                        result,
                        "2026-10-11T12:00:00+00:00",
                        now=10.0,
                    )

            self.assertEqual(runtime.get_health().history_error, "disco lleno")
            self.assertNotIn((1, "GOAL"), runtime._recorded_results)


if __name__ == "__main__":
    unittest.main()
