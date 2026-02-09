#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

UV_CACHE_DIR=../.uv-cache uv sync
UV_CACHE_DIR=../.uv-cache uv pip install -e .
UV_CACHE_DIR=../.uv-cache uv run uvicorn meetingai_backend.app:create_app --factory --reload --host 127.0.0.1 --port 8000
