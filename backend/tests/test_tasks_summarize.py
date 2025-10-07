from __future__ import annotations

from pathlib import Path

from meetingai_backend.settings import Settings, set_settings
from meetingai_backend.summarization import (
    load_action_items,
    load_summary_items,
    load_summary_quality,
)
from meetingai_backend.tasks.summarize import summarize_job
from meetingai_backend.transcription.segments import (
    TranscriptSegment,
    dump_transcript_segments,
)


def _make_segment(order: int) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=f"segment-{order}",
        job_id="job-123",
        order=order,
        start_ms=order * 60_000,
        end_ms=(order + 1) * 60_000,
        text=f"Discussion point {order}",
        language="ja",
        speaker_label=None,
        source_asset_id=f"asset-{order}",
        extra={},
    )


def test_summarize_job_persists_results(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-123"
    job_dir.mkdir()

    segments = [_make_segment(0), _make_segment(1)]
    dump_transcript_segments(job_dir, segments)

    settings = Settings(
        upload_root=tmp_path,
        redis_url="redis://localhost:6379/0",
        job_queue_name="meetingai:jobs",
        job_timeout_seconds=900,
        ffmpeg_path="ffmpeg",
        openai_api_key="test-key",
    )
    set_settings(settings)

    def fake_request(*, prompt, config):
        return {
            "summary_sections": [
                {
                    "summary": "Recap of discussion point 0.",
                    "start_ms": 0,
                    "end_ms": 60000,
                }
            ],
            "action_items": [
                {
                    "description": "Follow up on discussion point 1.",
                    "owner": "Bob",
                    "start_ms": 60000,
                    "end_ms": 120000,
                }
            ],
        }

    result = summarize_job(
        job_id="job-123",
        job_directory=str(job_dir),
        request_fn=fake_request,
    )

    assert result["summary_count"] == 1
    assert result["action_item_count"] == 1

    summary_items = load_summary_items(job_dir)
    assert summary_items and summary_items[0].summary_text.startswith("Recap")

    action_items = load_action_items(job_dir)
    assert action_items and action_items[0].owner == "Bob"

    quality = load_summary_quality(job_dir)
    assert quality is not None
    assert quality.action_item_count == 1
