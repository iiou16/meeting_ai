"""OpenAI-powered meeting summarization service."""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

import httpx

from ..transcription.segments import TranscriptSegment
from .models import ActionItem, SummaryBundle, SummaryItem, SummaryQualityMetrics
from .prompt import build_summary_prompt

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenAISummarizationConfig:
    """Configuration for invoking the OpenAI chat completion API."""

    api_key: str
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    request_timeout_seconds: float = 180.0
    max_attempts: int = 3
    retry_backoff_seconds: float = 2.0
    max_retry_backoff_seconds: float | None = 60.0
    temperature: float = 0.2
    max_output_tokens: int = 1200
    requests_per_minute: int | None = None
    user_agent: str | None = "MeetingAI/0.1"

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("api_key must be provided for OpenAI summarization.")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive.")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if self.retry_backoff_seconds <= 0:
            raise ValueError("retry_backoff_seconds must be positive.")
        if (
            self.max_retry_backoff_seconds is not None
            and self.max_retry_backoff_seconds <= 0
        ):
            raise ValueError(
                "max_retry_backoff_seconds must be positive when provided."
            )
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive.")
        if self.requests_per_minute is not None and self.requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive when provided.")


class SummarizationError(RuntimeError):
    """Raised when meeting summarization fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SummaryRequestFn(Protocol):  # pragma: no cover - Protocol runtime helper
    def __call__(
        self, *, prompt: str, config: OpenAISummarizationConfig
    ) -> Mapping[str, Any]: ...


_RETRIABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


def generate_meeting_summary(
    *,
    job_id: str,
    segments: Sequence[TranscriptSegment],
    config: OpenAISummarizationConfig,
    language_hint: str | None = None,
    request_fn: SummaryRequestFn | None = None,
    sleep: Callable[[float], None] | None = None,
) -> SummaryBundle:
    """Generate summary sections and action items for a meeting transcript."""
    if not segments:
        raise RuntimeError("Cannot summarise meeting without transcript segments.")

    prompt = build_summary_prompt(
        job_id=job_id,
        segments=segments,
        language_hint=language_hint,
    )

    caller = request_fn or _call_openai_summary_api
    sleep_fn = sleep or time.sleep

    attempt = 0
    last_exception: Exception | None = None
    while attempt < config.max_attempts:
        attempt += 1
        try:
            raw_payload = caller(prompt=prompt, config=config)
            break
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else None
            if status in _RETRIABLE_STATUS and attempt < config.max_attempts:
                delay = _select_retry_delay(
                    attempt=attempt,
                    config=config,
                    response=exc.response,
                )
                sleep_fn(delay)
                last_exception = exc
                continue
            raise SummarizationError(
                f"Summarization call failed with status {status}",
                status_code=status,
            ) from exc
        except httpx.RequestError as exc:
            if attempt < config.max_attempts:
                delay = _select_retry_delay(
                    attempt=attempt,
                    config=config,
                    response=None,
                )
                sleep_fn(delay)
                last_exception = exc
                continue
            raise SummarizationError(
                "Summarization request failed due to network error",
                status_code=None,
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise SummarizationError(
                "Unexpected error while generating meeting summary"
            ) from exc
    else:
        raise SummarizationError(
            "Exhausted retries while generating meeting summary."
        ) from last_exception

    if not isinstance(raw_payload, Mapping):
        raise SummarizationError("Summarization response must be a mapping.")

    payload = dict(raw_payload)
    model_metadata = dict(payload.pop("_metadata", {}) or {})
    for key in ("quality", "notes"):
        if key in payload and key not in model_metadata:
            model_metadata[key] = payload[key]

    transcript_start_ms = min(seg.start_ms for seg in segments)
    transcript_end_ms = max(seg.end_ms for seg in segments)

    if "summary_sections" in payload:
        summary_sections_raw = payload["summary_sections"]
    else:
        logger.warning("LLM response missing 'summary_sections' key for job %s", job_id)
        summary_sections_raw = []

    if "action_items" in payload:
        action_items_raw = payload["action_items"]
    else:
        logger.warning("LLM response missing 'action_items' key for job %s", job_id)
        action_items_raw = []

    summary_items = _parse_summary_sections(
        summary_sections_raw,
        job_id=job_id,
        transcript_start_ms=transcript_start_ms,
        transcript_end_ms=transcript_end_ms,
    )
    action_items = _parse_action_items(
        action_items_raw,
        job_id=job_id,
        starting_order=len(summary_items),
        transcript_start_ms=transcript_start_ms,
        transcript_end_ms=transcript_end_ms,
    )

    quality = _evaluate_quality_metrics(
        segments=segments,
        summary_items=summary_items,
        action_items=action_items,
        model_metadata=model_metadata,
    )

    return SummaryBundle(
        summary_items=summary_items,
        action_items=action_items,
        quality=quality,
        model_metadata=model_metadata,
    )


def _call_openai_summary_api(
    *,
    prompt: str,
    config: OpenAISummarizationConfig,
) -> Mapping[str, Any]:
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
    }
    if config.user_agent:
        headers["User-Agent"] = config.user_agent

    payload = {
        "model": config.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI that summarises meeting transcripts."
                    " Always respond with valid JSON matching the requested schema."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": config.temperature,
        "response_format": {"type": "json_object"},
        "max_tokens": config.max_output_tokens,
    }

    response = httpx.post(
        url,
        headers=headers,
        json=payload,
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, Mapping):
        raise SummarizationError("Unexpected response payload from OpenAI.")

    content = _extract_message_content(data)
    summary_payload = _decode_summary_json(content)
    summary_payload["_metadata"] = {
        "id": data.get("id"),
        "model": data.get("model"),
        "usage": data.get("usage"),
    }
    return summary_payload


def _extract_message_content(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise SummarizationError("OpenAI response did not include any choices.")

    message = choices[0].get("message")
    if isinstance(message, Mapping):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            joined = "".join(
                chunk.get("text", "")
                for chunk in content
                if isinstance(chunk, Mapping) and isinstance(chunk.get("text"), str)
            )
            if joined:
                return joined
    raise SummarizationError("OpenAI response missing textual content.")


def _decode_summary_json(content: str) -> dict[str, Any]:
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError as exc:
        raise SummarizationError("Model returned invalid JSON content.") from exc

    if not isinstance(decoded, dict):
        raise SummarizationError("Decoded summary payload must be a JSON object.")
    return decoded


def _parse_summary_sections(
    sections: Any,
    *,
    job_id: str,
    transcript_start_ms: int,
    transcript_end_ms: int,
) -> list[SummaryItem]:
    if not isinstance(sections, Sequence):
        return []

    parsed: list[SummaryItem] = []
    for index, entry in enumerate(sections):
        if not isinstance(entry, Mapping):
            continue

        summary_text = (
            entry["summary"]
            if "summary" in entry
            else (entry["text"] if "text" in entry else None)
        )
        if not isinstance(summary_text, str) or not summary_text.strip():
            continue

        start_ms = _extract_time_value(
            entry,
            keys=("start_ms", "start", "segment_start_ms", "segment_start"),
        )
        end_ms = _extract_time_value(
            entry,
            keys=("end_ms", "end", "segment_end_ms", "segment_end"),
        )
        if start_ms is None or end_ms is None or end_ms <= start_ms:
            continue

        # Clamp timestamps to transcript range.
        clamped_start = max(start_ms, transcript_start_ms)
        clamped_end = min(end_ms, transcript_end_ms)

        if clamped_start != start_ms or clamped_end != end_ms:
            logger.warning(
                "Summary section %d timestamps out of transcript range "
                "[%d, %d]: start_ms=%d -> %d, end_ms=%d -> %d",
                index,
                transcript_start_ms,
                transcript_end_ms,
                start_ms,
                clamped_start,
                end_ms,
                clamped_end,
            )

        if clamped_end <= clamped_start:
            logger.warning(
                "Summary section %d excluded: clamped range [%d, %d] is invalid "
                "(original [%d, %d])",
                index,
                clamped_start,
                clamped_end,
                start_ms,
                end_ms,
            )
            continue

        highlights = entry["highlights"] if "highlights" in entry else None
        if isinstance(highlights, Sequence) and not isinstance(
            highlights, (str, bytes)
        ):
            normalized_highlights = [
                str(item) for item in highlights if isinstance(item, (str, int, float))
            ]
        else:
            normalized_highlights = []

        title = str(entry["title"]) if "title" in entry and entry["title"] else None
        priority = (
            str(entry["priority"])
            if "priority" in entry and entry["priority"]
            else None
        )

        parsed.append(
            SummaryItem.create(
                job_id=job_id,
                order=len(parsed),
                segment_start_ms=clamped_start,
                segment_end_ms=clamped_end,
                summary_text=summary_text.strip(),
                heading=title,
                priority=priority,
                highlights=normalized_highlights,
            )
        )
    return parsed


def _parse_action_items(
    items: Any,
    *,
    job_id: str,
    starting_order: int,
    transcript_start_ms: int,
    transcript_end_ms: int,
) -> list[ActionItem]:
    if not isinstance(items, Sequence):
        return []

    parsed: list[ActionItem] = []
    for index, entry in enumerate(items):
        if not isinstance(entry, Mapping):
            continue

        description = (
            entry["description"]
            if "description" in entry
            else (entry["text"] if "text" in entry else None)
        )
        if not isinstance(description, str) or not description.strip():
            continue

        segment_start = _extract_time_value(
            entry,
            keys=("start_ms", "start", "segment_start_ms", "segment_start"),
        )
        segment_end = _extract_time_value(
            entry,
            keys=("end_ms", "end", "segment_end_ms", "segment_end"),
        )

        # Clamp timestamps to transcript range.
        if segment_start is not None:
            clamped_start = max(segment_start, transcript_start_ms)
            if clamped_start != segment_start:
                logger.warning(
                    "Action item %d start_ms out of range: %d -> %d",
                    index,
                    segment_start,
                    clamped_start,
                )
            segment_start = clamped_start
        if segment_end is not None:
            clamped_end = min(segment_end, transcript_end_ms)
            if clamped_end != segment_end:
                logger.warning(
                    "Action item %d end_ms out of range: %d -> %d",
                    index,
                    segment_end,
                    clamped_end,
                )
            segment_end = clamped_end

        if (
            segment_start is not None
            and segment_end is not None
            and segment_end <= segment_start
        ):
            logger.warning(
                "Action item %d excluded: clamped range [%d, %d] is invalid",
                index,
                segment_start,
                segment_end,
            )
            continue

        owner = str(entry["owner"]) if "owner" in entry and entry["owner"] else None
        due_date = (
            str(entry["due_date"])
            if "due_date" in entry and entry["due_date"]
            else None
        )
        priority = (
            str(entry["priority"])
            if "priority" in entry and entry["priority"]
            else None
        )

        parsed.append(
            ActionItem.create(
                job_id=job_id,
                order=starting_order + len(parsed),
                description=description.strip(),
                owner=owner,
                due_date=due_date,
                segment_start_ms=segment_start,
                segment_end_ms=segment_end,
                priority=priority,
            )
        )
    return parsed


def _evaluate_quality_metrics(
    *,
    segments: Sequence[TranscriptSegment],
    summary_items: Sequence[SummaryItem],
    action_items: Sequence[ActionItem],
    model_metadata: Mapping[str, Any],
) -> SummaryQualityMetrics:
    if not segments:
        return SummaryQualityMetrics(
            coverage_ratio=0.0,
            referenced_segments_ratio=0.0,
            average_summary_word_count=0.0,
            action_item_count=len(action_items),
            llm_confidence=_extract_llm_confidence(model_metadata),
        )

    total_duration = max(segment.end_ms for segment in segments) - min(
        segment.start_ms for segment in segments
    )
    total_duration = max(total_duration, 1)

    coverage_ranges: list[tuple[int, int]] = []
    referenced_orders: set[int] = set()

    for item in summary_items:
        start = max(item.segment_start_ms, segments[0].start_ms)
        end = min(item.segment_end_ms, segments[-1].end_ms)
        if end > start:
            coverage_ranges.append((start, end))

        for segment in segments:
            if segment.order in referenced_orders:
                continue
            if _spans_overlap(
                (item.segment_start_ms, item.segment_end_ms),
                (segment.start_ms, segment.end_ms),
            ):
                referenced_orders.add(segment.order)

    coverage_ratio = _calculate_coverage_ratio(coverage_ranges, total_duration)
    if segments:
        referenced_segments_ratio = len(referenced_orders) / len(segments)
    else:
        referenced_segments_ratio = 0.0

    average_word_count = (
        sum(_word_count(item.summary_text) for item in summary_items)
        / len(summary_items)
        if summary_items
        else 0.0
    )

    return SummaryQualityMetrics(
        coverage_ratio=round(coverage_ratio, 3),
        referenced_segments_ratio=round(referenced_segments_ratio, 3),
        average_summary_word_count=round(average_word_count, 2),
        action_item_count=len(action_items),
        llm_confidence=_extract_llm_confidence(model_metadata),
    )


def _calculate_coverage_ratio(
    ranges: Sequence[tuple[int, int]], total_duration: int
) -> float:
    if not ranges:
        return 0.0

    merged = []
    for start, end in sorted(ranges, key=lambda item: item[0]):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    covered = sum(end - start for start, end in merged)
    ratio = covered / total_duration if total_duration > 0 else 0.0
    return min(1.0, max(0.0, ratio))


def _spans_overlap(
    span_a: tuple[int, int | None],
    span_b: tuple[int, int | None],
) -> bool:
    start_a, end_a = span_a
    start_b, end_b = span_b
    if end_a is None or end_b is None:
        return False
    return max(start_a, start_b) < min(end_a, end_b)


def _word_count(text: str) -> int:
    return len([token for token in text.strip().split() if token])


def _coerce_milliseconds(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(math.floor(value))
    if isinstance(value, str):
        stripped = value.strip().lower()
        if not stripped:
            return None
        if stripped.endswith("ms"):
            stripped = stripped[:-2]
        multiplier = 1
        if stripped.endswith("s"):
            stripped = stripped[:-1]
            multiplier = 1000
        try:
            numeric = float(stripped)
        except ValueError:
            return None
        return int(math.floor(numeric * multiplier))
    return None


def _extract_time_value(entry: Mapping[str, Any], keys: Sequence[str]) -> int | None:
    for key in keys:
        if key in entry:
            coerced = _coerce_milliseconds(entry[key])
            if coerced is not None:
                return coerced
    return None


def _extract_llm_confidence(metadata: Mapping[str, Any]) -> float | None:
    quality = metadata.get("quality")
    if isinstance(quality, Mapping):
        confidence = quality.get("confidence")
        if isinstance(confidence, (int, float)):
            return float(confidence)
        if isinstance(confidence, str):
            try:
                return float(confidence)
            except ValueError:
                return None
    score = metadata.get("confidence")
    if isinstance(score, (int, float)):
        return float(score)
    return None


def _select_retry_delay(
    *,
    attempt: int,
    config: OpenAISummarizationConfig,
    response: httpx.Response | None,
) -> float:
    base_delay = config.retry_backoff_seconds * (2 ** (attempt - 1))
    retry_after = None
    if response is not None:
        retry_after = _parse_retry_after_seconds(response.headers)
    delay = base_delay
    if retry_after is not None:
        delay = max(delay, retry_after)
    if config.max_retry_backoff_seconds is not None:
        delay = min(delay, config.max_retry_backoff_seconds)
    return delay


def _parse_retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    raw = headers.get("Retry-After")
    if not raw:
        return None
    value = raw.strip()
    try:
        seconds = float(value)
    except ValueError:
        return None
    if seconds < 0:
        return None
    return seconds


__all__ = [
    "OpenAISummarizationConfig",
    "SummaryRequestFn",
    "SummarizationError",
    "generate_meeting_summary",
]
