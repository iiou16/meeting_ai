"""Job queue helpers for video processing tasks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from redis import Redis
from rq import Queue

from .settings import Settings

_JOB_QUEUE: JobQueueProtocol | None = None


class JobQueueProtocol(Protocol):
    """Protocol describing the methods used for enqueuing work."""

    def enqueue(
        self, func: str, *args: Any, **kwargs: Any
    ) -> Any:  # pragma: no cover - Protocol stub
        ...


@dataclass(slots=True)
class RedisJobQueue:
    """Thin wrapper around RQ's Queue with configuration helpers."""

    queue: Queue

    @classmethod
    def from_settings(cls, settings: Settings) -> "RedisJobQueue":
        connection = Redis.from_url(settings.redis_url)
        queue = Queue(
            settings.job_queue_name,
            connection=connection,
            default_timeout=settings.job_timeout_seconds,
        )
        return cls(queue=queue)

    def enqueue(self, func: str, *args: Any, **kwargs: Any) -> Any:
        return self.queue.enqueue(func, *args, **kwargs)


def get_job_queue(settings: Settings) -> JobQueueProtocol:
    """Return a cached job queue instance built from the provided settings."""
    global _JOB_QUEUE

    if _JOB_QUEUE is None:
        _JOB_QUEUE = RedisJobQueue.from_settings(settings)

    return _JOB_QUEUE


def set_job_queue(queue: JobQueueProtocol | None) -> None:
    """Override the cached queue instance, mainly for testing."""
    global _JOB_QUEUE
    _JOB_QUEUE = queue


def enqueue_video_ingest_job(
    *,
    queue: JobQueueProtocol,
    job_id: str,
    source_path: str,
) -> Any:
    """Schedule the initial video processing task."""
    return queue.enqueue(
        "meetingai_backend.tasks.ingest.process_uploaded_video",
        kwargs={"job_id": job_id, "source_path": source_path},
    )


def enqueue_transcription_job(
    *,
    queue: JobQueueProtocol,
    job_id: str,
    job_directory: str,
    language: str | None = None,
    prompt: str | None = None,
) -> Any:
    """Schedule transcription of prepared audio chunks for a job."""
    kwargs = {"job_id": job_id, "job_directory": job_directory}
    if language is not None:
        kwargs["language"] = language
    if prompt is not None:
        kwargs["prompt"] = prompt

    return queue.enqueue(
        "meetingai_backend.tasks.transcribe.transcribe_audio_for_job",
        kwargs=kwargs,
    )


__all__ = [
    "JobQueueProtocol",
    "RedisJobQueue",
    "enqueue_transcription_job",
    "enqueue_video_ingest_job",
    "get_job_queue",
    "set_job_queue",
]
