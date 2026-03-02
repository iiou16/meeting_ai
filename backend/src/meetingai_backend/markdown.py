"""Render meeting artefacts as a Markdown document."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from .job_state import SpeakerMappings
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


def _resolve_speaker(
    label: str | None,
    mappings: SpeakerMappings | None,
) -> str:
    """Return the display name for a speaker label."""
    if not label:
        return ""
    if mappings is not None:
        profile = mappings.resolve_label(label)
        if profile is not None:
            return profile.name
    return label


def _render_speaker_table(
    mappings: SpeakerMappings,
) -> list[str]:
    """Render a Markdown table listing all speaker profiles."""
    lines: list[str] = []
    lines.append("## Speakers")
    lines.append("")
    lines.append("| Name | Organization | Labels |")
    lines.append("|------|-------------|--------|")

    # Group labels by profile_id
    profile_labels: dict[str, list[str]] = {}
    for label, pid in mappings.label_to_profile.items():
        labels_list = profile_labels.setdefault(pid, [])
        labels_list.append(label)

    for pid, labels in profile_labels.items():
        profile = mappings.profiles[pid]
        name = _escape_pipe(profile.name)
        org = _escape_pipe(profile.organization) if profile.organization else "-"
        labels_str = _escape_pipe(", ".join(sorted(labels)))
        lines.append(f"| {name} | {org} | {labels_str} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def render_meeting_markdown(
    *,
    job_id: str,
    title: str | None,
    summary_items: Sequence[SummaryItem],
    action_items: Sequence[ActionItem],
    segments: Sequence[TranscriptSegment],
    speaker_mappings: SpeakerMappings | None = None,
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

    # --- Speaker Table ---
    if speaker_mappings is not None and speaker_mappings.profiles:
        lines.extend(_render_speaker_table(speaker_mappings))

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
            speaker_name = _resolve_speaker(segment.speaker_label, speaker_mappings)
            speaker = f" {speaker_name}:" if speaker_name else ""
            lines.append(f"**[{ts}]**{speaker} {segment.text}")
            lines.append("")

    return "\n".join(lines)
