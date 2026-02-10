from __future__ import annotations

import logging

import pytest

from meetingai_backend.summarization import (
    OpenAISummarizationConfig,
    build_summary_prompt,
    generate_meeting_summary,
)
from meetingai_backend.summarization.openai import SummarizationError
from meetingai_backend.transcription.segments import TranscriptSegment


def _make_segment(
    *,
    job_id: str,
    order: int,
    start_ms: int,
    end_ms: int,
    text: str,
    language: str | None = "ja",
) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=f"segment-{order}",
        job_id=job_id,
        order=order,
        start_ms=start_ms,
        end_ms=end_ms,
        text=text,
        language=language,
        speaker_label=None,
        source_asset_id="asset-123",
        extra={},
    )


def test_build_summary_prompt_includes_segments() -> None:
    segments = [
        _make_segment(
            job_id="job-1",
            order=0,
            start_ms=0,
            end_ms=60_000,
            text="Project kickoff discussion about roadmap and deliverables.",
        ),
        _make_segment(
            job_id="job-1",
            order=1,
            start_ms=60_000,
            end_ms=120_000,
            text="Open questions on resource planning and dependencies.",
        ),
    ]

    prompt = build_summary_prompt(job_id="job-1", segments=segments)
    assert "job-1" in prompt
    assert "Project kickoff discussion" in prompt
    assert "Open questions on resource planning" in prompt


def test_generate_meeting_summary_parses_payload() -> None:
    segments = [
        _make_segment(
            job_id="job-1",
            order=0,
            start_ms=0,
            end_ms=60_000,
            text="Discussed timeline and assigned responsibilities.",
        ),
        _make_segment(
            job_id="job-1",
            order=1,
            start_ms=60_000,
            end_ms=120_000,
            text="Identified action items and next meeting date.",
        ),
    ]

    def fake_request(*, prompt: str, config: OpenAISummarizationConfig):
        assert "job-1" in prompt
        return {
            "summary_sections": [
                {
                    "summary": "Project timeline confirmed with key milestones.",
                    "start_ms": 0,
                    "end_ms": 60000,
                    "priority": "high",
                },
                {
                    "summary": "Team reviewed outstanding tasks for next sprint.",
                    "start_ms": 60000,
                    "end_ms": 120000,
                    "priority": "medium",
                },
            ],
            "action_items": [
                {
                    "description": "Send updated project plan to stakeholders.",
                    "owner": "Alice",
                    "due_date": "2025-06-01",
                    "start_ms": 60000,
                    "end_ms": 120000,
                }
            ],
            "quality": {"confidence": 0.92},
        }

    config = OpenAISummarizationConfig(api_key="test-key")
    bundle = generate_meeting_summary(
        job_id="job-1",
        segments=segments,
        config=config,
        request_fn=fake_request,
    )

    assert len(bundle.summary_items) == 2
    assert bundle.summary_items[0].summary_text.startswith("Project timeline")
    assert len(bundle.action_items) == 1
    assert bundle.action_items[0].owner == "Alice"
    assert bundle.quality.action_item_count == 1
    assert 0.0 <= bundle.quality.coverage_ratio <= 1.0
    assert bundle.quality.llm_confidence == pytest.approx(0.92)


def test_generate_meeting_summary_invalid_payload_raises() -> None:
    segments = [
        _make_segment(
            job_id="job-1",
            order=0,
            start_ms=0,
            end_ms=30_000,
            text="Short discussion segment.",
        )
    ]

    def invalid_request(*, prompt: str, config: OpenAISummarizationConfig):
        return "not-a-dict"

    config = OpenAISummarizationConfig(api_key="test-key")
    with pytest.raises(SummarizationError):
        generate_meeting_summary(
            job_id="job-1",
            segments=segments,
            config=config,
            request_fn=invalid_request,
        )


class TestSummaryTimestampClamping:
    """サマリーのタイムスタンプがトランスクリプト範囲にクランプされることを検証。"""

    def _make_segments(self) -> list[TranscriptSegment]:
        """0-60000ms, 60000-120000ms の2セグメントを作成。"""
        return [
            _make_segment(
                job_id="job-clamp",
                order=0,
                start_ms=0,
                end_ms=60_000,
                text="First segment.",
            ),
            _make_segment(
                job_id="job-clamp",
                order=1,
                start_ms=60_000,
                end_ms=120_000,
                text="Second segment.",
            ),
        ]

    def test_out_of_range_timestamps_are_clamped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """トランスクリプト範囲外のタイムスタンプがクランプされる。"""
        segments = self._make_segments()

        def fake_request(*, prompt: str, config: OpenAISummarizationConfig):
            return {
                "summary_sections": [
                    {
                        "summary": "Section before transcript range.",
                        "start_ms": -5000,
                        "end_ms": 60000,
                    },
                    {
                        "summary": "Section after transcript range.",
                        "start_ms": 60000,
                        "end_ms": 200000,
                    },
                ],
                "action_items": [
                    {
                        "description": "Action with out-of-range time.",
                        "start_ms": -1000,
                        "end_ms": 300000,
                    }
                ],
            }

        config = OpenAISummarizationConfig(api_key="test-key")
        with caplog.at_level(logging.WARNING):
            bundle = generate_meeting_summary(
                job_id="job-clamp",
                segments=segments,
                config=config,
                request_fn=fake_request,
            )

        # クランプ後の値を検証
        assert bundle.summary_items[0].segment_start_ms == 0
        assert bundle.summary_items[1].segment_end_ms == 120_000

        # 元の値がログに記録されていることを検証
        assert any("-5000" in record.message for record in caplog.records)
        assert any("200000" in record.message for record in caplog.records)

    def test_section_excluded_when_clamped_to_invalid_range(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """クランプ後に end_ms <= start_ms となるセクションは除外される。"""
        segments = self._make_segments()

        def fake_request(*, prompt: str, config: OpenAISummarizationConfig):
            return {
                "summary_sections": [
                    {
                        "summary": "Valid section.",
                        "start_ms": 0,
                        "end_ms": 60000,
                    },
                    {
                        "summary": "Fully out of range section.",
                        "start_ms": 200000,
                        "end_ms": 300000,
                    },
                ],
                "action_items": [],
            }

        config = OpenAISummarizationConfig(api_key="test-key")
        with caplog.at_level(logging.WARNING):
            bundle = generate_meeting_summary(
                job_id="job-clamp",
                segments=segments,
                config=config,
                request_fn=fake_request,
            )

        assert len(bundle.summary_items) == 1
        assert bundle.summary_items[0].summary_text == "Valid section."

    def test_action_item_timestamps_are_clamped(self) -> None:
        """アクションアイテムのタイムスタンプもクランプされる。"""
        segments = self._make_segments()

        def fake_request(*, prompt: str, config: OpenAISummarizationConfig):
            return {
                "summary_sections": [
                    {
                        "summary": "Section.",
                        "start_ms": 0,
                        "end_ms": 120000,
                    }
                ],
                "action_items": [
                    {
                        "description": "Task with negative start.",
                        "start_ms": -500,
                        "end_ms": 60000,
                    },
                    {
                        "description": "Task with end beyond range.",
                        "start_ms": 60000,
                        "end_ms": 999999,
                    },
                ],
            }

        config = OpenAISummarizationConfig(api_key="test-key")
        bundle = generate_meeting_summary(
            job_id="job-clamp",
            segments=segments,
            config=config,
            request_fn=fake_request,
        )

        assert bundle.action_items[0].segment_start_ms == 0
        assert bundle.action_items[1].segment_end_ms == 120_000
