"""Transcription helpers and OpenAI integrations."""

from .openai import (
    ChunkTranscriptionResult,
    OpenAITranscriptionConfig,
    TranscriptionError,
    transcribe_audio_chunks,
)
from .segments import (
    TranscriptSegment,
    dump_transcript_segments,
    load_transcript_segments,
    merge_chunk_transcriptions,
)

__all__ = [
    "ChunkTranscriptionResult",
    "TranscriptSegment",
    "OpenAITranscriptionConfig",
    "TranscriptionError",
    "dump_transcript_segments",
    "load_transcript_segments",
    "merge_chunk_transcriptions",
    "transcribe_audio_chunks",
]
