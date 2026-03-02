"""Unit tests for the Markdown rendering module."""

from __future__ import annotations

from meetingai_backend.markdown import format_timestamp, render_meeting_markdown
from meetingai_backend.summarization.models import ActionItem, SummaryItem
from meetingai_backend.transcription.segments import TranscriptSegment


class TestFormatTimestamp:
    def test_zero(self) -> None:
        assert format_timestamp(0) == "00:00"

    def test_seconds_only(self) -> None:
        assert format_timestamp(5_000) == "00:05"

    def test_minutes_and_seconds(self) -> None:
        assert format_timestamp(125_000) == "02:05"

    def test_one_hour(self) -> None:
        assert format_timestamp(3_661_000) == "1:01:01"

    def test_large_value(self) -> None:
        assert format_timestamp(7_200_000) == "2:00:00"


def _make_summary(
    *,
    job_id: str = "job-1",
    order: int = 0,
    start_ms: int = 0,
    end_ms: int = 60_000,
    text: str = "Summary text.",
    heading: str | None = None,
    priority: str | None = None,
    highlights: list[str] | None = None,
) -> SummaryItem:
    return SummaryItem.create(
        job_id=job_id,
        order=order,
        segment_start_ms=start_ms,
        segment_end_ms=end_ms,
        summary_text=text,
        heading=heading,
        priority=priority,
        highlights=highlights,
    )


def _make_action(
    *,
    job_id: str = "job-1",
    order: int = 0,
    description: str = "Do something.",
    owner: str | None = None,
    due_date: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> ActionItem:
    return ActionItem.create(
        job_id=job_id,
        order=order,
        description=description,
        owner=owner,
        due_date=due_date,
        segment_start_ms=start_ms,
        segment_end_ms=end_ms,
    )


def _make_segment(
    *,
    job_id: str = "job-1",
    order: int = 0,
    start_ms: int = 0,
    end_ms: int = 30_000,
    text: str = "Hello.",
    speaker_label: str | None = None,
) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=f"seg-{order}",
        job_id=job_id,
        order=order,
        start_ms=start_ms,
        end_ms=end_ms,
        text=text,
        language="ja",
        speaker_label=speaker_label,
        source_asset_id="asset-1",
        extra={},
    )


class TestRenderMeetingMarkdown:
    def test_header_contains_title_and_job_id(self) -> None:
        md = render_meeting_markdown(
            job_id="job-123",
            title="Weekly Standup",
            summary_items=[],
            action_items=[],
            segments=[],
        )
        assert md.startswith("# Weekly Standup")
        assert "**Job ID**: job-123" in md

    def test_header_falls_back_to_job_id_when_no_title(self) -> None:
        md = render_meeting_markdown(
            job_id="job-456",
            title=None,
            summary_items=[],
            action_items=[],
            segments=[],
        )
        assert md.startswith("# job-456")

    def test_summary_section(self) -> None:
        items = [
            _make_summary(
                heading="Introduction",
                text="We discussed goals.",
                priority="High",
                highlights=["Goal sharing", "Confirmation"],
            ),
        ]
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=items,
            action_items=[],
            segments=[],
        )
        assert "### Introduction (00:00 - 01:00)" in md
        assert "We discussed goals." in md
        assert "**Priority**: High" in md
        assert "- Goal sharing" in md
        assert "- Confirmation" in md

    def test_action_items_table(self) -> None:
        actions = [
            _make_action(
                description="Share doc",
                owner="Alice",
                due_date="2025-06-01",
                start_ms=0,
                end_ms=60_000,
            ),
        ]
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=actions,
            segments=[],
        )
        assert "| 1 | Share doc | Alice | 2025-06-01 | 00:00-01:00 |" in md

    def test_action_items_pipe_escape(self) -> None:
        actions = [
            _make_action(description="A | B", owner="X | Y"),
        ]
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=actions,
            segments=[],
        )
        assert "A \\| B" in md
        assert "X \\| Y" in md

    def test_action_items_missing_optional_fields(self) -> None:
        actions = [
            _make_action(description="Task"),
        ]
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=actions,
            segments=[],
        )
        assert "| 1 | Task | - | - | - |" in md

    def test_transcript_section(self) -> None:
        segments = [
            _make_segment(text="Good morning.", speaker_label="Host"),
            _make_segment(order=1, start_ms=90_000, text="Let's begin."),
        ]
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=[],
            segments=segments,
        )
        assert "**[00:00]** Host: Good morning." in md
        assert "**[01:30]** Let's begin." in md

    def test_empty_meeting(self) -> None:
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=[],
            segments=[],
        )
        assert "No summary items." in md
        assert "No action items." in md
        assert "No transcript segments." in md

    def test_exported_timestamp_present(self) -> None:
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=[],
            segments=[],
        )
        assert "**Exported**:" in md


class TestSpeakerMappingsInMarkdown:
    def _make_mappings(self) -> "SpeakerMappings":
        from meetingai_backend.job_state import SpeakerMappings, SpeakerProfile

        return SpeakerMappings(
            profiles={
                "p1": SpeakerProfile("p1", "Alice", "Engineering"),
                "p2": SpeakerProfile("p2", "Bob", "Sales"),
            },
            label_to_profile={
                "Speaker A": "p1",
                "Speaker C": "p1",
                "Speaker B": "p2",
            },
        )

    def test_transcript_uses_resolved_names(self) -> None:
        segments = [
            _make_segment(text="Hello.", speaker_label="Speaker A"),
            _make_segment(
                order=1, start_ms=30_000, text="Hi.", speaker_label="Speaker B"
            ),
        ]
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=[],
            segments=segments,
            speaker_mappings=self._make_mappings(),
        )
        assert "**[00:00]** Alice: Hello." in md
        assert "**[00:30]** Bob: Hi." in md

    def test_merged_label_resolves_to_same_name(self) -> None:
        segments = [
            _make_segment(text="One.", speaker_label="Speaker C"),
        ]
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=[],
            segments=segments,
            speaker_mappings=self._make_mappings(),
        )
        assert "**[00:00]** Alice: One." in md

    def test_unmapped_label_uses_raw_label(self) -> None:
        segments = [
            _make_segment(text="Two.", speaker_label="Speaker Z"),
        ]
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=[],
            segments=segments,
            speaker_mappings=self._make_mappings(),
        )
        assert "**[00:00]** Speaker Z: Two." in md

    def test_speaker_table_rendered(self) -> None:
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=[],
            segments=[],
            speaker_mappings=self._make_mappings(),
        )
        assert "## Speakers" in md
        assert "| Alice |" in md
        assert "| Bob |" in md

    def test_no_speaker_table_without_mappings(self) -> None:
        md = render_meeting_markdown(
            job_id="job-1",
            title=None,
            summary_items=[],
            action_items=[],
            segments=[],
        )
        assert "## Speakers" not in md
