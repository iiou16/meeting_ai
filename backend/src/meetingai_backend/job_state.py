"""Helpers for tracking job-level state (failure markers, titles, etc.)."""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

JOB_STAGE_UPLOAD = "upload"
JOB_STAGE_CHUNKING = "chunking"
JOB_STAGE_TRANSCRIPTION = "transcription"
JOB_STAGE_SUMMARY = "summary"

_FAILURE_FILENAME = "job_failed.json"
_TITLE_FILENAME = "job_title.json"
_RECORDED_AT_FILENAME = "job_recorded_at.json"


@dataclass(slots=True)
class JobFailureRecord:
    """Serialized representation of a failed job stage."""

    stage: str
    message: str
    occurred_at: datetime
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "message": self.message,
            "occurred_at": self.occurred_at.isoformat(),
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobFailureRecord":
        occurred_at_raw = payload["occurred_at"]
        if not isinstance(occurred_at_raw, str):
            raise TypeError(
                f"occurred_at must be a string, got {type(occurred_at_raw).__name__}"
            )
        occurred_at = datetime.fromisoformat(occurred_at_raw)

        # "details" was added after the initial release; old records on
        # disk may not contain this key.
        if "details" in payload:
            details = payload["details"]
            if not isinstance(details, dict):
                raise TypeError(f"details must be a dict, got {type(details).__name__}")
        else:
            details = {}

        return cls(
            stage=str(payload["stage"]),
            message=str(payload["message"]),
            occurred_at=occurred_at,
            details=details,
        )


def mark_job_failed(
    job_directory: Path,
    *,
    stage: str,
    error: Exception | str,
    details: dict[str, Any] | None = None,
) -> Path:
    """Persist a failure marker for the given job directory."""

    job_directory.mkdir(parents=True, exist_ok=True)
    message = str(error)
    record = JobFailureRecord(
        stage=stage,
        message=message,
        occurred_at=datetime.now(timezone.utc),
        details=dict(details or {}),
    )

    path = job_directory / _FAILURE_FILENAME
    path.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def clear_job_failure(job_directory: Path) -> None:
    """Remove any persisted failure marker for the job."""

    path = job_directory / _FAILURE_FILENAME
    if path.exists():
        path.unlink()


def load_job_failure(job_directory: Path) -> JobFailureRecord | None:
    """Return the persisted failure record, if any."""

    path = job_directory / _FAILURE_FILENAME
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read job failure record at %s: %s", path, exc)
        raise

    if not isinstance(payload, dict):
        return None
    return JobFailureRecord.from_dict(payload)


def save_job_title(job_directory: Path, *, title: str) -> Path:
    """Persist a user-chosen title for the job (atomic write)."""
    job_directory.mkdir(parents=True, exist_ok=True)
    path = job_directory / _TITLE_FILENAME
    content = json.dumps({"title": title}, ensure_ascii=False, indent=2)
    fd = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=job_directory,
        suffix=".tmp",
        delete=False,
    )
    try:
        fd.write(content)
        fd.flush()
        fd.close()
        Path(fd.name).replace(path)
    except BaseException:
        Path(fd.name).unlink(missing_ok=True)
        raise
    return path


def load_job_title(job_directory: Path) -> str | None:
    """Return the persisted title, or *None* if no title has been set."""
    path = job_directory / _TITLE_FILENAME
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read job title at %s: %s", path, exc)
        raise

    if not isinstance(payload, dict):
        raise ValueError(f"Expected dict in {path}, got {type(payload).__name__}")
    return str(payload["title"])


def save_recorded_at(job_directory: Path, *, recorded_at: datetime) -> Path:
    """Persist the recording timestamp for the job (atomic write)."""
    job_directory.mkdir(parents=True, exist_ok=True)
    path = job_directory / _RECORDED_AT_FILENAME
    content = json.dumps(
        {"recorded_at": recorded_at.isoformat()}, ensure_ascii=False, indent=2
    )
    fd = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=job_directory,
        suffix=".tmp",
        delete=False,
    )
    try:
        fd.write(content)
        fd.flush()
        fd.close()
        Path(fd.name).replace(path)
    except BaseException:
        Path(fd.name).unlink(missing_ok=True)
        raise
    return path


def load_recorded_at(job_directory: Path) -> datetime | None:
    """Return the persisted recording timestamp, or *None* if not set."""
    path = job_directory / _RECORDED_AT_FILENAME
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read recorded_at at %s: %s", path, exc)
        raise

    if not isinstance(payload, dict):
        raise ValueError(f"Expected dict in {path}, got {type(payload).__name__}")
    recorded_at_raw = payload["recorded_at"]
    if not isinstance(recorded_at_raw, str):
        raise TypeError(
            f"recorded_at must be a string, got {type(recorded_at_raw).__name__}"
        )
    return datetime.fromisoformat(recorded_at_raw)


__all__ = [
    "JOB_STAGE_UPLOAD",
    "JOB_STAGE_CHUNKING",
    "JOB_STAGE_TRANSCRIPTION",
    "JOB_STAGE_SUMMARY",
    "JobFailureRecord",
    "clear_job_failure",
    "load_job_failure",
    "load_job_title",
    "load_recorded_at",
    "mark_job_failed",
    "save_job_title",
    "save_recorded_at",
]
