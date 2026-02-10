# MeetingAI Backend

FastAPI ベースの MeetingAI バックエンドです。動画アップロードから音声抽出、OpenAI GPT-4o Transcribe を用いた文字起こし、`TranscriptSegment` への保存までのバックエンド処理が実装されています。ジョブ処理には Redis + RQ が必須です。

## 実装済み機能（フェーズ1）

- `POST /api/videos` 動画アップロード API（multipart 対応、アップロードファイルをジョブディレクトリに保存）
- RQ + Redis を利用したジョブキュー設定 (`meetingai_backend.jobs`)
- 動画から WAV への音声抽出（FFmpeg 呼び出し）
- 長時間対応の音声チャンク分割 (`AudioChunkSpec` / `MediaAsset`)
- OpenAI GPT-4o Transcribe API 呼び出し（リトライとレート制御付き）
- チャンク結果のマージと `TranscriptSegment` 永続化（`transcription/segments.py`）
- ワーカータスク
  - `tasks.ingest.process_uploaded_video`: 動画→音声抽出・チャンク化・メタデータ保存
  - `tasks.transcribe.transcribe_audio_for_job`: チャンクの文字起こし→`TranscriptSegment` 保存
- 実データ（`backend/tests/data/2025-05-23 13-03-45.mov`）を使った統合テスト（FFmpeg が無い環境では自動的に skip）

## アプリケーションの実行

### 事前準備

- Redis を起動しておきます（例: `redis-server`、Docker の場合 `docker run -p 6379:6379 redis:7`）。
- `OPENAI_API_KEY` と `ffmpeg` のパスを設定します（必要に応じて `.env` を利用）。

### 開発用ショートカット

API サーバーとワーカー、必要であれば Redis（ローカルに `redis-server` がある場合）をまとめて起動するスクリプトを用意しています。

```bash
cd backend
./dev.sh
```

### 個別に起動する場合

- API サーバー:
  `UV_CACHE_DIR=../.uv-cache uv run uvicorn meetingai_backend.app:create_app --factory --reload`
- ワーカー:
  `UV_CACHE_DIR=../.uv-cache uv run python -m meetingai_backend.worker`

## テスト

```bash
cd backend
source .venv/bin/activate
pytest
```

テストでは、ユニットテストに加えて統合テスト `test_integration_transcription_flow.py` を実装しています。`backend/tests/data/2025-05-23 13-03-45.mov` をコピーしてジョブディレクトリを構築し、FFmpeg を利用して実際に音声抽出とチャンク生成を行います。`ffmpeg` が見つからない場合は自動的に skip されます。

## 今後の予定（次フェーズ）

- TranscriptSegment をもとにした要約生成やアクションアイテム抽出（フェーズ2）
- Redis/PostgreSQL などインフラ構成の確定と Docker Compose 化
- フロントエンドとの連携（ジョブ状況表示、文字起こし閲覧 UI など）
