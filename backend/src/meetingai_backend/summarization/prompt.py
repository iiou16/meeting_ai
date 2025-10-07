"""Prompt generation utilities for meeting summarization."""

from __future__ import annotations

from typing import Iterable, Sequence

from ..transcription.segments import TranscriptSegment

_DEFAULT_MAX_TOTAL_CHARACTERS = 8000
_DEFAULT_SEGMENT_SNIPPET_LENGTH = 400


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

    lines: list[str] = []
    total = 0

    for segment in segments:
        if not isinstance(segment, TranscriptSegment):
            continue
        if not segment.text.strip():
            continue

        formatted = _format_segment(segment, snippet_length=segment_snippet_length)
        projected_total = total + len(formatted) + 1  # newline
        if projected_total > max_total_characters and lines:
            break

        lines.append(formatted)
        total = projected_total

    transcript_block = "\n".join(lines)
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
        " optional fields `title` and `priority`. Each action item must include"
        " `description`, and may include `owner`, `due_date`, `start_ms`, `end_ms`, and `priority`."
        " Respond strictly with valid JSON. Do not include any additional commentary."
        f"{language_instruction}\n\n"
        f"Job identifier: {job_id}\n"
        "Transcript snippets (timestamps in milliseconds):\n"
        f"{transcript_block}"
    )


__all__ = ["build_summary_prompt"]
