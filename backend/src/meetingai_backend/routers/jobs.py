"""Job status inspection endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from ..job_state import (
    JOB_STAGE_CHUNKING,
    JOB_STAGE_SUMMARY,
    JOB_STAGE_TRANSCRIPTION,
    JOB_STAGE_UPLOAD,
    JobFailureRecord,
    load_job_failure,
)
from ..media.assets import load_media_assets
from ..settings import Settings, get_settings
from ..summarization import load_action_items, load_summary_items, load_summary_quality
from ..transcription.segments import load_transcript_segments

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_STAGES = (
    JOB_STAGE_UPLOAD,
    JOB_STAGE_CHUNKING,
    JOB_STAGE_TRANSCRIPTION,
    JOB_STAGE_SUMMARY,
)
_STAGE_COUNT = len(_STAGES)
_STAGE_INDEX = {key: index + 1 for index, key in enumerate(_STAGES)}


class JobStatus(str, Enum):
    """Simple lifecycle phases for jobs."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobFailure(BaseModel):
    stage: str = Field(..., description="Stage where the failure occurred.")
    message: str = Field(..., description="Failure message.")
    occurred_at: datetime = Field(
        ..., description="Timestamp when the failure was recorded."
    )


class JobSummary(BaseModel):
    """Short-form metadata for dashboards."""

    job_id: str = Field(..., description="Unique identifier of the job.")
    status: JobStatus = Field(..., description="Current processing state.")
    created_at: datetime = Field(..., description="When the job directory was created.")
    updated_at: datetime = Field(..., description="Last modification timestamp.")
    progress: float = Field(
        ..., ge=0.0, le=1.0, description="Approximate completion ratio (0.0-1.0)."
    )
    stage_index: int = Field(..., ge=1, description="1-based current stage index.")
    stage_count: int = Field(
        ..., ge=1, description="Total number of processing stages."
    )
    stage_key: str = Field(..., description="Identifier of the current stage.")
    duration_ms: int | None = Field(
        None, description="Media duration in milliseconds, if available."
    )
    languages: list[str] = Field(
        default_factory=list, description="Detected languages."
    )
    summary_count: int = Field(0, description="Number of summary sections.")
    action_item_count: int = Field(0, description="Number of action items.")
    can_delete: bool = Field(
        False,
        description="Indicates whether the job artefacts can be safely deleted.",
    )
    failure: JobFailure | None = Field(
        default=None,
        description="Failure metadata when the job has failed.",
    )


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


def _has_source_video(job_directory: Path) -> bool:
    patterns = ("*.mov", "*.mp4", "*.mkv", "*.webm")
    for pattern in patterns:
        if list(job_directory.glob(pattern)):
            return True
    return False


def _detect_stage(job_directory: Path) -> tuple[int, str]:
    """Detect the current in-progress stage based on completed artifacts.

    Each artifact indicates the *previous* stage completed, so we return the
    *next* stage (the one currently in progress).  For example, when
    ``audio_chunks/*.wav`` files exist, chunking has finished and transcription
    is the active stage.
    """
    if _has_file(job_directory, "summary_items.json"):
        return _STAGE_COUNT, JOB_STAGE_SUMMARY
    if _has_file(job_directory, "transcript_segments.json"):
        return 3, JOB_STAGE_SUMMARY
    if list(job_directory.glob("audio_chunks/*.wav")):
        return 2, JOB_STAGE_TRANSCRIPTION
    if _has_source_video(job_directory):
        return 1, JOB_STAGE_CHUNKING
    return 1, JOB_STAGE_UPLOAD


def _determine_status(stage_index: int, job_directory: Path) -> JobStatus:
    if stage_index >= _STAGE_COUNT:
        return JobStatus.COMPLETED
    if stage_index >= 2:
        return JobStatus.PROCESSING
    if any(job_directory.glob("*")):
        return JobStatus.PENDING
    return JobStatus.PENDING


def _build_failure_record(record: JobFailureRecord) -> JobFailure:
    return JobFailure(
        stage=record.stage,
        message=record.message,
        occurred_at=record.occurred_at,
    )


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
        logger.warning(
            "Media assets not found for job %s; duration unavailable", job_id
        )

    created_at = _timestamp_from_stat(job_directory, use_ctime=True)
    updated_at = _timestamp_from_stat(job_directory, use_ctime=False)
    failure_record = load_job_failure(job_directory)
    if failure_record:
        stage_key = failure_record.stage
        if stage_key not in _STAGE_INDEX:
            logger.warning(
                "Job %s has unknown failure stage '%s'; valid stages: %s",
                job_id,
                stage_key,
                list(_STAGE_INDEX.keys()),
            )
            stage_index = 1
        else:
            stage_index = _STAGE_INDEX[stage_key]
        status_value = JobStatus.FAILED
        progress = stage_index / _STAGE_COUNT
        failure = _build_failure_record(failure_record)
        can_delete = False
    else:
        stage_index, stage_key = _detect_stage(job_directory)
        status_value = _determine_status(stage_index, job_directory)
        progress = stage_index / _STAGE_COUNT
        failure = None
        can_delete = stage_index >= _STAGE_COUNT

    return JobSummary(
        job_id=job_id,
        status=status_value,
        created_at=created_at,
        updated_at=updated_at,
        progress=round(progress, 3),
        stage_index=stage_index,
        stage_count=_STAGE_COUNT,
        stage_key=stage_key,
        duration_ms=duration_ms,
        languages=languages,
        summary_count=len(summary_items),
        action_item_count=len(action_items),
        can_delete=can_delete,
        failure=failure,
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


__all__ = ["router", "JobStatus", "JobSummary", "JobDetail", "JobFailure"]
