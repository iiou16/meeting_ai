from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from meetingai_backend.app import create_app
from meetingai_backend.jobs import set_job_queue
from meetingai_backend.settings import set_settings


@pytest.fixture(autouse=True)
def reset_settings_cache() -> None:
    """Ensure settings cache is cleared before and after each test."""
    set_settings(None)
    yield
    set_settings(None)


class _StubQueue:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def enqueue(self, func: str, *args, **kwargs) -> object:
        payload = {"func": func, "args": args, "kwargs": kwargs}
        self.calls.append(payload)
        return object()


@pytest.fixture(autouse=True)
def stub_job_queue() -> Iterator[_StubQueue]:
    """Provide a stubbed queue so API handlers do not hit a real Redis instance."""
    queue = _StubQueue()
    set_job_queue(queue)
    yield queue
    set_job_queue(None)


def _create_test_client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_upload_video_persists_file_and_returns_job_id(
    tmp_path, monkeypatch
) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setenv("MEETINGAI_UPLOAD_DIR", str(upload_root))

    async with _create_test_client() as client:
        response = await client.post(
            "/api/videos",
            files={"file": ("meeting.mp4", b"sample-bytes", "video/mp4")},
        )

    assert response.status_code == 202
    payload = response.json()
    job_id = payload["job_id"]

    stored_dir = upload_root / job_id
    assert stored_dir.exists(), f"expected upload directory {stored_dir} to exist"

    stored_files = list(stored_dir.iterdir())
    assert stored_files, "expected uploaded file to be saved to disk"
    assert stored_files[0].read_bytes() == b"sample-bytes"


@pytest.mark.asyncio
async def test_upload_video_accepts_octet_stream(monkeypatch, tmp_path) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setenv("MEETINGAI_UPLOAD_DIR", str(upload_root))

    async with _create_test_client() as client:
        response = await client.post(
            "/api/videos",
            files={
                "file": ("recording.mov", b"binary-data", "application/octet-stream")
            },
        )

    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body


@pytest.mark.asyncio
async def test_upload_video_rejects_non_video_content(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MEETINGAI_UPLOAD_DIR", str(tmp_path))

    async with _create_test_client() as client:
        response = await client.post(
            "/api/videos",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )

    assert response.status_code == 415
    assert (
        response.json()["detail"]
        == "Unsupported media type. Please upload a video or audio file."
    )


@pytest.mark.asyncio
async def test_upload_video_enqueues_job(
    monkeypatch, tmp_path, stub_job_queue: _StubQueue
) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setenv("MEETINGAI_UPLOAD_DIR", str(upload_root))

    async with _create_test_client() as client:
        response = await client.post(
            "/api/videos",
            files={"file": ("meeting.mp4", b"bytes", "video/mp4")},
        )

    assert response.status_code == 202
    assert stub_job_queue.calls, "expected enqueue to be called"

    call = stub_job_queue.calls[0]
    assert call["func"] == "meetingai_backend.tasks.ingest.process_uploaded_video"
    assert call["args"] == ()
    kwargs = call["kwargs"]
    assert isinstance(kwargs, dict)
    job_kwargs = kwargs["kwargs"]
    payload = response.json()
    assert job_kwargs["job_id"] == payload["job_id"]
    assert job_kwargs["source_path"].endswith("meeting.mp4")


@pytest.mark.asyncio
async def test_upload_audio_mp3_accepted(monkeypatch, tmp_path) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setenv("MEETINGAI_UPLOAD_DIR", str(upload_root))

    async with _create_test_client() as client:
        response = await client.post(
            "/api/videos",
            files={"file": ("recording.mp3", b"mp3-bytes", "audio/mpeg")},
        )

    assert response.status_code == 202
    payload = response.json()
    assert "job_id" in payload


@pytest.mark.asyncio
async def test_upload_audio_wav_accepted(monkeypatch, tmp_path) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setenv("MEETINGAI_UPLOAD_DIR", str(upload_root))

    async with _create_test_client() as client:
        response = await client.post(
            "/api/videos",
            files={"file": ("recording.wav", b"wav-bytes", "audio/wav")},
        )

    assert response.status_code == 202
    payload = response.json()
    assert "job_id" in payload


@pytest.mark.asyncio
async def test_upload_audio_m4a_accepted(monkeypatch, tmp_path) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setenv("MEETINGAI_UPLOAD_DIR", str(upload_root))

    async with _create_test_client() as client:
        response = await client.post(
            "/api/videos",
            files={"file": ("recording.m4a", b"m4a-bytes", "audio/x-m4a")},
        )

    assert response.status_code == 202
    payload = response.json()
    assert "job_id" in payload


@pytest.mark.asyncio
async def test_upload_audio_enqueues_job(
    monkeypatch, tmp_path, stub_job_queue: _StubQueue
) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setenv("MEETINGAI_UPLOAD_DIR", str(upload_root))

    async with _create_test_client() as client:
        response = await client.post(
            "/api/videos",
            files={"file": ("recording.mp3", b"mp3-bytes", "audio/mpeg")},
        )

    assert response.status_code == 202
    assert stub_job_queue.calls, "expected enqueue to be called"

    call = stub_job_queue.calls[0]
    assert call["func"] == "meetingai_backend.tasks.ingest.process_uploaded_video"
    kwargs = call["kwargs"]
    assert isinstance(kwargs, dict)
    job_kwargs = kwargs["kwargs"]
    payload = response.json()
    assert job_kwargs["job_id"] == payload["job_id"]
    assert job_kwargs["source_path"].endswith("recording.mp3")
