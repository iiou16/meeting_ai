# 開発環境メモ

## バックエンド (FastAPI + uv)
- 依存関係の解決: `UV_CACHE_DIR=../.uv-cache uv sync`
- 開発サーバー起動: `UV_CACHE_DIR=../.uv-cache uv run uvicorn meetingai_backend.app:create_app --factory --reload`
- ユニットテスト: `source .venv/bin/activate && pytest`（直近確認時 19件すべて成功、実行時はカレントディレクトリを`backend/`にすること）
- バックグラウンドワーカー起動: `UV_CACHE_DIR=../.uv-cache uv run python -m meetingai_backend.worker`
- FFmpegバイナリの確認: `ffmpeg -version`。カスタムパスを使う場合は `MEETINGAI_FFMPEG_PATH` を設定する。
- 動画アップロードAPIは `MEETINGAI_UPLOAD_DIR` 環境変数でアップロードファイルの保存先を変更可能（未指定時は `backend/storage/uploads/` 配下）。
- Redis接続は `MEETINGAI_REDIS_URL` / `MEETINGAI_JOB_QUEUE_NAME` / `MEETINGAI_JOB_TIMEOUT` で調整可能。
- Docker開発イメージ: `docker build -f backend/Dockerfile -t meetingai-backend:dev backend/`。このイメージにはFFmpegが含まれており、そのままワーカー/サーバー実行に利用できる。

## フロントエンド (Next.js)
- 初回セットアップ: `npm_config_cache=../.npm-cache npm install`
- 開発サーバー起動: `npm_config_cache=../.npm-cache npm run dev`
- ユニットテスト: `npm_config_cache=../.npm-cache npm test -- --runInBand`

※ `UV_CACHE_DIR` / `npm_config_cache` はサンドボックス環境でのキャッシュディレクトリ指定です。
