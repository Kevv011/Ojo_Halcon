import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from ojo_halcon.calibration import CalibrationManager
from ojo_halcon.config import AppConfig


class FinishedProcess:
    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0


class CalibrationManagerTests(unittest.TestCase):
    def test_reloads_config_and_restarts_runtime_after_calibrator_closes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "default.json"
            AppConfig().save(config_path)
            runtime = Mock()
            runtime.camera_index = 1
            runtime.stop.return_value = True
            commands = []

            def process_factory(command, **_kwargs):
                commands.append(command)
                return FinishedProcess()

            manager = CalibrationManager(runtime, config_path, process_factory)

            accepted = manager.start()
            deadline = time.perf_counter() + 2
            while manager.get_status().active and time.perf_counter() < deadline:
                time.sleep(0.01)

            status = manager.get_status()
            self.assertEqual(accepted.status, "stopping")
            self.assertEqual(status.status, "idle")
            runtime.stop.assert_called_once()
            runtime.enter_calibration_mode.assert_called_once()
            runtime.replace_config.assert_called_once()
            runtime.start.assert_called_once()
            self.assertIn("ojo_halcon", commands[0])


if __name__ == "__main__":
    unittest.main()
