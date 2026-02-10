"""RQ worker entrypoint for processing background jobs."""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from redis import Redis
from rq import Queue, Worker
from rq.job import Job

from .settings import get_settings

logger = logging.getLogger(__name__)


def _on_job_failure(job: Job, typ: type, value: BaseException, tb: Any) -> None:
    """Write an error marker file to the job directory when an RQ job fails."""
    kwargs = job.kwargs or {}
    job_id = kwargs.get("job_id")
    if job_id is None:
        logger.error("Failed job has no job_id in kwargs; cannot write error marker")
        return

    settings = get_settings()
    job_directory = settings.upload_root / job_id
    if not job_directory.exists():
        logger.error("Job directory does not exist: %s", job_directory)
        return

    error_info = {
        "error": str(value),
        "error_type": f"{typ.__module__}.{typ.__qualname__}",
        "traceback": traceback.format_exception(typ, value, tb),
        "failed_at": datetime.now(tz=timezone.utc).isoformat(),
        "rq_job_id": job.id,
    }
    error_path = job_directory / "error.json"
    error_path.write_text(json.dumps(error_info, ensure_ascii=False, indent=2))
    logger.error("Job %s failed: %s", job_id, value)


def run_worker() -> None:
    """Start an RQ worker listening on the configured queue."""
    settings = get_settings()
    connection = Redis.from_url(settings.redis_url)
    queue = Queue(
        settings.job_queue_name,
        connection=connection,
        default_timeout=settings.job_timeout_seconds,
    )

    logger.info(
        "Starting worker; queue=%s redis=%s",
        settings.job_queue_name,
        settings.redis_url,
    )
    worker = Worker(
        [queue],
        name="meetingai-worker",
        connection=connection,
        exception_handlers=[_on_job_failure],
    )
    worker.work(with_scheduler=True)


__all__ = ["run_worker"]
