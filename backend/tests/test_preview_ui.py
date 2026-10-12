import unittest

import cv2

from ojo_halcon.config import AppConfig
from ojo_halcon.preview import CalibrationUI, MENU_MESSAGE, _wrap_text_lines


class CalibrationUITests(unittest.TestCase):
    def test_temporary_message_returns_to_menu_after_four_seconds(self) -> None:
        ui = CalibrationUI(AppConfig())
        ui.set_message("Mensaje temporal", now=10.0)

        self.assertEqual(ui.visible_message(now=13.99), "Mensaje temporal")
        self.assertEqual(ui.visible_message(now=14.0), MENU_MESSAGE)

    def test_long_panel_message_is_split_to_available_width(self) -> None:
        max_width = 180
        lines = _wrap_text_lines(
            "Esperando que el balon se aproxime desde el exterior",
            max_width,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            1,
        )

        self.assertGreater(len(lines), 1)
        for line in lines:
            width = cv2.getTextSize(
                line, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1
            )[0][0]
            self.assertLessEqual(width, max_width)


if __name__ == "__main__":
    unittest.main()
