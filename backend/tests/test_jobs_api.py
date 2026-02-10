from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from meetingai_backend.app import create_app
from meetingai_backend.job_state import mark_job_failed
from meetingai_backend.settings import Settings, set_settings
from meetingai_backend.summarization import (
    ActionItem,
    SummaryItem,
    SummaryQualityMetrics,
    dump_action_items,
    dump_summary_items,
    dump_summary_quality,
)
from meetingai_backend.transcription.segments import (
    TranscriptSegment,
    dump_transcript_segments,
)


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
    job_dir.mkdir()
    segments = [
        TranscriptSegment(
            segment_id="seg-1",
            job_id=job_dir.name,
            order=0,
            start_ms=0,
            end_ms=60_000,
            text="議題の確認を行いました。",
            language="ja",
            speaker_label="Alice",
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
            segment_end_ms=60_000,
            summary_text="議題の確認とタスク割り当てを実施。",
            heading="議題確認",
            highlights=["スケジュール共有"],
        )
    ]
    dump_summary_items(job_dir, summary_items)

    action_items = [
        ActionItem.create(
            job_id=job_dir.name,
            order=0,
            description="次回会議までに議事録を送付する。",
            owner="Bob",
            due_date="2025-06-01",
            segment_start_ms=0,
            segment_end_ms=60_000,
        )
    ]
    dump_action_items(job_dir, action_items)

    quality = SummaryQualityMetrics(
        coverage_ratio=0.95,
        referenced_segments_ratio=1.0,
        average_summary_word_count=12.5,
        action_item_count=1,
        llm_confidence=0.88,
    )
    dump_summary_quality(job_dir, quality)


def _create_pending_job(job_dir: Path) -> None:
    job_dir.mkdir()
    (job_dir / "meeting.mov").write_bytes(b"\x00\x00")


def test_jobs_endpoints(tmp_path: Path) -> None:
    completed_dir = tmp_path / "job-complete"
    pending_dir = tmp_path / "job-pending"
    _create_completed_job(completed_dir)
    _create_pending_job(pending_dir)

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())

    response = client.get("/api/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 2

    completed = next(job for job in jobs if job["job_id"] == "job-complete")
    assert completed["status"] == "completed"
    assert completed["summary_count"] == 1
    assert completed["action_item_count"] == 1
    assert completed["progress"] == 1.0
    assert completed["stage_index"] == 4
    assert completed["stage_count"] == 4
    assert completed["stage_key"] == "summary"
    assert completed["languages"] == ["ja"]
    assert completed["can_delete"] is True

    pending = next(job for job in jobs if job["job_id"] == "job-pending")
    assert pending["status"] == "pending"
    assert pending["progress"] == 0.25
    assert pending["stage_index"] == 1
    assert pending["stage_count"] == 4
    assert pending["stage_key"] == "upload"
    assert pending["can_delete"] is False

    detail = client.get("/api/jobs/job-complete")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["job_id"] == "job-complete"
    assert payload["quality_metrics"]["coverage_ratio"] == 0.95

    missing = client.get("/api/jobs/not-found")
    assert missing.status_code == 404

    set_settings(None)


def test_stage_info_transcribing(tmp_path: Path) -> None:
    """Job with audio chunks should report stage_key='chunking', stage_index=2."""
    job_dir = tmp_path / "job-chunks"
    job_dir.mkdir()
    chunks_dir = job_dir / "audio_chunks"
    chunks_dir.mkdir()
    (chunks_dir / "chunk_000.wav").write_bytes(b"\x00\x00")

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())
    response = client.get("/api/jobs")
    assert response.status_code == 200
    jobs = response.json()
    job = next(j for j in jobs if j["job_id"] == "job-chunks")
    assert job["stage_index"] == 2
    assert job["stage_count"] == 4
    assert job["stage_key"] == "chunking"

    set_settings(None)


def test_stage_info_summarizing(tmp_path: Path) -> None:
    """Job with transcript should report stage_key='transcription', stage_index=3."""
    job_dir = tmp_path / "job-transcript"
    job_dir.mkdir()
    segments = [
        TranscriptSegment(
            segment_id="seg-1",
            job_id="job-transcript",
            order=0,
            start_ms=0,
            end_ms=60_000,
            text="テスト",
            language="ja",
            speaker_label=None,
            source_asset_id="asset-1",
            extra={},
        )
    ]
    dump_transcript_segments(job_dir, segments)

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())
    response = client.get("/api/jobs")
    assert response.status_code == 200
    jobs = response.json()
    job = next(j for j in jobs if j["job_id"] == "job-transcript")
    assert job["stage_index"] == 3
    assert job["stage_count"] == 4
    assert job["stage_key"] == "transcription"

    set_settings(None)


def test_progress_audio_source_file(tmp_path: Path) -> None:
    """A job directory with an audio source file (e.g. .mp3) should report progress=0.25."""
    job_dir = tmp_path / "job-audio"
    job_dir.mkdir()
    (job_dir / "recording.mp3").write_bytes(b"\x00\x00")

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())

    response = client.get("/api/jobs")
    assert response.status_code == 200
    jobs = response.json()
    audio_job = next(job for job in jobs if job["job_id"] == "job-audio")
    assert audio_job["status"] == "pending"
    assert audio_job["progress"] == 0.25

    set_settings(None)


def test_job_with_unknown_failure_stage(tmp_path: Path) -> None:
    """job_failed.jsonに未知のstage値があってもジョブ一覧APIが500にならない。

    過去のバグで不正なstage値（例: "rq_worker"）が記録されたデータが
    ディスクに残っている場合、ジョブ一覧の取得でKeyErrorが発生して
    全ジョブが表示不能になっていた。
    """
    job_dir = tmp_path / "job-bad-stage"
    job_dir.mkdir()
    (job_dir / "meeting.mov").write_bytes(b"\x00\x00")

    # 不正なstage値を持つ失敗レコードを作成
    mark_job_failed(
        job_dir,
        stage="rq_worker",  # _STAGE_INDEXに存在しない値
        error="test error with unknown stage",
    )

    settings = _make_settings(tmp_path)
    set_settings(settings)

    client = TestClient(create_app())

    # ジョブ一覧が500にならずにレスポンスを返すこと
    response = client.get("/api/jobs")
    assert response.status_code == 200
    jobs = response.json()
    bad_job = next(j for j in jobs if j["job_id"] == "job-bad-stage")
    assert bad_job["status"] == "failed"
    assert bad_job["failure"]["message"] == "test error with unknown stage"
    # 未知のstageでもstage_keyは記録されたstage値がそのまま返ること
    assert bad_job["failure"]["stage"] == "rq_worker"

    # 個別ジョブ詳細も同様に取得できること
    detail_response = client.get("/api/jobs/job-bad-stage")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "failed"

    set_settings(None)
