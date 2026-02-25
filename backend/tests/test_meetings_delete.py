from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from meetingai_backend.app import create_app
from meetingai_backend.job_state import mark_job_failed
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


def _create_completed_job(job_dir: Path) -> None:
    """summary_items.json を含む完了済みジョブを作成。"""
    job_dir.mkdir()
    (job_dir / "summary_items.json").write_text(json.dumps([]), encoding="utf-8")


def test_delete_completed_meeting_removes_directory(tmp_path: Path) -> None:
    """完了済みジョブの削除が成功すること。"""
    job_dir = tmp_path / "job-001"
    _create_completed_job(job_dir)
    (job_dir / "audio_chunks").mkdir()
    (job_dir / "audio_chunks" / "chunk.wav").write_bytes(b"data")

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())

    response = client.delete("/api/meetings/job-001")
    assert response.status_code == 204
    assert not job_dir.exists()

    set_settings(None)


def test_delete_failed_meeting_removes_directory(tmp_path: Path) -> None:
    """失敗ジョブの削除が成功すること。"""
    job_dir = tmp_path / "job-failed"
    job_dir.mkdir()
    (job_dir / "meeting.mov").write_bytes(b"\x00\x00")
    mark_job_failed(job_dir, stage="transcription", error="API timeout")

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())

    response = client.delete("/api/meetings/job-failed")
    assert response.status_code == 204
    assert not job_dir.exists()

    set_settings(None)


def test_delete_processing_job_returns_409(tmp_path: Path) -> None:
    """処理中ジョブの削除は 409 Conflict で拒否されること。"""
    job_dir = tmp_path / "job-processing"
    job_dir.mkdir()
    chunks_dir = job_dir / "audio_chunks"
    chunks_dir.mkdir()
    (chunks_dir / "chunk_000.wav").write_bytes(b"data")

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())

    response = client.delete("/api/meetings/job-processing")
    assert response.status_code == 409
    assert job_dir.exists()

    set_settings(None)


def test_delete_pending_job_returns_409(tmp_path: Path) -> None:
    """ペンディングジョブの削除は 409 Conflict で拒否されること。"""
    job_dir = tmp_path / "job-pending"
    job_dir.mkdir()
    (job_dir / "meeting.mov").write_bytes(b"\x00\x00")

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())

    response = client.delete("/api/meetings/job-pending")
    assert response.status_code == 409
    assert job_dir.exists()

    set_settings(None)


def test_delete_failed_job_with_corrupt_failure_json(tmp_path: Path) -> None:
    """job_failed.json が破損していても削除が成功すること。"""
    job_dir = tmp_path / "job-corrupt"
    job_dir.mkdir()
    (job_dir / "meeting.mov").write_bytes(b"\x00\x00")
    (job_dir / "job_failed.json").write_text("NOT VALID JSON{{{", encoding="utf-8")

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())

    response = client.delete("/api/meetings/job-corrupt")
    assert response.status_code == 204
    assert not job_dir.exists()

    set_settings(None)
