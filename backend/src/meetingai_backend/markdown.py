"""Render meeting artefacts as a Markdown document."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from .summarization.models import ActionItem, SummaryItem
from .transcription.segments import TranscriptSegment


def format_timestamp(ms: int) -> str:
    """Format milliseconds as ``MM:SS`` or ``H:MM:SS``."""
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _escape_pipe(text: str) -> str:
    """Escape pipe characters for use inside Markdown table cells."""
    return text.replace("|", "\\|")


def render_meeting_markdown(
    *,
    job_id: str,
    title: str | None,
    summary_items: Sequence[SummaryItem],
    action_items: Sequence[ActionItem],
    segments: Sequence[TranscriptSegment],
) -> str:
    """Return a full Markdown report for the given meeting artefacts."""
    lines: list[str] = []

    # --- Header ---
    heading = title if title else job_id
    lines.append(f"# {heading}")
    lines.append("")
    lines.append(f"**Job ID**: {job_id}")
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"**Exported**: {now_utc}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Timestamped Summaries ---
    lines.append("## Timestamped Summaries")
    lines.append("")

    if not summary_items:
        lines.append("No summary items.")
        lines.append("")
    else:
        for item in summary_items:
            ts_range = (
                f"{format_timestamp(item.segment_start_ms)} - "
                f"{format_timestamp(item.segment_end_ms)}"
            )
            heading_text = item.heading if item.heading else "Summary"
            lines.append(f"### {heading_text} ({ts_range})")
            lines.append("")
            lines.append(item.summary_text)
            lines.append("")
            if item.priority:
                lines.append(f"**Priority**: {item.priority}")
                lines.append("")
            if item.highlights:
                lines.append("**Highlights**:")
                for hl in item.highlights:
                    lines.append(f"- {hl}")
                lines.append("")

    lines.append("---")
    lines.append("")

    # --- Action Items ---
    lines.append("## Action Items")
    lines.append("")

    if not action_items:
        lines.append("No action items.")
        lines.append("")
    else:
        lines.append("| # | Description | Owner | Due | Timespan |")
        lines.append("|---|-------------|-------|-----|----------|")
        for idx, item in enumerate(action_items, start=1):
            desc = _escape_pipe(item.description)
            owner = _escape_pipe(item.owner) if item.owner else "-"
            due = item.due_date if item.due_date else "-"
            if item.segment_start_ms is not None and item.segment_end_ms is not None:
                timespan = (
                    f"{format_timestamp(item.segment_start_ms)}-"
                    f"{format_timestamp(item.segment_end_ms)}"
                )
            else:
                timespan = "-"
            lines.append(f"| {idx} | {desc} | {owner} | {due} | {timespan} |")
        lines.append("")

    lines.append("---")
    lines.append("")

    # --- Full Transcript ---
    lines.append("## Full Transcript")
    lines.append("")

    if not segments:
        lines.append("No transcript segments.")
        lines.append("")
    else:
        for segment in segments:
            ts = format_timestamp(segment.start_ms)
            speaker = f" {segment.speaker_label}:" if segment.speaker_label else ""
            lines.append(f"**[{ts}]**{speaker} {segment.text}")
            lines.append("")

    return "\n".join(lines)
