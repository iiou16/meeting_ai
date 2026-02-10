# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MeetingAI は会議動画から自動で文字起こし・要約・アクションアイテム抽出を行うWebアプリケーションです。
- **Backend**: FastAPI + Python 3.11 (音声処理、OpenAI API連携、ジョブキュー)
- **Frontend**: Next.js + TypeScript (App Router、Tailwind CSS)
- **Worker**: RQ + Redis (非同期タスク処理)

## Important

- Be sure to answer in Japanese.
- 現在はこのプログラムは開発中なので、エラーが発生したときに確実にそれを検出する必要があります。フォールバック等の処理でエラーの隠蔽、プログラムが終了しないことを優先した以下の処理は禁止します。
  - `try ... except Exception: pass`、`try ... except Exception: continue` 等のエラーを握りつぶす処理
    - `raise ...` で確実にエラーにしてください。その時には、エラーメッセージ(e)に十分な情報が含まれていることを確認してください。
  - 辞書の値を取得する際に、`dict.get(key)` / `dict.get(key, default_value)`を使うこと
    - 存在しないキーを指定した場合に None が返ってしまい、その後の処理で不具合が発生する可能性があります。必ず `dict[key]` の形式で取得してください。
  - 値が見つからないときにデフォルト値を返す処理
    - 例: `some_list[index] if index < len(some_list) else default_value` 等
    - 存在しない値を使うことはバグの原因になるため、必ずエラーにしてください。

## Common Development Commands

### 起動スクリプト（推奨）
```bash
# Backend 起動 (Redis + RQ Worker + API サーバーを一括起動)
./scripts/start-backend.sh

# Frontend 起動
./scripts/start-frontend.sh
```
`start-backend.sh` は Redis コンテナ（Docker）、RQ Worker、API サーバーをまとめて起動します。
Ctrl+C で終了すると Worker も自動停止します。

### Backend (Python) - 個別コマンド
```bash
# 環境構築とパッケージインストール
cd backend
UV_CACHE_DIR=../.uv-cache uv sync
source .venv/bin/activate

# APIサーバー起動 (開発)
UV_CACHE_DIR=../.uv-cache uv run uvicorn meetingai_backend.app:create_app --factory --reload

# ワーカー起動 (別ターミナル)
UV_CACHE_DIR=../.uv-cache uv run python -m meetingai_backend.worker

# テスト実行
pytest                         # 全テスト
pytest tests/test_health.py    # 特定ファイルのテスト
pytest -k test_create_job      # 特定テスト関数を実行
pytest -v                      # 詳細出力
```

### Frontend (Next.js) - 個別コマンド
```bash
# 環境構築とパッケージインストール
cd frontend
npm_config_cache=../.npm-cache npm install

# 開発サーバー起動
npm run dev

# ビルド
npm run build

# リント
npm run lint

# テスト
npm test                       # 全テスト
npm test -- dashboard          # 特定ファイルのテスト
```

## Architecture Overview

### Backend Structure
```
backend/src/meetingai_backend/
├── app.py                # FastAPI アプリケーションファクトリ
├── settings.py           # 環境設定 (upload_root, redis_url等)
├── jobs.py              # ジョブキュー設定
├── worker.py            # RQワーカー
├── routers/
│   ├── videos.py        # 動画アップロードAPI (/api/videos)
│   ├── jobs.py          # ジョブ状態管理API (/api/jobs)
│   └── meetings.py      # 会議結果取得API (/api/meetings)
├── tasks/
│   ├── ingest.py        # 動画→音声抽出・チャンク分割
│   ├── transcribe.py    # OpenAI GPT-4o Transcribe呼び出し
│   └── summarize.py     # 要約・アクションアイテム抽出
├── media/               # 音声処理 (FFmpeg, チャンク管理)
├── transcription/       # 文字起こし (OpenAI API, segments保存)
└── summarization/       # 要約生成 (OpenAI GPT-4o, プロンプト管理)
```

### Processing Flow
1. **動画アップロード** → `/api/videos` エンドポイントでファイル受信、ジョブID発行
2. **音声抽出** → `tasks.ingest.process_uploaded_video` でFFmpegを使い動画から音声抽出、15分チャンクに分割
3. **文字起こし** → `tasks.transcribe.transcribe_audio_for_job` で各チャンクをOpenAI APIで処理、`TranscriptSegment`として保存
4. **要約生成** → `tasks.summarize.summarize_transcript_for_job` でGPT-4oを使い要約・アクションアイテム生成
5. **結果取得** → Frontend経由で `/api/meetings/{job_id}` から結果を取得・表示

### Key Dependencies & Setup

#### 必須環境変数
```bash
OPENAI_API_KEY=sk-...           # OpenAI APIキー (必須)
MEETINGAI_REDIS_URL=redis://localhost:6379  # Redisサーバー (ジョブキュー用)
MEETINGAI_FFMPEG_PATH=/path/to/ffmpeg      # FFmpegパス (PATHにない場合)
```

#### FFmpeg
音声抽出に必須。未インストールの場合、テストは自動スキップされます。
- macOS: `brew install ffmpeg`
- Windows: 公式サイトからダウンロードしPATHに追加
- Linux: `sudo apt-get install ffmpeg`

#### Redis
ジョブキュー管理に使用。`scripts/start-backend.sh` が Docker コンテナ (`meetingai-redis`) を自動起動します。
手動で起動する場合:
```bash
docker run -d --name meetingai-redis -p 6379:6379 redis:alpine
```

### Data Models
- **Meeting**: ジョブID、タイトル、処理状態、作成日時
- **MediaAsset**: 音声チャンクファイル情報 (パス、開始/終了時間、サンプリング)
- **TranscriptSegment**: 文字起こしセグメント (タイムスタンプ、テキスト)
- **SummaryItem**: セクション要約 (開始/終了時間、要約テキスト)
- **ActionItem**: アクションアイテム (担当者、期日、説明)

### Testing Approach

Backend:
- ユニットテスト: 各モジュール単体の動作確認
- 統合テスト: `test_integration_transcription_flow.py` で実際の動画ファイルを使った全フロー検証
- モック利用: OpenAI API呼び出しはモック化、FFmpeg実行は実環境依存

Frontend:
- コンポーネントテスト: Jest + Testing Library
- レンダリング・イベント処理の確認

### API Endpoints

- `POST /api/videos` - 動画アップロード (multipart/form-data)
- `GET /api/jobs` - ジョブ一覧取得
- `GET /api/jobs/{job_id}` - ジョブ状態取得
- `DELETE /api/jobs/{job_id}` - ジョブ削除
- `GET /api/meetings/{job_id}` - 会議結果取得 (文字起こし・要約)

### Development Notes

- **パッケージ管理**: Backend は `uv` のみ使用 (pip禁止)、Frontend は npm/yarn
- **非同期処理**: ジョブはRedis + RQで管理、長時間処理対応
- **エラーハンドリング**: OpenAI APIレート制限・タイムアウト考慮、リトライ実装済み
- **ファイル管理**: アップロードファイルは `storage/jobs/{job_id}/` に保存
