"""Tests for job_state module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meetingai_backend.job_state import JobFailureRecord, load_job_failure


class TestJobFailureRecordFromDict:
    """Tests for JobFailureRecord.from_dict()."""

    def test_full_payload(self) -> None:
        """All fields present — should parse correctly."""
        payload = {
            "stage": "rq_worker",
            "message": "connection refused",
            "occurred_at": "2025-06-01T12:00:00+00:00",
            "details": {"rq_job_id": "abc"},
        }
        record = JobFailureRecord.from_dict(payload)
        assert record.stage == "rq_worker"
        assert record.message == "connection refused"
        assert record.details == {"rq_job_id": "abc"}

    def test_payload_without_details_key(self) -> None:
        """Old-format records without 'details' should parse
        with details defaulting to empty dict.

        旧バージョンの to_dict() は details が空の場合キーを
        出力しなかったため、ディスク上に details なしの
        job_failed.json が存在し得る。
        """
        payload = {
            "stage": "upload",
            "message": "something failed",
            "occurred_at": "2025-06-01T12:00:00+00:00",
        }
        record = JobFailureRecord.from_dict(payload)
        assert record.stage == "upload"
        assert record.message == "something failed"
        assert record.details == {}

    def test_missing_required_field_raises(self) -> None:
        """Missing truly required fields (stage, message, occurred_at)
        should raise KeyError."""
        payload = {"stage": "upload"}
        with pytest.raises(KeyError):
            JobFailureRecord.from_dict(payload)


class TestLoadJobFailureBackwardsCompat:
    """Test that load_job_failure handles old-format files on disk."""

    def test_old_format_without_details(self, tmp_path: Path) -> None:
        """A job_failed.json without 'details' key (written by old code)
        should load successfully via load_job_failure."""
        old_payload = {
            "stage": "chunking",
            "message": "FFmpeg not found",
            "occurred_at": "2025-05-20T08:30:00+00:00",
        }
        (tmp_path / "job_failed.json").write_text(
            json.dumps(old_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        record = load_job_failure(tmp_path)
        assert record is not None
        assert record.stage == "chunking"
        assert record.message == "FFmpeg not found"
        assert record.details == {}

    def test_current_format_with_details(self, tmp_path: Path) -> None:
        """A job_failed.json with 'details' key should load normally."""
        payload = {
            "stage": "rq_worker",
            "message": "timeout",
            "occurred_at": "2025-06-01T12:00:00+00:00",
            "details": {"rq_job_id": "xyz"},
        }
        (tmp_path / "job_failed.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        record = load_job_failure(tmp_path)
        assert record is not None
        assert record.details == {"rq_job_id": "xyz"}
