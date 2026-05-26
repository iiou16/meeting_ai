"""Job status inspection endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, status

if TYPE_CHECKING:
    from ..transcription.progress import TranscriptionProgress
from pydantic import BaseModel, Field, field_validator, model_validator

from ..job_state import (
    JOB_STAGE_CHUNKING,
    JOB_STAGE_SUMMARY,
    JOB_STAGE_TRANSCRIPTION,
    JOB_STAGE_UPLOAD,
    JobFailureRecord,
    load_job_failure,
    load_job_title,
    load_recorded_at,
    save_job_title,
    save_recorded_at,
)
from ..media.assets import load_media_assets
from ..settings import Settings, get_settings
from ..summarization import load_action_items, load_summary_items, load_summary_quality
from ..transcription.segments import load_transcript_segments

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobRetryRequest(BaseModel):
    """Optional override for the language when retrying a job."""

    language: str | None = Field(
        default=None,
        description="Override transcription language (ja/en). Required when not stored on disk.",
    )


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
    title: str | None = Field(None, description="User-assigned title for the job.")
    status: JobStatus = Field(..., description="Current processing state.")
    created_at: datetime = Field(..., description="When the job directory was created.")
    updated_at: datetime = Field(..., description="Last modification timestamp.")
    recorded_at: datetime | None = Field(
        None,
        description="When the meeting was recorded (from media file metadata).",
    )
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
    sub_progress_completed: int | None = Field(
        None, description="Sub-progress completed count within current stage."
    )
    sub_progress_total: int | None = Field(
        None, description="Sub-progress total count within current stage."
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


class JobUpdate(BaseModel):
    """Request body for updating job metadata (title and/or recorded_at)."""

    title: str | None = Field(
        None, min_length=1, max_length=200, description="New title for the job."
    )
    recorded_at: datetime | None = Field(
        None, description="New recorded-at timestamp (ISO 8601)."
    )

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        return stripped

    @model_validator(mode="after")
    def at_least_one_field(self) -> JobUpdate:
        if self.title is None and self.recorded_at is None:
            raise ValueError(
                "at least one of 'title' or 'recorded_at' must be provided"
            )
        return self


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
    ``audio_chunks/*.wav`` files exist, chunking has
    finished and transcription is the active stage.
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


def _compute_sub_progress(
    record: TranscriptionProgress | None, stage_key: str
) -> float:
    """Return sub-progress within the current stage (0.0-1.0)."""
    if stage_key != JOB_STAGE_TRANSCRIPTION:
        return 0.0
    if record is None:
        return 0.0  # transcription タスクがまだ開始されていない
    if record.chunks_total <= 0:
        raise ValueError(
            f"Invalid chunks_total={record.chunks_total} in progress record"
        )
    return record.chunks_completed / record.chunks_total


def _determine_status(stage_index: int) -> JobStatus:
    if stage_index >= _STAGE_COUNT:
        return JobStatus.COMPLETED
    if stage_index >= 2:
        return JobStatus.PROCESSING
    return JobStatus.PENDING


def _build_failure_record(record: JobFailureRecord) -> JobFailure:
    return JobFailure(
        stage=record.stage,
        message=record.message,
        occurred_at=record.occurred_at,
    )


def _compute_progress(
    stage_index: int,
    stage_key: str,
    progress_record: TranscriptionProgress | None,
) -> float:
    """Compute overall progress (0.0-1.0) with sub-stage interpolation.

    The denominator is _STAGE_COUNT + 1 to reserve space for sub-stage
    interpolation within each stage (e.g. transcription chunk progress).
    This ensures progress smoothly approaches but never reaches 1.0 until
    the job is fully completed.
    """
    if stage_index >= _STAGE_COUNT:
        return 1.0
    sub = _compute_sub_progress(progress_record, stage_key)
    return (stage_index + sub) / (_STAGE_COUNT + 1)


def _load_job_summary(job_id: str, job_directory: Path) -> JobSummary:
    from ..transcription.progress import load_transcription_progress

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
    title = load_job_title(job_directory)
    recorded_at = load_recorded_at(job_directory)
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
        progress_record = load_transcription_progress(job_directory)
        progress = _compute_progress(stage_index, stage_key, progress_record)
        failure = _build_failure_record(failure_record)
        can_delete = True
    else:
        stage_index, stage_key = _detect_stage(job_directory)
        status_value = _determine_status(stage_index)
        progress_record = load_transcription_progress(job_directory)
        progress = _compute_progress(stage_index, stage_key, progress_record)
        failure = None
        can_delete = stage_index >= _STAGE_COUNT

    sub_completed: int | None = None
    sub_total: int | None = None
    if progress_record is not None and stage_key == JOB_STAGE_TRANSCRIPTION:
        sub_completed = progress_record.chunks_completed
        sub_total = progress_record.chunks_total

    return JobSummary(
        job_id=job_id,
        title=title,
        status=status_value,
        created_at=created_at,
        updated_at=updated_at,
        recorded_at=recorded_at,
        progress=round(progress, 3),
        stage_index=stage_index,
        stage_count=_STAGE_COUNT,
        stage_key=stage_key,
        duration_ms=duration_ms,
        languages=languages,
        summary_count=len(summary_items),
        action_item_count=len(action_items),
        can_delete=can_delete,
        sub_progress_completed=sub_completed,
        sub_progress_total=sub_total,
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

    with_recorded = [j for j in jobs if j.recorded_at is not None]
    without_recorded = [j for j in jobs if j.recorded_at is None]
    with_recorded.sort(key=lambda item: item.recorded_at, reverse=True)  # type: ignore[arg-type]
    without_recorded.sort(key=lambda item: item.updated_at, reverse=True)
    return with_recorded + without_recorded


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: str, settings: Settings = Depends(get_settings)) -> JobDetail:
    """Return detailed metadata for a single job."""
    job_directory = settings.upload_root / job_id
    if not job_directory.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")

    return _load_job_detail(job_id, job_directory)


@router.patch("/{job_id}", response_model=JobDetail)
def update_job(
    job_id: str,
    body: JobUpdate,
    settings: Settings = Depends(get_settings),
) -> JobDetail:
    """Update the user-assigned title and/or recorded_at for a job."""
    job_directory = settings.upload_root / job_id
    if not job_directory.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")

    if body.title is not None:
        save_job_title(job_directory, title=body.title)
    if body.recorded_at is not None:
        save_recorded_at(job_directory, recorded_at=body.recorded_at)
    return _load_job_detail(job_id, job_directory)


@router.post(
    "/{job_id}/retry",
    response_model=JobDetail,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_job(
    job_id: str,
    body: JobRetryRequest | None = None,
    settings: Settings = Depends(get_settings),
) -> JobDetail:
    """Re-enqueue a failed job at the stage where it failed."""
    from ..job_state import (
        consume_job_failure,
        load_job_language,
        load_source_path,
        restore_job_failure,
    )
    from ..jobs import (
        SUPPORTED_LANGUAGES,
        enqueue_summary_job,
        enqueue_transcription_job,
        enqueue_video_ingest_job,
        get_job_queue,
    )

    job_directory = settings.upload_root / job_id
    if not job_directory.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")

    # Validate the request body up-front so we never claim the failure marker
    # for an invalid request (which would leave the job in an "abandoned"
    # state — neither failed nor queued).
    if body is None:
        requested_language: str | None = None
    else:
        requested_language = body.language
    if requested_language is not None and requested_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unsupported language: {requested_language!r}; "
            f"must be one of {list(SUPPORTED_LANGUAGES)}",
        )

    # Atomically claim the failure marker so concurrent retry requests cannot
    # both proceed.  The loser of the race receives ``None`` and is told the
    # job is no longer failed (409).
    failure = consume_job_failure(job_directory)
    if failure is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "job is not in a failed state; retry is only allowed for failed jobs",
        )

    try:
        stage = failure.stage
        if stage not in _STAGE_INDEX:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"unknown failure stage on disk: {stage!r}",
            )

        if requested_language is None:
            language = load_job_language(job_directory)
        else:
            language = requested_language

        if stage in (
            JOB_STAGE_UPLOAD,
            JOB_STAGE_CHUNKING,
            JOB_STAGE_TRANSCRIPTION,
        ):
            if language is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "language is required to retry this job but is not stored on disk; "
                    "provide it in the request body",
                )

        queue = get_job_queue(settings)

        if stage in (JOB_STAGE_UPLOAD, JOB_STAGE_CHUNKING):
            source_path = load_source_path(job_directory)
            if source_path is None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "original source path is not recorded for this job; "
                    "re-upload the file to retry from this stage",
                )
            enqueue_video_ingest_job(
                queue=queue,
                job_id=job_id,
                source_path=str(source_path),
                language=language,
            )
        elif stage == JOB_STAGE_TRANSCRIPTION:
            enqueue_transcription_job(
                queue=queue,
                job_id=job_id,
                job_directory=str(job_directory),
                language=language,
            )
        elif stage == JOB_STAGE_SUMMARY:
            enqueue_summary_job(
                queue=queue,
                job_id=job_id,
                job_directory=str(job_directory),
            )
        else:
            # Defensive: _STAGE_INDEX check above should make this unreachable.
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"retry not implemented for stage {stage!r}",
            )
    except BaseException:
        # Anything that prevents the re-enqueue (validation error, queue
        # failure, etc.) leaves the job in a failed state again — restore the
        # marker we consumed so the user can retry once the issue is fixed.
        restore_job_failure(job_directory, record=failure)
        raise

    logger.info(
        "Re-enqueued failed job %s at stage %s (language=%s)",
        job_id,
        stage,
        language,
    )
    return _load_job_detail(job_id, job_directory)


__all__ = [
    "router",
    "JobStatus",
    "JobSummary",
    "JobDetail",
    "JobFailure",
    "JobRetryRequest",
    "JobUpdate",
]
