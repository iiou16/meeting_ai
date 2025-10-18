"""Prompt generation utilities for meeting summarization."""

from __future__ import annotations

from typing import Iterable, Sequence

from ..transcription.segments import TranscriptSegment

_DEFAULT_MAX_TOTAL_CHARACTERS = 20000
_DEFAULT_SEGMENT_SNIPPET_LENGTH = 1600
_DEFAULT_MAX_SECTION_SPAN_MS = 300_000
_DEFAULT_MIN_SUMMARY_SECTIONS = 6
_DEFAULT_MAX_SUMMARY_SECTIONS = 32


def _format_segment(segment: TranscriptSegment, *, snippet_length: int) -> str:
    text = segment.text.strip().replace("\n", " ")
    if len(text) > snippet_length:
        text = f"{text[:snippet_length].rstrip()}..."
    return f"[{segment.start_ms}-{segment.end_ms}] {text}"


def build_summary_prompt(
    *,
    job_id: str,
    segments: Sequence[TranscriptSegment],
    language_hint: str | None = None,
    max_total_characters: int = _DEFAULT_MAX_TOTAL_CHARACTERS,
    segment_snippet_length: int = _DEFAULT_SEGMENT_SNIPPET_LENGTH,
) -> str:
    """Create a compact instruction prompt for the LLM summarization call."""
    if not isinstance(segments, Iterable):
        raise TypeError("segments must be an iterable of TranscriptSegment")

    valid_segments: list[TranscriptSegment] = []
    lines: list[str] = []
    total = 0

    for segment in segments:
        if not isinstance(segment, TranscriptSegment):
            continue
        if not segment.text.strip():
            continue

        valid_segments.append(segment)

        formatted = _format_segment(segment, snippet_length=segment_snippet_length)
        projected_total = total + len(formatted) + 1  # newline
        if projected_total > max_total_characters and lines:
            break

        lines.append(formatted)
        total = projected_total

    if not valid_segments:
        raise ValueError(
            "segments must contain at least one TranscriptSegment with text"
        )

    transcript_block = "\n".join(lines)

    first_start = min(segment.start_ms for segment in valid_segments)
    last_end = max(segment.end_ms for segment in valid_segments)
    meeting_duration_ms = max(1, last_end - first_start)
    meeting_duration_minutes = meeting_duration_ms / 60000

    target_sections = (
        round(meeting_duration_minutes / 3)
        if meeting_duration_minutes > 0
        else _DEFAULT_MIN_SUMMARY_SECTIONS
    )
    target_sections = max(
        _DEFAULT_MIN_SUMMARY_SECTIONS,
        min(_DEFAULT_MAX_SUMMARY_SECTIONS, target_sections),
    )

    pacing_instruction = (
        f" This meeting lasts approximately {meeting_duration_minutes:.1f} minutes."
        f" Produce around {target_sections} summary sections, allowing a deviation of up to two sections if needed."
        f" Each summary section must focus on a single discussion thread and the span between start_ms and end_ms"
        f" must not exceed {_DEFAULT_MAX_SECTION_SPAN_MS} milliseconds."
        " Include concrete facts, decisions, blockers, and owners."
    )
    if language_hint:
        language_instruction = (
            f" The source language is predominantly {language_hint}."
            f" Keep every textual field (summaries, titles, highlights, action items, owners, due dates)"
            f" in {language_hint} without translating."
        )
    else:
        language_instruction = " Maintain the language used in the transcript snippets for every textual field."

    return (
        "You are an expert meeting summarization assistant. "
        "Given transcript snippets with millisecond timestamps, provide a structured JSON"
        " response that contains two arrays: `summary_sections` and `action_items`."
        " Each summary section must include `summary`, `start_ms`, `end_ms`, and may include"
        " optional fields `title`, `highlights` (1-3 short bullet strings), and `priority`. Each action item must include"
        " `description`, and may include `owner`, `due_date`, `start_ms`, `end_ms`, and `priority`."
        " Start times and end times should align with the transcript context you are summarising."
        f"{pacing_instruction}"
        " Respond strictly with valid JSON. Do not include any additional commentary."
        f"{language_instruction}\n\n"
        f"Job identifier: {job_id}\n"
        "Transcript snippets (timestamps in milliseconds):\n"
        f"{transcript_block}"
    )


__all__ = ["build_summary_prompt"]
