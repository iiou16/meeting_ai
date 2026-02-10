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

# --- パッケージインストール (Redis チェックに仮想環境の Python を使うため先に実行) ---
UV_CACHE_DIR=../.uv-cache uv sync

# --- Redis 起動 ---
REDIS_CONTAINER_NAME="meetingai-redis"
REDIS_PORT="6379"
REDIS_SERVER_PID=""

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

start_redis_docker() {
  if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    return 1
  fi

  if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER_NAME}$"; then
    echo "Redis コンテナ '${REDIS_CONTAINER_NAME}' は既に起動中です"
  elif docker ps -a --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER_NAME}$"; then
    echo "停止中の Redis コンテナ '${REDIS_CONTAINER_NAME}' を再起動します"
    docker start "${REDIS_CONTAINER_NAME}"
  else
    echo "Redis コンテナ '${REDIS_CONTAINER_NAME}' を新規作成します"
    docker run -d --name "${REDIS_CONTAINER_NAME}" -p "${REDIS_PORT}:6379" redis:alpine
  fi
  return 0
}

start_redis_server() {
  if ! command -v redis-server >/dev/null 2>&1; then
    return 1
  fi

  echo "redis-server をバックグラウンドで起動します (ポート: ${REDIS_PORT})..."
  redis-server --port "${REDIS_PORT}" --daemonize no &
  REDIS_SERVER_PID=$!
  return 0
}

# 1. 既に Redis が応答中ならそのまま使う
if redis_ping; then
  echo "Redis はポート ${REDIS_PORT} で既に稼働中です"
# 2. Docker が利用可能なら Docker コンテナで起動
elif start_redis_docker; then
  :
# 3. redis-server コマンドがあれば直接起動
elif start_redis_server; then
  :
else
  echo "エラー: Redis を起動できませんでした" >&2
  echo "以下のいずれかの方法で Redis をインストールしてください:" >&2
  echo "  - Linux (apt):   sudo apt-get install redis-server" >&2
  echo "  - Linux (yum):   sudo yum install redis" >&2
  echo "  - macOS (brew):  brew install redis" >&2
  echo "  - Docker:        docker / podman をインストール" >&2
  exit 1
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

# 終了時にプロセスをクリーンアップ
cleanup() {
  echo ""
  echo "Worker プロセス (PID: ${WORKER_PID}) を停止します..."
  kill "${WORKER_PID}" 2>/dev/null
  wait "${WORKER_PID}" 2>/dev/null
  if [ -n "${REDIS_SERVER_PID}" ]; then
    echo "redis-server (PID: ${REDIS_SERVER_PID}) を停止します..."
    kill "${REDIS_SERVER_PID}" 2>/dev/null
    wait "${REDIS_SERVER_PID}" 2>/dev/null
  fi
  echo "クリーンアップ完了"
}
trap cleanup EXIT INT TERM

# --- API サーバー起動 (フォアグラウンド) ---
UV_CACHE_DIR=../.uv-cache uv run uvicorn meetingai_backend.app:create_app --factory --reload --host 127.0.0.1 --port 8000
