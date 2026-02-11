"""Worker tasks for transcribing audio chunks and persisting transcript segments."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Iterable

from ..job_state import JOB_STAGE_TRANSCRIPTION, clear_job_failure, mark_job_failed
from ..jobs import enqueue_summary_job, get_job_queue
from ..media import MediaAsset, load_media_assets
from ..settings import Settings, get_settings
from ..transcription import (
    OpenAITranscriptionConfig,
    dump_transcript_segments,
    merge_chunk_transcriptions,
    transcribe_audio_chunks,
)
from ..transcription.openai import ChunkRequestFn

logger = logging.getLogger(__name__)


def _build_transcription_config(settings: Settings) -> OpenAITranscriptionConfig:
    """Translate project settings into an OpenAI transcription configuration."""
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured; cannot run transcription job."
        )

    return OpenAITranscriptionConfig(
        api_key=settings.openai_api_key,
        model=settings.openai_transcription_model,
        base_url=settings.openai_base_url,
        request_timeout_seconds=settings.openai_request_timeout_seconds,
        max_attempts=settings.openai_max_attempts,
        retry_backoff_seconds=settings.openai_retry_backoff_seconds,
        max_retry_backoff_seconds=settings.openai_max_retry_backoff_seconds,
        requests_per_minute=settings.openai_requests_per_minute,
        user_agent=settings.openai_user_agent,
        max_concurrent_requests=settings.openai_max_concurrent_requests,
    )


def _filter_audio_chunk_assets(assets: Iterable[MediaAsset]) -> list[MediaAsset]:
    """Return audio chunk assets ordered by the original chunk order."""
    chunk_assets = [asset for asset in assets if asset.kind == "audio_chunk"]
    return sorted(chunk_assets, key=lambda asset: asset.order)


def transcribe_audio_for_job(
    *,
    job_id: str,
    job_directory: str,
    language: str | None = None,
    prompt: str | None = None,
    request_fn: ChunkRequestFn | None = None,
    sleep: Callable[[float], None] | None = None,
) -> dict[str, object]:
    """Transcribe the prepared audio chunks for the given job and store transcript segments."""
    job_path = Path(job_directory)
    if not job_path.exists():
        error = FileNotFoundError(f"job directory does not exist: {job_directory}")
        mark_job_failed(job_path, stage=JOB_STAGE_TRANSCRIPTION, error=error)
        raise error

    clear_job_failure(job_path)

    settings = get_settings()
    sleep_fn = sleep or time.sleep

    try:
        config = _build_transcription_config(settings)
        assets = load_media_assets(job_path)
        chunk_assets = _filter_audio_chunk_assets(assets)
        if not chunk_assets:
            raise RuntimeError("no audio chunk assets found; cannot run transcription.")

        chunk_results = transcribe_audio_chunks(
            chunk_assets,
            config=config,
            language=language,
            prompt=prompt,
            request_fn=request_fn,
            sleep=sleep_fn,
        )

        segments = merge_chunk_transcriptions(
            job_id=job_id, chunk_results=chunk_results
        )
        segments_path = dump_transcript_segments(job_path, segments)

        languages = sorted(
            {segment.language for segment in segments if segment.language}
        )
    except Exception as exc:
        mark_job_failed(job_path, stage=JOB_STAGE_TRANSCRIPTION, error=exc)
        raise

    try:
        queue = get_job_queue(settings)
        enqueue_summary_job(
            queue=queue,
            job_id=job_id,
            job_directory=str(job_path),
        )
    except Exception as exc:
        logger.exception(
            "Failed to enqueue summary job",
            extra={"job_id": job_id, "job_directory": str(job_path)},
        )
        mark_job_failed(job_path, stage=JOB_STAGE_TRANSCRIPTION, error=exc)
        raise

    return {
        "job_id": job_id,
        "chunk_count": len(chunk_assets),
        "segment_count": len(segments),
        "segments_path": str(segments_path.resolve()),
        "languages": languages,
    }


__all__ = ["transcribe_audio_for_job"]
