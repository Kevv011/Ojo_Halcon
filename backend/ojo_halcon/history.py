from __future__ import annotations

import threading
from pathlib import Path

from .schemas import PlayRecord


class PlayHistory:
    """Historial JSONL sencillo y persistente de decisiones finales."""

    def __init__(self, path: Path, max_records: int = 500) -> None:
        self.path = path
        self.max_records = max(1, max_records)
        self._lock = threading.Lock()
        self._records = self._load()
        line_count = (
            len(self.path.read_text(encoding="utf-8").splitlines())
            if self.path.exists()
            else 0
        )
        if line_count > len(self._records):
            self._write_atomic(self._records)

    def _load(self) -> list[PlayRecord]:
        if not self.path.exists():
            return []
        records: list[PlayRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(PlayRecord.model_validate_json(line))
            except ValueError:
                # Una línea dañada no impide recuperar el resto del historial.
                continue
        return records[-self.max_records :]

    @property
    def last_play_id(self) -> int:
        with self._lock:
            return max((record.play_id for record in self._records), default=0)

    @property
    def total(self) -> int:
        with self._lock:
            return len(self._records)

    def append(self, record: PlayRecord) -> None:
        with self._lock:
            records = (self._records + [record])[-self.max_records :]
            self._write_atomic(records)
            self._records = records

    def recent(self, limit: int = 20) -> list[PlayRecord]:
        safe_limit = max(1, min(limit, self.max_records))
        with self._lock:
            return list(reversed(self._records[-safe_limit:]))

    def _write_atomic(self, records: list[PlayRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            contents = "".join(record.model_dump_json() + "\n" for record in records)
            temporary.write_text(contents, encoding="utf-8")
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
