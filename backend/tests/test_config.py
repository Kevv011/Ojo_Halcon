import json
import tempfile
import unittest
from pathlib import Path

from ojo_halcon.config import AppConfig, ConfigError


class AppConfigTests(unittest.TestCase):
    def test_rejects_invalid_hsv_and_tracking_values(self) -> None:
        config = AppConfig()
        config.ball.hsv_lower = [999, -1, 300]
        config.tracking.smoothing_alpha = 1.5

        with self.assertRaises(ConfigError) as context:
            config.validate()

        self.assertIn("hsv_lower", str(context.exception))
        self.assertIn("smoothing_alpha", str(context.exception))

    def test_rejects_invalid_geometry(self) -> None:
        config = AppConfig(
            goal_line=[[10, 10], [10, 10]],
            goal_side_point=[10, 10],
            roi=[[0, 0], [1, 1], [2, 2]],
        )

        with self.assertRaises(ConfigError) as context:
            config.validate()

        message = str(context.exception)
        self.assertIn("extremos diferentes", message)
        self.assertIn("área válida", message)

    def test_missing_required_file_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with self.assertRaises(ConfigError):
                AppConfig.load(missing, require_exists=True)

    def test_save_is_valid_and_leaves_no_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            config = AppConfig()
            config.save(path)

            restored = AppConfig.load(path, require_exists=True)

            self.assertEqual(restored.camera.width, config.camera.width)
            self.assertFalse(path.with_suffix(".json.tmp").exists())
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
