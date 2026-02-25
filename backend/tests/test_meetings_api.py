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

    # speaker_mappings is null when not set
    assert payload["speaker_mappings"] is None

    missing = client.get("/api/meetings/unknown")
    assert missing.status_code == 404

    set_settings(None)


def test_get_meeting_includes_speaker_mappings(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-sp"
    _seed_meeting(job_dir)
    _configure_settings(tmp_path)

    client = TestClient(create_app())

    # Save speaker mappings via PUT
    body = {
        "profiles": {
            "p1": {"profile_id": "p1", "name": "田中", "organization": "開発"},
        },
        "label_to_profile": {},
    }
    put_resp = client.put("/api/meetings/job-sp/speakers", json=body)
    assert put_resp.status_code == 200

    # GET should include mappings
    get_resp = client.get("/api/meetings/job-sp")
    assert get_resp.status_code == 200
    payload = get_resp.json()
    assert payload["speaker_mappings"] is not None
    assert payload["speaker_mappings"]["profiles"]["p1"]["name"] == "田中"

    set_settings(None)


def test_put_speakers_validates_profile_id_reference(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-val"
    _seed_meeting(job_dir)
    _configure_settings(tmp_path)

    client = TestClient(create_app())

    body = {
        "profiles": {
            "p1": {"profile_id": "p1", "name": "Alice", "organization": ""},
        },
        "label_to_profile": {"Speaker A": "nonexistent"},
    }
    resp = client.put("/api/meetings/job-val/speakers", json=body)
    assert resp.status_code == 422

    set_settings(None)


def test_put_speakers_validates_empty_name(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-empty-name"
    _seed_meeting(job_dir)
    _configure_settings(tmp_path)

    client = TestClient(create_app())

    body = {
        "profiles": {
            "p1": {"profile_id": "p1", "name": "", "organization": ""},
        },
        "label_to_profile": {},
    }
    resp = client.put("/api/meetings/job-empty-name/speakers", json=body)
    assert resp.status_code == 422

    set_settings(None)


def test_put_speakers_not_found(tmp_path: Path) -> None:
    _configure_settings(tmp_path)
    client = TestClient(create_app())

    body = {"profiles": {}, "label_to_profile": {}}
    resp = client.put("/api/meetings/nonexistent/speakers", json=body)
    assert resp.status_code == 404

    set_settings(None)
