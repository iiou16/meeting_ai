"""RQ worker entrypoint for processing background jobs."""

from __future__ import annotations

import logging
import traceback
from typing import Any

from redis import Redis
from rq import Queue, Worker
from rq.job import Job

from .job_state import (
    JOB_STAGE_SUMMARY,
    JOB_STAGE_TRANSCRIPTION,
    JOB_STAGE_UPLOAD,
    load_job_failure,
    mark_job_failed,
)
from .settings import Settings, get_settings

logger = logging.getLogger(__name__)


_JOB_FUNC_TO_STAGE: dict[str, str] = {
    "process_uploaded_video": JOB_STAGE_UPLOAD,
    "transcribe_audio_for_job": JOB_STAGE_TRANSCRIPTION,
    "summarize_job": JOB_STAGE_SUMMARY,
    "summarize_transcript_for_job": JOB_STAGE_SUMMARY,
}


def _infer_stage_from_job(job: Job) -> str:
    """ジョブ関数名からステージを推定する。"""
    func_name = job.func_name.rsplit(".", 1)[-1] if job.func_name else ""
    return _JOB_FUNC_TO_STAGE.get(func_name, JOB_STAGE_UPLOAD)


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

    # タスク側で既に失敗記録が書かれている場合はステージを維持する。
    existing = load_job_failure(job_directory)
    if existing is not None:
        logger.error("Job %s failed: %s", job_id, value)
        return

    # タスク側で失敗記録が書かれなかった場合、ジョブ関数名からステージを推定する。
    stage = _infer_stage_from_job(job)

    mark_job_failed(
        job_directory,
        stage=stage,
        error=str(value),
        details={
            "error_type": f"{typ.__module__}.{typ.__qualname__}",
            "traceback": traceback.format_exception(typ, value, tb),
            "rq_job_id": job.id,
        },
    )
    logger.error("Job %s failed: %s", job_id, value)


def _validate_settings(settings: Settings) -> None:
    """ワーカー起動前に必須設定を検証する。不足があれば起動を中止する。"""
    missing: list[str] = []
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeError(
            f"必須環境変数が未設定です: {', '.join(missing)}。"
            f".envファイルまたは環境変数で設定してください。"
        )


def run_worker() -> None:
    """Start an RQ worker listening on the configured queue."""
    settings = get_settings()
    _validate_settings(settings)
    connection = Redis.from_url(settings.redis_url)
    queue = Queue(
        settings.job_queue_name,
        connection=connection,
        default_timeout=settings.job_timeout_seconds,
    )

    # 前回のワーカーが強制終了された場合、Redisに登録が残っている可能性がある。
    # 同名のstaleなワーカー登録をRedisから直接削除してから起動する。
    worker_name = "meetingai-worker"
    worker_key = f"rq:worker:{worker_name}"
    if connection.exists(worker_key):
        logger.info("Removing stale worker registration from Redis: %s", worker_key)
        connection.srem("rq:workers", worker_key)
        connection.delete(worker_key)

    logger.info(
        "Starting worker; queue=%s redis=%s",
        settings.job_queue_name,
        settings.redis_url,
    )
    worker = Worker(
        queues=[queue],
        connection=connection,
        name=worker_name,
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
