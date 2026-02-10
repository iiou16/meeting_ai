"""Tests for RQ worker failure handler."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from meetingai_backend.job_state import JobFailureRecord, load_job_failure
from meetingai_backend.worker import _on_job_failure


def _make_mock_job(job_id: str, rq_job_id: str = "rq-123") -> MagicMock:
    """Create a mock RQ Job with the given kwargs."""
    job = MagicMock()
    job.kwargs = {"job_id": job_id}
    job.id = rq_job_id
    return job


class TestOnJobFailure:
    """Tests for _on_job_failure handler."""

    def test_writes_job_failed_json_via_mark_job_failed(
        self, tmp_path: Path
    ) -> None:
        """_on_job_failure should write job_failed.json (not error.json)
        so that load_job_failure() can find the record."""
        job_dir = tmp_path / "test-job-id"
        job_dir.mkdir()

        mock_job = _make_mock_job("test-job-id")
        exc = RuntimeError("something went wrong")

        with patch(
            "meetingai_backend.worker.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(upload_root=tmp_path)
            try:
                raise exc
            except RuntimeError:
                import sys

                tb = sys.exc_info()[2]
                _on_job_failure(mock_job, RuntimeError, exc, tb)

        # job_failed.json should exist (used by load_job_failure)
        assert (job_dir / "job_failed.json").exists()

        # load_job_failure should be able to read the record
        record = load_job_failure(job_dir)
        assert record is not None
        assert isinstance(record, JobFailureRecord)
        assert "something went wrong" in record.message
        assert record.stage == "rq_worker"

    def test_error_json_not_written(self, tmp_path: Path) -> None:
        """_on_job_failure should NOT write error.json (old behavior)."""
        job_dir = tmp_path / "test-job-id"
        job_dir.mkdir()

        mock_job = _make_mock_job("test-job-id")
        exc = ValueError("bad value")

        with patch(
            "meetingai_backend.worker.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(upload_root=tmp_path)
            try:
                raise exc
            except ValueError:
                import sys

                tb = sys.exc_info()[2]
                _on_job_failure(mock_job, ValueError, exc, tb)

        assert not (job_dir / "error.json").exists()

    def test_details_contain_traceback_and_rq_job_id(
        self, tmp_path: Path
    ) -> None:
        """The failure record details should include traceback and rq_job_id."""
        job_dir = tmp_path / "test-job-id"
        job_dir.mkdir()

        mock_job = _make_mock_job("test-job-id", rq_job_id="rq-456")
        exc = TypeError("type error")

        with patch(
            "meetingai_backend.worker.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(upload_root=tmp_path)
            try:
                raise exc
            except TypeError:
                import sys

                tb = sys.exc_info()[2]
                _on_job_failure(mock_job, TypeError, exc, tb)

        record = load_job_failure(job_dir)
        assert record is not None
        assert "rq_job_id" in record.details
        assert record.details["rq_job_id"] == "rq-456"
        assert "traceback" in record.details

    def test_no_kwargs_logs_error_and_returns(self, tmp_path: Path) -> None:
        """If job has no kwargs, _on_job_failure should log and return
        without writing any file."""
        job = MagicMock()
        job.kwargs = None

        with patch(
            "meetingai_backend.worker.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(upload_root=tmp_path)
            _on_job_failure(job, RuntimeError, RuntimeError("err"), None)

        # No files should be created
        assert list(tmp_path.iterdir()) == []

    def test_missing_job_directory_logs_error(self, tmp_path: Path) -> None:
        """If job directory does not exist, should log error and not crash."""
        mock_job = _make_mock_job("nonexistent-job")

        with patch(
            "meetingai_backend.worker.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(upload_root=tmp_path)
            # Should not raise
            _on_job_failure(
                mock_job, RuntimeError, RuntimeError("err"), None
            )

        assert not (tmp_path / "nonexistent-job" / "job_failed.json").exists()
