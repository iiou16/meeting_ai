"""Chunk-level progress tracking for transcription jobs."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROGRESS_FILENAME = "transcription_progress.json"


@dataclass(slots=True)
class TranscriptionProgress:
    """Snapshot of transcription progress for a single job."""

    chunks_total: int
    chunks_completed: int
    started_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunks_total": self.chunks_total,
            "chunks_completed": self.chunks_completed,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TranscriptionProgress:
        started_at_raw = payload["started_at"]
        if not isinstance(started_at_raw, str):
            raise TypeError(
                f"started_at must be a string, got {type(started_at_raw).__name__}"
            )
        updated_at_raw = payload["updated_at"]
        if not isinstance(updated_at_raw, str):
            raise TypeError(
                f"updated_at must be a string, got {type(updated_at_raw).__name__}"
            )
        return cls(
            chunks_total=int(payload["chunks_total"]),
            chunks_completed=int(payload["chunks_completed"]),
            started_at=datetime.fromisoformat(started_at_raw),
            updated_at=datetime.fromisoformat(updated_at_raw),
        )


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically using tmp file + os.replace."""
    content = json.dumps(data, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".progress_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError as cleanup_err:
            logger.warning("Failed to remove temp file %s: %s", tmp_path, cleanup_err)
        raise


class ProgressTracker:
    """Tracks chunk-level transcription progress, persisted as JSON."""

    def __init__(self, job_directory: Path, chunks_total: int) -> None:
        if chunks_total < 1:
            raise ValueError(f"chunks_total must be at least 1, got {chunks_total}")
        self._job_directory = job_directory
        self._chunks_total = chunks_total
        self._chunks_completed = 0
        self._lock = threading.Lock()
        self._path = job_directory / _PROGRESS_FILENAME

    def initialize(self) -> None:
        """Create (or overwrite) the progress file with chunks_completed=0."""
        now = datetime.now(timezone.utc)
        record = TranscriptionProgress(
            chunks_total=self._chunks_total,
            chunks_completed=0,
            started_at=now,
            updated_at=now,
        )
        _atomic_write_json(self._path, record.to_dict())

    def update(self, chunks_completed: int) -> None:
        """Update the progress file with the given completed count."""
        if chunks_completed < 0 or chunks_completed > self._chunks_total:
            raise ValueError(
                f"chunks_completed must be between 0 and {self._chunks_total}, "
                f"got {chunks_completed}"
            )
        with self._lock:
            self._chunks_completed = chunks_completed
            now = datetime.now(timezone.utc)
            record = TranscriptionProgress(
                chunks_total=self._chunks_total,
                chunks_completed=self._chunks_completed,
                started_at=self._read_started_at(),
                updated_at=now,
            )
            _atomic_write_json(self._path, record.to_dict())

    def _read_started_at(self) -> datetime:
        """Read started_at from the existing progress file."""
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        try:
            raw = payload["started_at"]
        except KeyError:
            raise KeyError(f"'started_at' not found in progress file {self._path}")
        return datetime.fromisoformat(raw)


def load_transcription_progress(
    job_directory: Path,
) -> TranscriptionProgress | None:
    """Load transcription progress from disk. Returns None only if file does not exist."""
    path = job_directory / _PROGRESS_FILENAME
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(
            f"Transcription progress at {path} is not a dict, got {type(payload).__name__}"
        )
    return TranscriptionProgress.from_dict(payload)


__all__ = [
    "TranscriptionProgress",
    "ProgressTracker",
    "load_transcription_progress",
]
