"""Tests for the transcription progress tracking module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meetingai_backend.transcription.progress import (
    ProgressTracker,
    TranscriptionProgress,
    load_transcription_progress,
)

_PROGRESS_FILENAME = "transcription_progress.json"


class TestTranscriptionProgressRoundtrip:
    """TranscriptionProgress.to_dict() / from_dict() round-trip."""

    def test_round_trip(self) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        original = TranscriptionProgress(
            chunks_total=9,
            chunks_completed=3,
            started_at=now,
            updated_at=now,
        )
        payload = original.to_dict()
        restored = TranscriptionProgress.from_dict(payload)
        assert restored.chunks_total == original.chunks_total
        assert restored.chunks_completed == original.chunks_completed
        assert restored.started_at == original.started_at
        assert restored.updated_at == original.updated_at

    def test_from_dict_missing_key(self) -> None:
        with pytest.raises(KeyError):
            TranscriptionProgress.from_dict({"chunks_total": 5})

    def test_from_dict_invalid_type(self) -> None:
        with pytest.raises(TypeError):
            TranscriptionProgress.from_dict(
                {
                    "chunks_total": 5,
                    "chunks_completed": 0,
                    "started_at": 12345,
                    "updated_at": "2025-01-01T00:00:00+00:00",
                }
            )


class TestProgressTracker:
    """ProgressTracker initialize / update cycle."""

    def test_initialize_creates_file(self, tmp_path: Path) -> None:
        tracker = ProgressTracker(tmp_path, chunks_total=5)
        tracker.initialize()

        path = tmp_path / _PROGRESS_FILENAME
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["chunks_total"] == 5
        assert data["chunks_completed"] == 0

    def test_update_increments(self, tmp_path: Path) -> None:
        tracker = ProgressTracker(tmp_path, chunks_total=3)
        tracker.initialize()

        tracker.update(1)
        data = json.loads((tmp_path / _PROGRESS_FILENAME).read_text(encoding="utf-8"))
        assert data["chunks_completed"] == 1

        tracker.update(2)
        data = json.loads((tmp_path / _PROGRESS_FILENAME).read_text(encoding="utf-8"))
        assert data["chunks_completed"] == 2

        tracker.update(3)
        data = json.loads((tmp_path / _PROGRESS_FILENAME).read_text(encoding="utf-8"))
        assert data["chunks_completed"] == 3

    def test_invalid_chunks_total(self) -> None:
        with pytest.raises(ValueError, match="chunks_total must be at least 1"):
            ProgressTracker(Path("/tmp"), chunks_total=0)

    def test_initialize_overwrites_existing(self, tmp_path: Path) -> None:
        """Re-initialization should reset progress to 0."""
        tracker = ProgressTracker(tmp_path, chunks_total=5)
        tracker.initialize()
        tracker.update(3)

        tracker2 = ProgressTracker(tmp_path, chunks_total=5)
        tracker2.initialize()
        data = json.loads((tmp_path / _PROGRESS_FILENAME).read_text(encoding="utf-8"))
        assert data["chunks_completed"] == 0


class TestLoadTranscriptionProgress:
    """load_transcription_progress() edge cases."""

    def test_file_missing(self, tmp_path: Path) -> None:
        assert load_transcription_progress(tmp_path) is None

    def test_valid_file(self, tmp_path: Path) -> None:
        tracker = ProgressTracker(tmp_path, chunks_total=9)
        tracker.initialize()
        tracker.update(4)

        record = load_transcription_progress(tmp_path)
        assert record is not None
        assert record.chunks_total == 9
        assert record.chunks_completed == 4

    def test_corrupted_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / _PROGRESS_FILENAME
        path.write_text("{invalid json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_transcription_progress(tmp_path)

    def test_invalid_structure_raises(self, tmp_path: Path) -> None:
        path = tmp_path / _PROGRESS_FILENAME
        path.write_text(json.dumps({"chunks_total": 5}), encoding="utf-8")

        with pytest.raises(KeyError):
            load_transcription_progress(tmp_path)

    def test_not_a_dict_raises(self, tmp_path: Path) -> None:
        path = tmp_path / _PROGRESS_FILENAME
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

        with pytest.raises(TypeError, match="not a dict"):
            load_transcription_progress(tmp_path)
