"""Tests for POST /api/jobs/{job_id}/retry."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meetingai_backend.app import create_app
from meetingai_backend.job_state import (
    JOB_STAGE_CHUNKING,
    JOB_STAGE_SUMMARY,
    JOB_STAGE_TRANSCRIPTION,
    JOB_STAGE_UPLOAD,
    load_job_failure,
    mark_job_failed,
    save_job_language,
    save_source_path,
)
from meetingai_backend.jobs import set_job_queue
from meetingai_backend.settings import Settings, set_settings


class _StubQueue:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def enqueue(self, func: str, *args: object, **kwargs: object) -> object:
        self.calls.append({"func": func, "args": args, "kwargs": kwargs})
        return object()


class _FailingQueue:
    def enqueue(self, func: str, *args: object, **kwargs: object) -> object:
        raise RuntimeError("redis is down")


@pytest.fixture
def stub_queue() -> Iterator[_StubQueue]:
    queue = _StubQueue()
    set_job_queue(queue)
    yield queue
    set_job_queue(None)


def _make_settings(upload_root: Path) -> Settings:
    return Settings(
        upload_root=upload_root,
        redis_url="redis://localhost:6379/0",
        job_queue_name="meetingai:jobs",
        job_timeout_seconds=900,
        ffmpeg_path="ffmpeg",
        openai_api_key="test-key",
    )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, Path]]:
    settings = _make_settings(tmp_path)
    set_settings(settings)
    try:
        yield TestClient(create_app()), tmp_path
    finally:
        set_settings(None)


def test_retry_returns_404_when_job_missing(
    client: tuple[TestClient, Path], stub_queue: _StubQueue
) -> None:
    test_client, _ = client
    response = test_client.post("/api/jobs/does-not-exist/retry")
    assert response.status_code == 404
    assert stub_queue.calls == []


def test_retry_returns_409_when_not_failed(
    client: tuple[TestClient, Path], stub_queue: _StubQueue
) -> None:
    test_client, root = client
    (root / "job-ok").mkdir()
    response = test_client.post("/api/jobs/job-ok/retry")
    assert response.status_code == 409
    assert stub_queue.calls == []


def test_retry_transcription_reenqueues_transcribe_task(
    client: tuple[TestClient, Path], stub_queue: _StubQueue
) -> None:
    test_client, root = client
    job_dir = root / "job-trans"
    job_dir.mkdir()
    save_job_language(job_dir, language="ja")
    mark_job_failed(
        job_dir,
        stage=JOB_STAGE_TRANSCRIPTION,
        error=RuntimeError("network error"),
    )

    response = test_client.post("/api/jobs/job-trans/retry")
    assert response.status_code == 202

    assert (job_dir / "job_failed.json").exists() is False
    assert len(stub_queue.calls) == 1
    call = stub_queue.calls[0]
    assert call["func"] == "meetingai_backend.tasks.transcribe.transcribe_audio_for_job"
    job_kwargs = call["kwargs"]["kwargs"]
    assert job_kwargs["job_id"] == "job-trans"
    assert job_kwargs["language"] == "ja"
    assert job_kwargs["job_directory"] == str(job_dir)


def test_retry_summary_reenqueues_summary_task(
    client: tuple[TestClient, Path], stub_queue: _StubQueue
) -> None:
    test_client, root = client
    job_dir = root / "job-sum"
    job_dir.mkdir()
    save_job_language(job_dir, language="en")
    mark_job_failed(
        job_dir,
        stage=JOB_STAGE_SUMMARY,
        error=RuntimeError("rate limited"),
    )

    response = test_client.post("/api/jobs/job-sum/retry")
    assert response.status_code == 202

    assert len(stub_queue.calls) == 1
    call = stub_queue.calls[0]
    assert call["func"] == "meetingai_backend.tasks.summarize.summarize_job"
    job_kwargs = call["kwargs"]["kwargs"]
    assert job_kwargs["job_id"] == "job-sum"
    assert "language" not in job_kwargs


def test_retry_chunking_reenqueues_ingest_task(
    client: tuple[TestClient, Path], stub_queue: _StubQueue
) -> None:
    test_client, root = client
    job_dir = root / "job-chunk"
    job_dir.mkdir()
    source = job_dir / "meeting.mov"
    source.write_bytes(b"\x00\x00")
    save_job_language(job_dir, language="ja")
    save_source_path(job_dir, source_path=source)
    mark_job_failed(
        job_dir,
        stage=JOB_STAGE_CHUNKING,
        error=RuntimeError("ffmpeg failed"),
    )

    response = test_client.post("/api/jobs/job-chunk/retry")
    assert response.status_code == 202

    call = stub_queue.calls[0]
    assert call["func"] == "meetingai_backend.tasks.ingest.process_uploaded_video"
    job_kwargs = call["kwargs"]["kwargs"]
    assert job_kwargs["source_path"].endswith("meeting.mov")
    assert job_kwargs["language"] == "ja"


def test_retry_upload_returns_409_when_source_path_missing(
    client: tuple[TestClient, Path], stub_queue: _StubQueue
) -> None:
    """Legacy job dirs without job_source.json cannot be auto-retried from upload/chunking."""
    test_client, root = client
    job_dir = root / "job-up"
    job_dir.mkdir()
    (job_dir / "meeting.mov").write_bytes(b"\x00\x00")
    save_job_language(job_dir, language="ja")
    mark_job_failed(
        job_dir,
        stage=JOB_STAGE_UPLOAD,
        error=RuntimeError("disk error"),
    )

    response = test_client.post("/api/jobs/job-up/retry")
    assert response.status_code == 409
    assert stub_queue.calls == []
    # The failure marker is restored so the user can still see the original failure.
    assert (job_dir / "job_failed.json").exists()


def test_retry_uses_body_language_when_disk_missing(
    client: tuple[TestClient, Path], stub_queue: _StubQueue
) -> None:
    test_client, root = client
    job_dir = root / "job-old"
    job_dir.mkdir()
    mark_job_failed(
        job_dir,
        stage=JOB_STAGE_TRANSCRIPTION,
        error=RuntimeError("network"),
    )

    response = test_client.post("/api/jobs/job-old/retry", json={"language": "en"})
    assert response.status_code == 202

    call = stub_queue.calls[0]
    job_kwargs = call["kwargs"]["kwargs"]
    assert job_kwargs["language"] == "en"


def test_retry_requires_language_when_disk_missing_and_body_empty(
    client: tuple[TestClient, Path], stub_queue: _StubQueue
) -> None:
    test_client, root = client
    job_dir = root / "job-old"
    job_dir.mkdir()
    mark_job_failed(
        job_dir,
        stage=JOB_STAGE_TRANSCRIPTION,
        error=RuntimeError("network"),
    )

    response = test_client.post("/api/jobs/job-old/retry")
    assert response.status_code == 400
    assert stub_queue.calls == []
    # Failure marker restored so the user can retry with a language.
    assert (job_dir / "job_failed.json").exists()


def test_retry_rejects_invalid_language(
    client: tuple[TestClient, Path], stub_queue: _StubQueue
) -> None:
    test_client, root = client
    job_dir = root / "job-bad-lang"
    job_dir.mkdir()
    save_job_language(job_dir, language="ja")
    mark_job_failed(
        job_dir,
        stage=JOB_STAGE_TRANSCRIPTION,
        error=RuntimeError("net"),
    )

    response = test_client.post("/api/jobs/job-bad-lang/retry", json={"language": "fr"})
    assert response.status_code == 400
    assert stub_queue.calls == []
    # Validation runs before consume_job_failure, so the marker is untouched.
    assert (job_dir / "job_failed.json").exists()


def test_retry_restores_failure_when_enqueue_fails(tmp_path: Path) -> None:
    """If enqueue raises, the failure marker must be restored verbatim."""
    settings = _make_settings(tmp_path)
    set_settings(settings)
    set_job_queue(_FailingQueue())
    try:
        test_client = TestClient(create_app(), raise_server_exceptions=False)

        job_dir = tmp_path / "job-enqueue-fail"
        job_dir.mkdir()
        save_job_language(job_dir, language="ja")
        mark_job_failed(
            job_dir,
            stage=JOB_STAGE_TRANSCRIPTION,
            error=RuntimeError("original network error"),
        )
        original = load_job_failure(job_dir)
        assert original is not None

        response = test_client.post("/api/jobs/job-enqueue-fail/retry")
        assert response.status_code == 500

        restored = load_job_failure(job_dir)
        assert restored is not None
        assert restored.stage == original.stage
        assert restored.message == original.message
        assert restored.occurred_at == original.occurred_at
    finally:
        set_job_queue(None)
        set_settings(None)


def test_concurrent_retry_only_one_proceeds(
    client: tuple[TestClient, Path], stub_queue: _StubQueue
) -> None:
    """Two concurrent retry requests must not both enqueue the same job.

    Simulated by manually invoking consume_job_failure twice before any
    enqueue happens (mirroring the race).
    """
    from meetingai_backend.job_state import consume_job_failure

    test_client, root = client
    job_dir = root / "job-race"
    job_dir.mkdir()
    save_job_language(job_dir, language="ja")
    mark_job_failed(
        job_dir,
        stage=JOB_STAGE_TRANSCRIPTION,
        error=RuntimeError("net"),
    )

    first = consume_job_failure(job_dir)
    second = consume_job_failure(job_dir)
    assert first is not None
    assert second is None

    # Subsequent retry request should see no failure marker → 409.
    response = test_client.post("/api/jobs/job-race/retry")
    assert response.status_code == 409
    assert stub_queue.calls == []
