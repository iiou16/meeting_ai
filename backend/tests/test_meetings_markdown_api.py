"""Integration tests for GET /api/meetings/{job_id}/markdown."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from meetingai_backend.app import create_app
from meetingai_backend.job_state import save_job_title
from meetingai_backend.settings import Settings, set_settings
from meetingai_backend.summarization import (
    ActionItem,
    SummaryItem,
    dump_action_items,
    dump_summary_items,
)
from meetingai_backend.transcription.segments import (
    TranscriptSegment,
    dump_transcript_segments,
)


def _configure_settings(tmp_path: Path) -> None:
    settings = Settings(
        upload_root=tmp_path,
        redis_url="redis://localhost:6379/0",
        job_queue_name="meetingai:jobs",
        job_timeout_seconds=900,
        ffmpeg_path="ffmpeg",
        openai_api_key="test-key",
    )
    set_settings(settings)


def _seed_meeting(job_dir: Path, *, title: str | None = None) -> None:
    job_dir.mkdir()

    if title is not None:
        save_job_title(job_dir, title=title)

    segments = [
        TranscriptSegment(
            segment_id="seg-1",
            job_id=job_dir.name,
            order=0,
            start_ms=0,
            end_ms=30_000,
            text="Hello everyone.",
            language="en",
            speaker_label="Host",
            source_asset_id="asset-1",
            extra={},
        )
    ]
    dump_transcript_segments(job_dir, segments)

    summary_items = [
        SummaryItem.create(
            job_id=job_dir.name,
            order=0,
            segment_start_ms=0,
            segment_end_ms=30_000,
            summary_text="Greetings and introductions.",
            heading="Opening",
        )
    ]
    dump_summary_items(job_dir, summary_items)

    action_items = [
        ActionItem.create(
            job_id=job_dir.name,
            order=0,
            description="Prepare slides.",
            owner="Bob",
            due_date="2025-06-15",
            segment_start_ms=0,
            segment_end_ms=30_000,
        )
    ]
    dump_action_items(job_dir, action_items)


def test_markdown_endpoint_returns_markdown(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-md-1"
    _seed_meeting(job_dir, title="Test Meeting")
    _configure_settings(tmp_path)

    client = TestClient(create_app())
    response = client.get("/api/meetings/job-md-1/markdown")

    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    assert 'filename="job-md-1.md"' in response.headers["content-disposition"]

    body = response.text
    assert body.startswith("# Test Meeting")
    assert "**Job ID**: job-md-1" in body
    assert "### Opening (00:00 - 00:30)" in body
    assert "Greetings and introductions." in body
    assert "Prepare slides." in body
    assert "Bob" in body
    assert "**[00:00]** Host: Hello everyone." in body

    set_settings(None)


def test_markdown_endpoint_without_title(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-md-2"
    _seed_meeting(job_dir, title=None)
    _configure_settings(tmp_path)

    client = TestClient(create_app())
    response = client.get("/api/meetings/job-md-2/markdown")

    assert response.status_code == 200
    body = response.text
    assert body.startswith("# job-md-2")

    set_settings(None)


def test_markdown_endpoint_404(tmp_path: Path) -> None:
    _configure_settings(tmp_path)

    client = TestClient(create_app())
    response = client.get("/api/meetings/nonexistent/markdown")

    assert response.status_code == 404

    set_settings(None)
