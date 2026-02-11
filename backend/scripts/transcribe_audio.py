"""CLI utility to run the transcription pipeline for a standalone audio file."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Sequence

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from meetingai_backend.media import AudioExtractionConfig, extract_audio
from meetingai_backend.media.chunking import AudioChunkSpec, split_audio_into_chunks
from meetingai_backend.settings import get_settings
from meetingai_backend.transcription import (
    OpenAITranscriptionConfig,
    merge_chunk_transcriptions,
    transcribe_audio_chunks,
)


def _load_dotenv_if_needed() -> None:
    dotenv_path = PROJECT_ROOT / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        cleaned = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, cleaned)


def _build_transcription_config(settings) -> OpenAITranscriptionConfig:
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured; cannot run transcription job."
        )

    return OpenAITranscriptionConfig(
        api_key=settings.openai_api_key,
        model=settings.openai_transcription_model,
        base_url=settings.openai_base_url,
        request_timeout_seconds=settings.openai_request_timeout_seconds,
        max_attempts=settings.openai_max_attempts,
        retry_backoff_seconds=settings.openai_retry_backoff_seconds,
        max_retry_backoff_seconds=settings.openai_max_retry_backoff_seconds,
        requests_per_minute=settings.openai_requests_per_minute,
        user_agent=settings.openai_user_agent,
    )


def _ensure_audio(input_path: Path, *, temp_dir: Path) -> Path:
    if input_path.suffix.lower() == ".mp3" and input_path.exists():
        destination = temp_dir / input_path.name
        shutil.copy2(input_path, destination)
        return destination

    settings = get_settings()
    config = AudioExtractionConfig(ffmpeg_path=settings.ffmpeg_path)
    return extract_audio(input_path, output_dir=temp_dir, config=config)


def _chunk_audio(job_id: str, audio_path: Path) -> Sequence[AudioChunkSpec]:
    settings = get_settings()
    return split_audio_into_chunks(
        audio_path,
        job_id=job_id,
        parent_asset_id=None,
        output_dir=audio_path.parent / "chunks",
        ffmpeg_path=settings.ffmpeg_path,
    )


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run MeetingAI transcription on a standalone audio or video file.",
    )
    parser.add_argument("audio", type=Path, help="Path to the source audio/video file")
    parser.add_argument(
        "--job-id",
        type=str,
        default=None,
        help="Optional job identifier. Defaults to a generated UUID.",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Optional language hint passed to the transcription API.",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Optional prompt hint passed to the transcription API.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the transcript segments as JSON.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _create_parser()
    args = parser.parse_args(argv)

    source_path: Path = args.audio.resolve()
    if not source_path.exists():
        parser.error(f"source file does not exist: {source_path}")

    job_id = args.job_id or uuid.uuid4().hex

    _load_dotenv_if_needed()
    settings = get_settings()
    config = _build_transcription_config(settings)

    with tempfile.TemporaryDirectory(prefix="meetingai_transcribe_") as tmp_dir:
        temp_dir = Path(tmp_dir)
        audio_path = _ensure_audio(source_path, temp_dir=temp_dir)
        chunk_specs = list(_chunk_audio(job_id, audio_path))

        if not chunk_specs:
            raise RuntimeError("chunking pipeline produced no audio chunks.")

        chunk_assets = [spec.asset for spec in chunk_specs]

        results = transcribe_audio_chunks(
            chunk_assets,
            config=config,
            language=args.language,
            prompt=args.prompt,
        )

        segments = merge_chunk_transcriptions(job_id=job_id, chunk_results=results)
        payload = [segment.to_dict() for segment in segments]

        output_text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output_text, encoding="utf-8")
        else:
            sys.stdout.write(output_text + "\n")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
