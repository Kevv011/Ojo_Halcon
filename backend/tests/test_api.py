import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from ojo_halcon.api import create_app
from ojo_halcon.config import AppConfig
from ojo_halcon.schemas import PlayRecord
from ojo_halcon.service import VisionRuntime


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        history_path = Path(self.temporary_directory.name) / "plays.jsonl"
        self.runtime = VisionRuntime(AppConfig(), history_path=history_path)
        self.runtime.history.append(
            PlayRecord(
                play_id=1,
                result="GOAL",
                reason="Cruce completo confirmado",
                decided_at="2026-10-11T12:00:00+00:00",
            )
        )
        self.app = create_app(self.runtime, start_runtime=False)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_http_contract_without_opening_camera(self) -> None:
        with TestClient(self.app) as client:
            self.assertEqual(client.get("/").status_code, 200)

            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "degraded")
            self.assertFalse(health.json()["calibration_ready"])

            state = client.get("/api/state")
            self.assertEqual(state.status_code, 200)
            self.assertEqual(state.json()["type"], "state")

            plays = client.get("/api/plays?limit=1")
            self.assertEqual(plays.status_code, 200)
            self.assertEqual(plays.json()["total"], 1)
            self.assertEqual(plays.json()["plays"][0]["result"], "GOAL")

            config = client.get("/api/config")
            self.assertEqual(config.status_code, 200)
            self.assertIn("camera", config.json())

            self.assertEqual(client.get("/api/snapshot.jpg").status_code, 503)

            reset = client.post("/api/reset")
            self.assertEqual(reset.status_code, 202)
            self.assertTrue(self.runtime.reset_pending)

    def test_snapshot_returns_latest_jpeg(self) -> None:
        self.runtime._latest_jpeg = b"\xff\xd8test\xff\xd9"
        with TestClient(self.app) as client:
            response = client.get("/api/snapshot.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertEqual(response.content, b"\xff\xd8test\xff\xd9")

    def test_result_snapshot_is_bound_to_play_id(self) -> None:
        self.runtime._result_jpegs[4] = b"\xff\xd8result\xff\xd9"
        with TestClient(self.app) as client:
            found = client.get("/api/result-snapshot.jpg?play_id=4")
            missing = client.get("/api/result-snapshot.jpg?play_id=5")

        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.content, b"\xff\xd8result\xff\xd9")
        self.assertEqual(missing.status_code, 404)

    def test_websocket_sends_initial_and_live_state(self) -> None:
        with TestClient(self.app) as client:
            with client.websocket_connect("/ws") as websocket:
                initial = websocket.receive_json()
                self.assertEqual(initial["type"], "state")

                self.runtime.broadcaster.publish(self.runtime.get_state())
                update = websocket.receive_json()
                self.assertEqual(update["game"]["state"], "ESPERANDO JUGADA")

    def test_websocket_broadcast_reaches_multiple_clients(self) -> None:
        with TestClient(self.app) as client:
            with client.websocket_connect("/ws") as first:
                with client.websocket_connect("/ws") as second:
                    first.receive_json()
                    second.receive_json()
                    self.runtime.broadcaster.publish(self.runtime.get_state())

                    self.assertEqual(first.receive_json()["schema_version"], "1.0")
                    self.assertEqual(second.receive_json()["schema_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
