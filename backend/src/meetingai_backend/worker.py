"""RQ worker entrypoint for processing background jobs."""

from __future__ import annotations

import logging

from redis import Redis
from rq import Queue, Worker

from .settings import get_settings

logger = logging.getLogger(__name__)


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
    )
    worker.work(with_scheduler=True)


__all__ = ["run_worker"]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_worker()
