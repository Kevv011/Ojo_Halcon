import tempfile
import unittest
from pathlib import Path

from ojo_halcon.history import PlayHistory
from ojo_halcon.schemas import PlayRecord


class PlayHistoryTests(unittest.TestCase):
    def test_persists_and_loads_recent_plays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plays.jsonl"
            history = PlayHistory(path)
            history.append(
                PlayRecord(
                    play_id=1,
                    result="GOAL",
                    reason="Cruce completo confirmado",
                    decided_at="2026-10-11T12:00:00+00:00",
                )
            )
            history.append(
                PlayRecord(
                    play_id=2,
                    result="NO GOAL",
                    reason="Balon detenido sin cruzar",
                    decided_at="2026-10-11T12:01:00+00:00",
                )
            )

            restored = PlayHistory(path)

            self.assertEqual(restored.total, 2)
            self.assertEqual(restored.last_play_id, 2)
            self.assertEqual(restored.recent(1)[0].result, "NO GOAL")

    def test_ignores_a_corrupted_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plays.jsonl"
            path.write_text("esto no es json\n", encoding="utf-8")

            history = PlayHistory(path)

            self.assertEqual(history.total, 0)

    def test_caps_memory_and_file_to_max_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plays.jsonl"
            history = PlayHistory(path, max_records=2)
            for play_id in range(1, 4):
                history.append(
                    PlayRecord(
                        play_id=play_id,
                        result="GOAL",
                        reason="Prueba",
                        decided_at=f"2026-10-11T12:0{play_id}:00+00:00",
                    )
                )

            restored = PlayHistory(path, max_records=2)

            self.assertEqual(restored.total, 2)
            self.assertEqual(restored.last_play_id, 3)
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
