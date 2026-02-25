"""Tests for meetingai_backend.jobs module."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from meetingai_backend.jobs import (
    RedisJobQueue,
    enqueue_summary_job,
    enqueue_transcription_job,
    enqueue_video_ingest_job,
    get_job_queue,
    set_job_queue,
)
from meetingai_backend.settings import Settings


@dataclass
class _RecordingQueue:
    """Stub that records enqueue calls for assertion."""

    calls: list[tuple[str, tuple, dict]] = field(default_factory=list)

    def enqueue(self, func: str, *args: Any, **kwargs: Any) -> str:
        self.calls.append((func, args, kwargs))
        return "fake-rq-job-id"


@pytest.fixture(autouse=True)
def _reset_job_queue() -> Iterator[None]:
    set_job_queue(None)
    yield
    set_job_queue(None)


# ---------- TestEnqueueVideoIngestJob ----------


class TestEnqueueVideoIngestJob:
    def test_delegates_to_queue_enqueue(self) -> None:
        q = _RecordingQueue()
        enqueue_video_ingest_job(queue=q, job_id="j1", source_path="/tmp/v.mp4")
        assert len(q.calls) == 1

    def test_passes_correct_func_path(self) -> None:
        q = _RecordingQueue()
        enqueue_video_ingest_job(queue=q, job_id="j1", source_path="/tmp/v.mp4")
        func_path = q.calls[0][0]
        assert func_path == "meetingai_backend.tasks.ingest.process_uploaded_video"

    def test_kwargs_exact_match(self) -> None:
        q = _RecordingQueue()
        enqueue_video_ingest_job(queue=q, job_id="j1", source_path="/tmp/v.mp4")
        positional_args = q.calls[0][1]
        kwargs = q.calls[0][2]
        assert positional_args == ()
        assert kwargs == {
            "kwargs": {"job_id": "j1", "source_path": "/tmp/v.mp4", "language": "ja"}
        }

    def test_language_included_in_kwargs(self) -> None:
        q = _RecordingQueue()
        enqueue_video_ingest_job(
            queue=q, job_id="j1", source_path="/tmp/v.mp4", language="en"
        )
        kwargs = q.calls[0][2]["kwargs"]
        assert kwargs["language"] == "en"

    def test_language_defaults_to_ja(self) -> None:
        q = _RecordingQueue()
        enqueue_video_ingest_job(queue=q, job_id="j1", source_path="/tmp/v.mp4")
        kwargs = q.calls[0][2]["kwargs"]
        assert kwargs["language"] == "ja"

    def test_returns_enqueue_result(self) -> None:
        q = _RecordingQueue()
        result = enqueue_video_ingest_job(
            queue=q, job_id="j1", source_path="/tmp/v.mp4"
        )
        assert result == "fake-rq-job-id"


# ---------- TestEnqueueTranscriptionJob ----------


class TestEnqueueTranscriptionJob:
    def test_passes_correct_func_path(self) -> None:
        q = _RecordingQueue()
        enqueue_transcription_job(queue=q, job_id="j1", job_directory="/tmp/j1")
        func_path = q.calls[0][0]
        assert (
            func_path == "meetingai_backend.tasks.transcribe.transcribe_audio_for_job"
        )

    def test_kwargs_exact_match_required_only(self) -> None:
        q = _RecordingQueue()
        enqueue_transcription_job(queue=q, job_id="j1", job_directory="/tmp/j1")
        positional_args = q.calls[0][1]
        kwargs = q.calls[0][2]
        assert positional_args == ()
        assert kwargs == {"kwargs": {"job_id": "j1", "job_directory": "/tmp/j1"}}

    def test_optional_language_included_when_provided(self) -> None:
        q = _RecordingQueue()
        enqueue_transcription_job(
            queue=q, job_id="j1", job_directory="/tmp/j1", language="ja"
        )
        kwargs = q.calls[0][2]["kwargs"]
        assert kwargs["language"] == "ja"

    def test_optional_language_excluded_when_none(self) -> None:
        q = _RecordingQueue()
        enqueue_transcription_job(
            queue=q, job_id="j1", job_directory="/tmp/j1", language=None
        )
        kwargs = q.calls[0][2]["kwargs"]
        assert "language" not in kwargs

    def test_optional_prompt_included_when_provided(self) -> None:
        q = _RecordingQueue()
        enqueue_transcription_job(
            queue=q, job_id="j1", job_directory="/tmp/j1", prompt="meeting context"
        )
        kwargs = q.calls[0][2]["kwargs"]
        assert kwargs["prompt"] == "meeting context"

    def test_optional_prompt_excluded_when_none(self) -> None:
        q = _RecordingQueue()
        enqueue_transcription_job(
            queue=q, job_id="j1", job_directory="/tmp/j1", prompt=None
        )
        kwargs = q.calls[0][2]["kwargs"]
        assert "prompt" not in kwargs

    def test_returns_enqueue_result(self) -> None:
        q = _RecordingQueue()
        result = enqueue_transcription_job(
            queue=q, job_id="j1", job_directory="/tmp/j1"
        )
        assert result == "fake-rq-job-id"


# ---------- TestEnqueueSummaryJob ----------


class TestEnqueueSummaryJob:
    def test_passes_correct_func_path(self) -> None:
        q = _RecordingQueue()
        enqueue_summary_job(queue=q, job_id="j1", job_directory="/tmp/j1")
        func_path = q.calls[0][0]
        assert func_path == "meetingai_backend.tasks.summarize.summarize_job"

    def test_kwargs_exact_match(self) -> None:
        q = _RecordingQueue()
        enqueue_summary_job(queue=q, job_id="j1", job_directory="/tmp/j1")
        positional_args = q.calls[0][1]
        kwargs = q.calls[0][2]
        assert positional_args == ()
        assert kwargs == {"kwargs": {"job_id": "j1", "job_directory": "/tmp/j1"}}

    def test_returns_enqueue_result(self) -> None:
        q = _RecordingQueue()
        result = enqueue_summary_job(queue=q, job_id="j1", job_directory="/tmp/j1")
        assert result == "fake-rq-job-id"


# ---------- TestGetSetJobQueue ----------


class TestGetSetJobQueue:
    def test_set_and_get_returns_injected_queue(self) -> None:
        q = _RecordingQueue()
        set_job_queue(q)
        settings = MagicMock(spec=Settings)
        result = get_job_queue(settings)
        assert result is q

    @patch("meetingai_backend.jobs.RedisJobQueue.from_settings")
    def test_get_builds_from_settings_on_first_call(
        self, mock_from_settings: MagicMock
    ) -> None:
        mock_queue = MagicMock()
        mock_from_settings.return_value = mock_queue
        settings = MagicMock(spec=Settings)

        result = get_job_queue(settings)
        assert result is mock_queue
        mock_from_settings.assert_called_once_with(settings)

    @patch("meetingai_backend.jobs.RedisJobQueue.from_settings")
    def test_get_caches_and_reuses_on_second_call(
        self, mock_from_settings: MagicMock
    ) -> None:
        mock_queue = MagicMock()
        mock_from_settings.return_value = mock_queue
        settings = MagicMock(spec=Settings)

        first = get_job_queue(settings)
        second = get_job_queue(settings)
        assert first is second
        mock_from_settings.assert_called_once()

    @patch("meetingai_backend.jobs.RedisJobQueue.from_settings")
    def test_set_none_clears_cache_and_rebuilds(
        self, mock_from_settings: MagicMock
    ) -> None:
        mock_queue_1 = MagicMock()
        mock_queue_2 = MagicMock()
        mock_from_settings.side_effect = [mock_queue_1, mock_queue_2]
        settings = MagicMock(spec=Settings)

        first = get_job_queue(settings)
        set_job_queue(None)
        second = get_job_queue(settings)

        assert first is mock_queue_1
        assert second is mock_queue_2
        assert mock_from_settings.call_count == 2


# ---------- TestRedisJobQueueFromSettings ----------


class TestRedisJobQueueFromSettings:
    @patch("meetingai_backend.jobs.Queue")
    @patch("meetingai_backend.jobs.Redis")
    def test_from_settings_creates_queue_with_correct_params(
        self, mock_redis_cls: MagicMock, mock_queue_cls: MagicMock
    ) -> None:
        settings = MagicMock(spec=Settings)
        settings.redis_url = "redis://localhost:6379/0"
        settings.job_queue_name = "meetingai:jobs"
        settings.job_timeout_seconds = 900

        mock_conn = MagicMock()
        mock_redis_cls.from_url.return_value = mock_conn

        rjq = RedisJobQueue.from_settings(settings)

        mock_redis_cls.from_url.assert_called_once_with("redis://localhost:6379/0")
        mock_queue_cls.assert_called_once_with(
            "meetingai:jobs",
            connection=mock_conn,
            default_timeout=900,
        )
        assert rjq.queue is mock_queue_cls.return_value

    def test_enqueue_delegates_to_rq_queue(self) -> None:
        mock_queue = MagicMock()
        rjq = RedisJobQueue(queue=mock_queue)
        rjq.enqueue("some.func", kwargs={"key": "val"})
        mock_queue.enqueue.assert_called_once_with("some.func", kwargs={"key": "val"})

    def test_enqueue_returns_rq_queue_return_value(self) -> None:
        mock_queue = MagicMock()
        sentinel = object()
        mock_queue.enqueue.return_value = sentinel
        rjq = RedisJobQueue(queue=mock_queue)
        result = rjq.enqueue("some.func", kwargs={"k": "v"})
        assert result is sentinel


class TestEnqueueTranscriptionJobEmptyStrings:
    def test_empty_string_language_included_in_kwargs(self) -> None:
        q = _RecordingQueue()
        enqueue_transcription_job(
            queue=q, job_id="j1", job_directory="/tmp/j1", language=""
        )
        kwargs = q.calls[0][2]["kwargs"]
        assert kwargs["language"] == ""

    def test_empty_string_prompt_included_in_kwargs(self) -> None:
        q = _RecordingQueue()
        enqueue_transcription_job(
            queue=q, job_id="j1", job_directory="/tmp/j1", prompt=""
        )
        kwargs = q.calls[0][2]["kwargs"]
        assert kwargs["prompt"] == ""


class TestGetJobQueueInitFailure:
    @patch("meetingai_backend.jobs.RedisJobQueue.from_settings")
    def test_from_settings_exception_does_not_corrupt_cache(
        self, mock_from_settings: MagicMock
    ) -> None:
        mock_from_settings.side_effect = ConnectionError("Redis down")
        settings = MagicMock(spec=Settings)

        with pytest.raises(ConnectionError):
            get_job_queue(settings)

        # Cache should remain empty; next call rebuilds
        mock_from_settings.side_effect = None
        mock_from_settings.return_value = MagicMock()
        result = get_job_queue(settings)
        assert result is mock_from_settings.return_value
