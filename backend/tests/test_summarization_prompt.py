"""Tests for meetingai_backend.summarization.prompt module."""

from __future__ import annotations

import pytest

from meetingai_backend.summarization.prompt import _format_segment, build_summary_prompt
from meetingai_backend.transcription.segments import TranscriptSegment


def _make_segment(
    *,
    order: int = 0,
    start_ms: int = 0,
    end_ms: int = 60_000,
    text: str = "Hello world",
    language: str | None = "ja",
) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=f"seg-{order}",
        job_id="job-1",
        order=order,
        start_ms=start_ms,
        end_ms=end_ms,
        text=text,
        language=language,
    )


# ---------- TestFormatSegment ----------


class TestFormatSegment:
    def test_basic_formatting(self) -> None:
        seg = _make_segment(start_ms=1000, end_ms=5000, text="Hello world")
        result = _format_segment(seg, snippet_length=1600)
        assert result == "[1000-5000] Hello world"

    def test_newlines_replaced_with_spaces(self) -> None:
        seg = _make_segment(text="line one\nline two\nline three")
        result = _format_segment(seg, snippet_length=1600)
        assert "\n" not in result
        assert "line one line two line three" in result

    def test_long_text_truncated_with_ellipsis(self) -> None:
        long_text = "a" * 200
        seg = _make_segment(start_ms=0, end_ms=1000, text=long_text)
        result = _format_segment(seg, snippet_length=50)
        assert result.endswith("...")
        # Format: "[0-1000] " (10 chars) + 50 truncated chars + "..."
        assert result == f"[0-1000] {'a' * 50}..."

    def test_text_at_exact_snippet_length_not_truncated(self) -> None:
        exact_text = "b" * 50
        seg = _make_segment(start_ms=0, end_ms=1000, text=exact_text)
        result = _format_segment(seg, snippet_length=50)
        assert "..." not in result
        assert result == f"[0-1000] {exact_text}"

    def test_whitespace_stripped(self) -> None:
        seg = _make_segment(text="  padded text  \n")
        result = _format_segment(seg, snippet_length=1600)
        assert "padded text" in result
        assert not result.endswith(" ")


# ---------- TestBuildSummaryPrompt ----------


class TestBuildSummaryPrompt:
    def test_empty_segments_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            build_summary_prompt(job_id="j1", segments=[])

    def test_whitespace_only_segments_raises_value_error(self) -> None:
        seg = _make_segment(text="   \n  ")
        with pytest.raises(ValueError, match="at least one"):
            build_summary_prompt(job_id="j1", segments=[seg])

    def test_non_iterable_segments_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="iterable"):
            build_summary_prompt(job_id="j1", segments=42)  # type: ignore[arg-type]

    def test_non_transcript_segment_items_filtered_out(self) -> None:
        valid = _make_segment(text="valid text")
        mixed = [valid, "not a segment", 123, None]  # type: ignore[list-item]
        prompt = build_summary_prompt(job_id="j1", segments=mixed)
        assert "valid text" in prompt

    def test_language_hint_included_in_prompt(self) -> None:
        seg = _make_segment()
        prompt = build_summary_prompt(
            job_id="j1", segments=[seg], language_hint="Japanese"
        )
        assert "Japanese" in prompt

    def test_no_language_hint_uses_transcript_language(self) -> None:
        seg = _make_segment()
        prompt = build_summary_prompt(job_id="j1", segments=[seg], language_hint=None)
        assert "same language as the transcript" in prompt

    def test_no_truncation_omits_note(self) -> None:
        seg = _make_segment(text="short text")
        prompt = build_summary_prompt(
            job_id="j1",
            segments=[seg],
            max_total_characters=200_000,
        )
        assert "[NOTE:" not in prompt

    def test_truncation_adds_note_with_timestamps(self) -> None:
        segments = [
            _make_segment(
                order=i,
                start_ms=i * 60_000,
                end_ms=(i + 1) * 60_000,
                text="x" * 500,
            )
            for i in range(50)
        ]
        prompt = build_summary_prompt(
            job_id="j1",
            segments=segments,
            max_total_characters=1000,
        )
        assert "[NOTE: Showing" in prompt
        # Should contain first_start (0ms) and last_end (3000000ms)
        assert "0ms" in prompt
        assert "3000000ms" in prompt

    def test_first_segment_always_included_even_with_tiny_budget(self) -> None:
        seg = _make_segment(text="This must appear")
        prompt = build_summary_prompt(
            job_id="j1",
            segments=[seg],
            max_total_characters=1,
        )
        assert "This must appear" in prompt

    def test_section_count_clamped_to_min(self) -> None:
        short_seg = _make_segment(start_ms=0, end_ms=60_000, text="short meeting")
        prompt = build_summary_prompt(job_id="j1", segments=[short_seg])
        assert "around 3 summary sections" in prompt

    def test_section_count_clamped_to_max(self) -> None:
        long_segments = [
            _make_segment(
                order=i,
                start_ms=i * 60_000,
                end_ms=(i + 1) * 60_000,
                text=f"segment {i} content here",
            )
            for i in range(200)
        ]
        prompt = build_summary_prompt(job_id="j1", segments=long_segments)
        assert "around 16 summary sections" in prompt

    def test_job_id_included_in_prompt(self) -> None:
        seg = _make_segment(text="content")
        prompt = build_summary_prompt(job_id="my-special-job", segments=[seg])
        assert "my-special-job" in prompt

    def test_exact_budget_boundary_does_not_truncate(self) -> None:
        """projected_total == max_total_characters should NOT trigger truncation."""
        seg = _make_segment(start_ms=0, end_ms=1000, text="abc")
        # Format: "[0-1000] abc" = 12 chars + 1 newline = 13
        formatted = _format_segment(seg, snippet_length=1600)
        exact_budget = len(formatted) + 1  # +1 for newline accounting
        prompt = build_summary_prompt(
            job_id="j1",
            segments=[seg],
            max_total_characters=exact_budget,
        )
        assert "[NOTE:" not in prompt
        assert "abc" in prompt

    def test_one_over_budget_truncates_second_segment(self) -> None:
        """When adding the 2nd segment would exceed max_total_characters, truncate."""
        seg1 = _make_segment(order=0, start_ms=0, end_ms=1000, text="ALPHA_SEG")
        seg2 = _make_segment(order=1, start_ms=1000, end_ms=2000, text="BRAVO_SEG")
        formatted1 = _format_segment(seg1, snippet_length=1600)
        formatted2 = _format_segment(seg2, snippet_length=1600)
        # projected_total for seg2 = (len(f1)+1) + len(f2) + 1
        # Set budget so that projected_total for seg2 is exactly budget+1 → truncation
        budget = len(formatted1) + 1 + len(formatted2)  # seg2's projected = budget + 1
        prompt = build_summary_prompt(
            job_id="j1",
            segments=[seg1, seg2],
            max_total_characters=budget,
        )
        assert "ALPHA_SEG" in prompt
        assert "BRAVO_SEG" not in prompt
        assert "[NOTE: Showing 1/2" in prompt

    def test_both_fit_when_budget_covers_all_newlines(self) -> None:
        """When budget covers both segments including all newline accounting, no truncation."""
        seg1 = _make_segment(order=0, start_ms=0, end_ms=1000, text="ALPHA_SEG")
        seg2 = _make_segment(order=1, start_ms=1000, end_ms=2000, text="BRAVO_SEG")
        formatted1 = _format_segment(seg1, snippet_length=1600)
        formatted2 = _format_segment(seg2, snippet_length=1600)
        # projected_total for seg2 = (len(f1)+1) + len(f2) + 1
        budget = len(formatted1) + 1 + len(formatted2) + 1  # exactly matches
        prompt = build_summary_prompt(
            job_id="j1",
            segments=[seg1, seg2],
            max_total_characters=budget,
        )
        assert "ALPHA_SEG" in prompt
        assert "BRAVO_SEG" in prompt
        assert "[NOTE:" not in prompt

    def test_explicit_segment_snippet_length(self) -> None:
        """Custom segment_snippet_length should control text truncation in prompt."""
        long_text = "a" * 200
        seg = _make_segment(text=long_text)
        prompt = build_summary_prompt(
            job_id="j1",
            segments=[seg],
            segment_snippet_length=30,
        )
        # The segment text in prompt should be truncated at 30 chars + "..."
        assert "a" * 30 + "..." in prompt
        assert "a" * 31 not in prompt

    def test_empty_language_hint_uses_transcript_language(self) -> None:
        """Empty string language_hint is falsy, so should use transcript language."""
        seg = _make_segment()
        prompt = build_summary_prompt(job_id="j1", segments=[seg], language_hint="")
        assert "same language as the transcript" in prompt

    def test_truncated_prompt_uses_full_meeting_duration_for_sections(self) -> None:
        """target_sections should be computed from ALL segments, not just displayed ones."""
        # 200 minutes meeting → round(200/7) = 29, clamped to max 16
        segments = [
            _make_segment(
                order=i,
                start_ms=i * 60_000,
                end_ms=(i + 1) * 60_000,
                text="X" * 500,
            )
            for i in range(200)
        ]
        prompt = build_summary_prompt(
            job_id="j1",
            segments=segments,
            max_total_characters=1000,
        )
        # Even though only a few snippets are shown, sections should use full 200 min
        assert "[NOTE:" in prompt
        assert "around 16 summary sections" in prompt
        assert "approximately 200.0 minutes" in prompt

    def test_out_of_order_segments_compute_correct_duration(self) -> None:
        """min/max should correctly compute meeting span regardless of segment order."""
        seg_late = _make_segment(order=0, start_ms=120_000, end_ms=180_000, text="late")
        seg_early = _make_segment(order=1, start_ms=0, end_ms=60_000, text="early")
        prompt = build_summary_prompt(
            job_id="j1",
            segments=[seg_late, seg_early],
        )
        # Duration should be 0ms to 180000ms = 3 minutes
        assert "approximately 3.0 minutes" in prompt

    def test_snippet_length_zero_still_produces_output(self) -> None:
        """snippet_length=0 should truncate all text but not crash."""
        seg = _make_segment(text="some text here")
        result = _format_segment(seg, snippet_length=0)
        assert result.startswith("[")
        assert "..." in result
