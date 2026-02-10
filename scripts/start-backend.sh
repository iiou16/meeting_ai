#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# --- .env 読み込み ---
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

cd backend

# --- Docker 起動確認 ---
if ! docker info >/dev/null 2>&1; then
  echo "エラー: Docker が利用できません" >&2
  echo "Docker Desktop を起動してください" >&2
  exit 1
fi

# --- パッケージインストール (Redis チェックに仮想環境の Python を使うため先に実行) ---
# uv sync はプロジェクト自体を非editable(キャッシュwheel)でインストールするため、
# ソース変更が反映されない問題がある。--no-install-project で依存のみインストールし、
# プロジェクト本体は editable install で入れる。
UV_CACHE_DIR=../.uv-cache uv sync --no-install-project
UV_CACHE_DIR=../.uv-cache uv pip install -e .

# --- Redis 起動 ---
REDIS_CONTAINER_NAME="meetingai-redis"
REDIS_PORT="6379"

redis_ping() {
  UV_CACHE_DIR=../.uv-cache uv run python3 -c "
import socket, sys
try:
    s = socket.create_connection(('localhost', ${REDIS_PORT}), timeout=1)
    s.sendall(b'*1\r\n\$4\r\nPING\r\n')
    data = s.recv(1024)
    s.close()
    sys.exit(0 if b'PONG' in data else 1)
except Exception:
    sys.exit(1)
"
}

# まず既存の Redis が応答するか確認 (別プロセスやDocker Desktop経由など)
if redis_ping; then
  echo "Redis はポート ${REDIS_PORT} で既に稼働中です"
elif docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER_NAME}$"; then
  echo "Redis コンテナ '${REDIS_CONTAINER_NAME}' は既に起動中です"
elif docker ps -a --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER_NAME}$"; then
  echo "停止中の Redis コンテナ '${REDIS_CONTAINER_NAME}' を再起動します"
  docker start "${REDIS_CONTAINER_NAME}"
else
  echo "Redis コンテナ '${REDIS_CONTAINER_NAME}' を新規作成します"
  docker run -d --name "${REDIS_CONTAINER_NAME}" -p "${REDIS_PORT}:6379" redis:alpine
fi

# Redis が応答可能になるまで待機
echo "Redis の起動を待機中..."
for i in $(seq 1 30); do
  if redis_ping; then
    echo "Redis が起動しました"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "エラー: Redis の起動がタイムアウトしました" >&2
    exit 1
  fi
  sleep 1
done

# --- RQ Worker 起動 (バックグラウンド) ---
echo "RQ Worker を起動します..."
UV_CACHE_DIR=../.uv-cache uv run python -c "from meetingai_backend.worker import run_worker; run_worker()" &
WORKER_PID=$!
echo "RQ Worker を起動しました (PID: ${WORKER_PID})"

# 終了時に Worker プロセスをクリーンアップ
cleanup() {
  echo ""
  echo "Worker プロセス (PID: ${WORKER_PID}) を停止します..."
  kill "${WORKER_PID}" 2>/dev/null
  wait "${WORKER_PID}" 2>/dev/null
  echo "クリーンアップ完了"
}
trap cleanup EXIT INT TERM

# --- API サーバー起動 (フォアグラウンド) ---
UV_CACHE_DIR=../.uv-cache uv run uvicorn meetingai_backend.app:create_app --factory --reload --host 127.0.0.1 --port 8000
