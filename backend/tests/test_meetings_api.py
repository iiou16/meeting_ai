from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from meetingai_backend.app import create_app
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


def _seed_meeting(job_dir: Path) -> None:
    job_dir.mkdir()

    segments = [
        TranscriptSegment(
            segment_id="seg-1",
            job_id=job_dir.name,
            order=0,
            start_ms=0,
            end_ms=30_000,
            text="チームの進捗を確認しました。",
            language="ja",
            speaker_label=None,
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
            summary_text="チームの進捗を確認し、次のステップを決定。",
        )
    ]
    dump_summary_items(job_dir, summary_items)

    action_items = [
        ActionItem.create(
            job_id=job_dir.name,
            order=0,
            description="週末までにレポートを送付する。",
            owner="Carol",
        )
    ]
    dump_action_items(job_dir, action_items)


def test_get_meeting_returns_content(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-42"
    _seed_meeting(job_dir)
    _configure_settings(tmp_path)

    client = TestClient(create_app())

    response = client.get("/api/meetings/job-42")
    assert response.status_code == 200

    payload = response.json()
    assert payload["job_id"] == "job-42"
    assert len(payload["segments"]) == 1
    assert payload["segments"][0]["text"].startswith("チームの進捗")
    assert len(payload["summary_items"]) == 1
    assert payload["summary_items"][0]["summary_text"].startswith("チームの進捗")
    assert len(payload["action_items"]) == 1
    assert payload["action_items"][0]["owner"] == "Carol"

    missing = client.get("/api/meetings/unknown")
    assert missing.status_code == 404

    set_settings(None)
