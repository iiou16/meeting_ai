#!/usr/bin/env bash
set -euo pipefail

# Simple development launcher for the MeetingAI backend.
# - Ensures Redis is available (starts a local instance if possible)
# - Starts the FastAPI server via uvicorn (uv)
# - Starts the background worker (RQ)
# Stop everything with Ctrl+C.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV_BIN="${UV_BIN:-uv}"
UV_CACHE_DIR="${UV_CACHE_DIR:-$PROJECT_ROOT/../.uv-cache}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
REDIS_URL="${MEETINGAI_REDIS_URL:-redis://localhost:6379/0}"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/../.env}"

API_PID=""
WORKER_PID=""
REDIS_PID=""

log() {
  printf '[dev] %s\n' "$*" >&2
}

command -v "$UV_BIN" >/dev/null 2>&1 || {
  log "uv command not found. Install with: pip install uv (https://github.com/astral-sh/uv)"
  exit 1
}

ensure_redis() {
  if command -v redis-cli >/dev/null 2>&1; then
    if redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
      log "Redis already running at $REDIS_URL"
      return
    fi
  fi

  if command -v redis-server >/dev/null 2>&1; then
    log "Starting local redis-server..."
    redis-server --save "" --appendonly no >/tmp/meetingai-redis.log 2>&1 &
    REDIS_PID=$!
    sleep 0.3
    if command -v redis-cli >/dev/null 2>&1; then
      if ! redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
        log "Failed to start redis-server (check /tmp/meetingai-redis.log)"
        exit 1
      fi
    fi
  else
    log "Redis is not running and redis-server command was not found."
    log "Start Redis manually or install it before launching the backend."
    exit 1
  fi
}

cleanup() {
  local code=$?
  if [[ -n "$API_PID" ]]; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$WORKER_PID" ]]; then
    kill "$WORKER_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$REDIS_PID" ]]; then
    log "Stopping local redis-server (pid=$REDIS_PID)"
    kill "$REDIS_PID" >/dev/null 2>&1 || true
  fi
  wait >/dev/null 2>&1 || true
  exit $code
}

handle_sigint() {
  log "Interrupt received, shutting down…"
  cleanup
}

trap cleanup EXIT
trap handle_sigint INT TERM

log "Preparing backend environment..."
cd "$PROJECT_ROOT"
export PYTHONPATH=src
export UV_CACHE_DIR

if [[ -f "$ENV_FILE" ]]; then
  log "Loading environment variables from $ENV_FILE"
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

ensure_redis

log "Starting FastAPI server on http://$API_HOST:$API_PORT"
"$UV_BIN" run uvicorn meetingai_backend.app:create_app --factory --host "$API_HOST" --port "$API_PORT" --reload &
API_PID=$!

log "Starting background worker"
"$UV_BIN" run python -m meetingai_backend.worker &
WORKER_PID=$!

log "Backend services running. Press Ctrl+C to stop."

wait "$API_PID" "$WORKER_PID"
