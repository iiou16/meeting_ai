"""Tests for RQ worker failure handler."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from meetingai_backend.job_state import (
    JobFailureRecord,
    load_job_failure,
    mark_job_failed,
)
from meetingai_backend.worker import _infer_stage_from_job, _on_job_failure


def _make_mock_job(job_id: str, rq_job_id: str = "rq-123") -> MagicMock:
    """Create a mock RQ Job with the given kwargs."""
    job = MagicMock()
    job.kwargs = {"job_id": job_id}
    job.id = rq_job_id
    return job


class TestOnJobFailure:
    """Tests for _on_job_failure handler."""

    def test_writes_job_failed_json_via_mark_job_failed(self, tmp_path: Path) -> None:
        """_on_job_failure should write job_failed.json (not error.json)
        so that load_job_failure() can find the record."""
        job_dir = tmp_path / "test-job-id"
        job_dir.mkdir()

        mock_job = _make_mock_job("test-job-id")
        exc = RuntimeError("something went wrong")

        with patch("meetingai_backend.worker.get_settings") as mock_settings:
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
        assert record.stage == "upload"  # ジョブ関数名不明の場合デフォルトはupload

    def test_error_json_not_written(self, tmp_path: Path) -> None:
        """_on_job_failure should NOT write error.json (old behavior)."""
        job_dir = tmp_path / "test-job-id"
        job_dir.mkdir()

        mock_job = _make_mock_job("test-job-id")
        exc = ValueError("bad value")

        with patch("meetingai_backend.worker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(upload_root=tmp_path)
            try:
                raise exc
            except ValueError:
                import sys

                tb = sys.exc_info()[2]
                _on_job_failure(mock_job, ValueError, exc, tb)

        assert not (job_dir / "error.json").exists()

    def test_details_contain_traceback_and_rq_job_id(self, tmp_path: Path) -> None:
        """The failure record details should include traceback and rq_job_id."""
        job_dir = tmp_path / "test-job-id"
        job_dir.mkdir()

        mock_job = _make_mock_job("test-job-id", rq_job_id="rq-456")
        exc = TypeError("type error")

        with patch("meetingai_backend.worker.get_settings") as mock_settings:
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

        with patch("meetingai_backend.worker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(upload_root=tmp_path)
            _on_job_failure(job, RuntimeError, RuntimeError("err"), None)

        # No files should be created
        assert list(tmp_path.iterdir()) == []

    def test_missing_job_directory_logs_error(self, tmp_path: Path) -> None:
        """If job directory does not exist, should log error and not crash."""
        mock_job = _make_mock_job("nonexistent-job")

        with patch("meetingai_backend.worker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(upload_root=tmp_path)
            # Should not raise
            _on_job_failure(mock_job, RuntimeError, RuntimeError("err"), None)

        assert not (tmp_path / "nonexistent-job" / "job_failed.json").exists()

    def test_existing_failure_record_preserves_stage_and_adds_details(
        self, tmp_path: Path
    ) -> None:
        """タスク側で既に失敗記録が書かれている場合、ステージとメッセージを
        維持しつつトレースバック等の詳細を追記する。"""
        job_dir = tmp_path / "test-job-id"
        job_dir.mkdir()

        # タスク側で先に失敗記録を書く（detailsなし）
        mark_job_failed(job_dir, stage="transcription", error="original error")

        mock_job = _make_mock_job("test-job-id", rq_job_id="rq-789")
        mock_job.func_name = (
            "meetingai_backend.tasks.transcribe.transcribe_audio_for_job"
        )
        exc = RuntimeError("worker-level error")

        with patch("meetingai_backend.worker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(upload_root=tmp_path)
            try:
                raise exc
            except RuntimeError:
                import sys

                tb = sys.exc_info()[2]
                _on_job_failure(mock_job, RuntimeError, exc, tb)

        # ステージとメッセージはタスク側の記録が保持されること
        record = load_job_failure(job_dir)
        assert record is not None
        assert record.stage == "transcription"
        assert "original error" in record.message

        # トレースバック等の詳細が追記されていること
        assert record.details["rq_job_id"] == "rq-789"
        assert "traceback" in record.details
        assert any("worker-level error" in line for line in record.details["traceback"])


class TestInferStageFromJob:
    """_infer_stage_from_job のステージ推定テスト。"""

    def test_ingest_function_returns_upload_stage(self) -> None:
        job = MagicMock()
        job.func_name = "meetingai_backend.tasks.ingest.process_uploaded_video"
        assert _infer_stage_from_job(job) == "upload"

    def test_transcribe_function_returns_transcription_stage(self) -> None:
        job = MagicMock()
        job.func_name = "meetingai_backend.tasks.transcribe.transcribe_audio_for_job"
        assert _infer_stage_from_job(job) == "transcription"

    def test_summarize_function_returns_summary_stage(self) -> None:
        job = MagicMock()
        job.func_name = "meetingai_backend.tasks.summarize.summarize_job"
        assert _infer_stage_from_job(job) == "summary"

    def test_summarize_transcript_function_returns_summary_stage(self) -> None:
        job = MagicMock()
        job.func_name = "meetingai_backend.tasks.summarize.summarize_transcript_for_job"
        assert _infer_stage_from_job(job) == "summary"

    def test_unknown_function_defaults_to_upload_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """未知のジョブ関数名の場合、upload をデフォルトとし警告ログを出力する。"""
        job = MagicMock()
        job.func_name = "some.module.unknown_function"
        with caplog.at_level("WARNING"):
            result = _infer_stage_from_job(job)
        assert result == "upload"
        assert any("Unknown job function" in r.message for r in caplog.records)
        assert any("unknown_function" in r.message for r in caplog.records)

    def test_empty_func_name_defaults_to_upload_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """func_name が空文字列の場合も upload をデフォルトとし警告ログを出力する。"""
        job = MagicMock()
        job.func_name = ""
        with caplog.at_level("WARNING"):
            result = _infer_stage_from_job(job)
        assert result == "upload"
        assert any("Unknown job function" in r.message for r in caplog.records)
