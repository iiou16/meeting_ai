"""Worker tasks for generating meeting summaries and action items."""

from __future__ import annotations

from pathlib import Path

from ..job_state import JOB_STAGE_SUMMARY, clear_job_failure, mark_job_failed
from ..settings import Settings, get_settings
from ..summarization import (
    OpenAISummarizationConfig,
    SummaryRequestFn,
    dump_action_items,
    dump_summary_items,
    dump_summary_quality,
    generate_meeting_summary,
)
from ..transcription.segments import load_transcript_segments


def _build_summary_config(settings: Settings) -> OpenAISummarizationConfig:
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured; cannot run summarization job."
        )

    return OpenAISummarizationConfig(
        api_key=settings.openai_api_key,
        model=settings.openai_summary_model,
        base_url=settings.openai_base_url,
        request_timeout_seconds=settings.openai_summary_request_timeout_seconds,
        max_attempts=settings.openai_summary_max_attempts,
        retry_backoff_seconds=settings.openai_summary_retry_backoff_seconds,
        max_retry_backoff_seconds=settings.openai_summary_max_retry_backoff_seconds,
        temperature=settings.openai_summary_temperature,
        max_output_tokens=settings.openai_summary_max_output_tokens,
        requests_per_minute=settings.openai_summary_requests_per_minute,
        user_agent=settings.openai_user_agent,
    )


def summarize_job(
    *,
    job_id: str,
    job_directory: str,
    request_fn: SummaryRequestFn | None = None,
) -> dict[str, object]:
    """Generate summaries and action items for a processed transcription."""
    job_path = Path(job_directory)
    if not job_path.exists():
        error = FileNotFoundError(f"Job directory does not exist: {job_directory}")
        mark_job_failed(job_path, stage=JOB_STAGE_SUMMARY, error=error)
        raise error

    clear_job_failure(job_path)

    try:
        segments = load_transcript_segments(job_path)
        if not segments:
            raise RuntimeError(
                "Transcription segments are not available; run transcription first."
            )

        settings = get_settings()
        config = _build_summary_config(settings)

        language_hint = next(
            (segment.language for segment in segments if segment.language), None
        )

        bundle = generate_meeting_summary(
            job_id=job_id,
            segments=segments,
            config=config,
            language_hint=language_hint,
            request_fn=request_fn,
        )

        summary_path = dump_summary_items(job_path, bundle.summary_items)
        action_items_path = dump_action_items(job_path, bundle.action_items)
        quality_path = dump_summary_quality(job_path, bundle.quality)

        return {
            "job_id": job_id,
            "summary_count": len(bundle.summary_items),
            "action_item_count": len(bundle.action_items),
            "summary_path": str(summary_path.resolve()),
            "action_items_path": str(action_items_path.resolve()),
            "quality_path": str(quality_path.resolve()),
            "quality_metrics": bundle.quality.to_dict(),
            "model_metadata": dict(bundle.model_metadata),
        }
    except Exception as exc:
        mark_job_failed(job_path, stage=JOB_STAGE_SUMMARY, error=exc)
        raise


__all__ = ["summarize_job"]
