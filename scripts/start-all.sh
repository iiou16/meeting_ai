#!/usr/bin/env bash
set -euo pipefail

# Backend と Frontend をまとめて起動するスクリプト。
# Ctrl+C で両方のプロセスを安全に停止する。

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
LOG_DIR="${ROOT_DIR}/tmp/logs"
mkdir -p "${LOG_DIR}"

# job control を有効化してバックグラウンドジョブごとに別プロセスグループを作る
# (setsid 相当の挙動。macOS には setsid が無いためこちらを使う)
set -m

BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "[start-all] 子プロセスを停止します..."
  if [ -n "${FRONTEND_PID}" ] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    # プロセスグループ全体に SIGTERM を送る (next dev の子プロセスごと止めるため)
    kill -TERM -"${FRONTEND_PID}" 2>/dev/null || kill -TERM "${FRONTEND_PID}" 2>/dev/null || true
  fi
  if [ -n "${BACKEND_PID}" ] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill -TERM -"${BACKEND_PID}" 2>/dev/null || kill -TERM "${BACKEND_PID}" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  echo "[start-all] 停止完了"
}
trap cleanup EXIT INT TERM

echo "[start-all] Backend を起動します (ログ: ${BACKEND_LOG})"
# ログをファイルと標準出力の両方に流す
( "${ROOT_DIR}/scripts/start-backend.sh" 2>&1 | sed -u 's/^/[backend] /' | tee "${BACKEND_LOG}" ) &
BACKEND_PID=$!

# Backend (uvicorn) が応答するまで待機
echo "[start-all] Backend の起動を待機中..."
for i in $(seq 1 60); do
  if curl -fsS -o /dev/null "http://127.0.0.1:8000/docs" 2>/dev/null \
     || curl -fsS -o /dev/null "http://127.0.0.1:8000/" 2>/dev/null; then
    echo "[start-all] Backend が起動しました"
    break
  fi
  if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    echo "[start-all] エラー: Backend の起動に失敗しました。${BACKEND_LOG} を確認してください" >&2
    exit 1
  fi
  if [ "$i" -eq 60 ]; then
    echo "[start-all] エラー: Backend の起動がタイムアウトしました" >&2
    exit 1
  fi
  sleep 1
done

echo "[start-all] Frontend を起動します (ログ: ${FRONTEND_LOG})"
( "${ROOT_DIR}/scripts/start-frontend.sh" 2>&1 | sed -u 's/^/[frontend] /' | tee "${FRONTEND_LOG}" ) &
FRONTEND_PID=$!

echo ""
echo "[start-all] === 起動完了 ==="
echo "  Backend  : http://127.0.0.1:8000"
echo "  Frontend : http://127.0.0.1:3000"
echo "  Ctrl+C で全プロセスを停止します"
echo ""

# どちらかのプロセスが終了したらスクリプトを終了する
# (macOS の bash 3.2 は `wait -n` をサポートしないためポーリングで実装)
while kill -0 "${BACKEND_PID}" 2>/dev/null && kill -0 "${FRONTEND_PID}" 2>/dev/null; do
  sleep 2
done
