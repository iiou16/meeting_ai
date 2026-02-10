"""RQ worker entrypoint for processing background jobs."""

from __future__ import annotations

import logging
import traceback
from typing import Any

from redis import Redis
from rq import Queue, Worker
from rq.job import Job

from .job_state import mark_job_failed
from .settings import get_settings

logger = logging.getLogger(__name__)


def _on_job_failure(job: Job, typ: type, value: BaseException, tb: Any) -> None:
    """Write a failure marker to the job directory when an RQ job fails."""
    kwargs = job.kwargs
    if kwargs is None:
        logger.error("Failed job has no kwargs; cannot write error marker")
        return
    job_id = kwargs["job_id"]

    settings = get_settings()
    job_directory = settings.upload_root / job_id
    if not job_directory.exists():
        logger.error("Job directory does not exist: %s", job_directory)
        return

    mark_job_failed(
        job_directory,
        stage="rq_worker",
        error=str(value),
        details={
            "error_type": f"{typ.__module__}.{typ.__qualname__}",
            "traceback": traceback.format_exception(typ, value, tb),
            "rq_job_id": job.id,
        },
    )
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
        queues=[queue],
        connection=connection,
        name="meetingai-worker",
        exception_handlers=[_on_job_failure],
    )
    worker.work(with_scheduler=True)


__all__ = ["run_worker"]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_worker()
