from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from meetingai_backend.app import create_app
from meetingai_backend.settings import Settings, set_settings


def _make_settings(upload_root: Path) -> Settings:
    return Settings(
        upload_root=upload_root,
        redis_url="redis://localhost:6379/0",
        job_queue_name="meetingai:jobs",
        job_timeout_seconds=900,
        ffmpeg_path="ffmpeg",
        openai_api_key="test-key",
    )


def test_delete_meeting_removes_directory(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-001"
    job_dir.mkdir()
    (job_dir / "file.txt").write_text("hello", encoding="utf-8")
    (job_dir / "audio_chunks").mkdir()
    (job_dir / "audio_chunks" / "chunk.mp3").write_bytes(b"data")

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())

    response = client.delete("/api/meetings/job-001")
    assert response.status_code == 204
    assert not job_dir.exists()

    set_settings(None)
