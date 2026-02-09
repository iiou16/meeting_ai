"""Job status inspection endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..media.assets import load_media_assets
from ..settings import Settings, get_settings
from ..summarization import load_action_items, load_summary_items, load_summary_quality
from ..transcription.segments import load_transcript_segments

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobStatus(str, Enum):
    """Simple lifecycle phases for jobs."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobSummary(BaseModel):
    """Short-form metadata for dashboards."""

    job_id: str = Field(..., description="Unique identifier of the job.")
    status: JobStatus = Field(..., description="Current processing state.")
    created_at: datetime = Field(..., description="When the job directory was created.")
    updated_at: datetime = Field(..., description="Last modification timestamp.")
    progress: float = Field(
        ..., ge=0.0, le=1.0, description="Approximate completion ratio (0.0-1.0)."
    )
    duration_ms: int | None = Field(
        None, description="Media duration in milliseconds, if available."
    )
    languages: list[str] = Field(
        default_factory=list, description="Detected languages."
    )
    summary_count: int = Field(0, description="Number of summary sections.")
    action_item_count: int = Field(0, description="Number of action items.")


class JobDetail(JobSummary):
    """Detailed metadata with quality metrics."""

    quality_metrics: dict[str, Any] | None = Field(
        None, description="Optional quality metrics computed during summarisation."
    )


def _iter_job_directories(settings: Settings) -> list[Path]:
    upload_root = settings.upload_root
    if not upload_root.exists():
        return []
    return [path for path in sorted(upload_root.iterdir()) if path.is_dir()]


def _timestamp_from_stat(path: Path, *, use_ctime: bool) -> datetime:
    stat = path.stat()
    source = stat.st_ctime if use_ctime else stat.st_mtime
    return datetime.fromtimestamp(source, tz=timezone.utc)


def _has_file(job_directory: Path, name: str) -> bool:
    return (job_directory / name).exists()


def _calculate_progress(job_directory: Path) -> float:
    if _has_file(job_directory, "summary_items.json"):
        return 1.0
    if _has_file(job_directory, "transcript_segments.json"):
        return 0.7
    if list(job_directory.glob("audio_chunks/*.wav")):
        return 0.4
    _source_exts = (
        "*.mov", "*.mp4", "*.webm",
        "*.mp3", "*.wav", "*.m4a", "*.aac", "*.flac", "*.ogg",
    )
    if any(list(job_directory.glob(ext)) for ext in _source_exts):
        return 0.2
    return 0.0


def _determine_status(job_directory: Path) -> JobStatus:
    if _has_file(job_directory, "summary_items.json"):
        return JobStatus.COMPLETED
    if _has_file(job_directory, "transcript_segments.json"):
        return JobStatus.PROCESSING
    if any(job_directory.glob("*")):
        return JobStatus.PENDING
    return JobStatus.PENDING


def _load_job_summary(job_id: str, job_directory: Path) -> JobSummary:
    segments = load_transcript_segments(job_directory)
    summary_items = load_summary_items(job_directory)
    action_items = load_action_items(job_directory)

    languages = sorted(
        {segment.language for segment in segments if segment.language},
        key=lambda value: value or "",
    )

    duration_ms: int | None = None
    try:
        assets = load_media_assets(job_directory)
        masters = [asset for asset in assets if asset.kind == "audio_master"]
        if masters:
            duration_ms = int(masters[0].duration_ms)
    except FileNotFoundError:
        duration_ms = None

    created_at = _timestamp_from_stat(job_directory, use_ctime=True)
    updated_at = _timestamp_from_stat(job_directory, use_ctime=False)
    status_value = _determine_status(job_directory)
    progress = _calculate_progress(job_directory)

    return JobSummary(
        job_id=job_id,
        status=status_value,
        created_at=created_at,
        updated_at=updated_at,
        progress=round(progress, 3),
        duration_ms=duration_ms,
        languages=languages,
        summary_count=len(summary_items),
        action_item_count=len(action_items),
    )


def _load_job_detail(job_id: str, job_directory: Path) -> JobDetail:
    summary = _load_job_summary(job_id, job_directory)
    quality = load_summary_quality(job_directory)
    return JobDetail(
        **summary.model_dump(),
        quality_metrics=quality.to_dict() if quality else None,
    )


@router.get("", response_model=list[JobSummary])
def list_jobs(settings: Settings = Depends(get_settings)) -> list[JobSummary]:
    """Return all known job directories with their current status."""
    jobs: list[JobSummary] = []
    for directory in _iter_job_directories(settings):
        job_id = directory.name
        jobs.append(_load_job_summary(job_id, directory))
    return sorted(jobs, key=lambda item: item.updated_at, reverse=True)


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: str, settings: Settings = Depends(get_settings)) -> JobDetail:
    """Return detailed metadata for a single job."""
    job_directory = settings.upload_root / job_id
    if not job_directory.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")

    return _load_job_detail(job_id, job_directory)


__all__ = ["router", "JobStatus", "JobSummary", "JobDetail"]
