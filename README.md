# MeetingAI プロジェクト概要

MeetingAI は、会議動画から自動で文字起こし・要約・アクションアイテム抽出を行うアプリケーションです。本リポジトリはフロントエンド（Next.js）とバックエンド（FastAPI）、ワーカー処理、ドキュメントで構成されています。

## ディレクトリ構成

- `frontend/` … Next.js + TypeScript ベースのフロントエンド
- `backend/` … FastAPI ベースのバックエンドおよびワーカー処理
- `Docs/` … 仕様書や TODO、開発メモなど
- `storage/` … 開発用のアップロード先など

## 環境構築

### 前提ソフトウェア

- Python 3.11
- [uv](https://github.com/astral-sh/uv)（Python 依存解決・仮想環境管理）
- Node.js 18+（フロントエンド開発時に利用）
- Redis 5+（バックエンドジョブキュー用、オプション）
- FFmpeg（動画→音声抽出で必須）
- OpenAI API キー

### FFmpeg インストール方法

- **macOS**: `brew install ffmpeg`
- **Windows**:
  1. [公式配布サイト](https://ffmpeg.org/download.html) から Windows 用ビルドをダウンロード
  2. 解凍して `ffmpeg.exe` を `C:\ffmpeg\bin` などに配置
  3. 環境変数 `PATH` に `C:\ffmpeg\bin` を追加
- **Ubuntu**:
  - `sudo apt-get update && sudo apt-get install ffmpeg`

`ffmpeg` を PATH に追加できない場合は `.env` などで `MEETINGAI_FFMPEG_PATH=/path/to/ffmpeg` を指定してください。

### Redis インストール方法

ジョブキュー管理に Redis が必要です。

- **macOS**: `brew install redis && brew services start redis`
- **Windows (WSL/Ubuntu)**:
  ```bash
  sudo apt-get update
  sudo apt-get install redis-server
  sudo service redis-server start
  ```
- **Docker** (推奨):
  ```bash
  docker run -d --name redis-meetingai -p 6379:6379 redis:alpine
  ```

Redis が起動していることを確認:
```bash
redis-cli ping  # PONG が返れば正常
```

### OpenAI API キー

`.env` または環境変数で `OPENAI_API_KEY` を設定してください。

```
OPENAI_API_KEY=sk-...
```

## バックエンドのセットアップ例

```bash
cd backend
UV_CACHE_DIR=../.uv-cache uv sync
source .venv/bin/activate
```

詳細な実装内容や起動・テスト方法は `backend/README.md` を参照してください。

## フロントエンドのセットアップ例

```bash
cd frontend
npm_config_cache=../.npm-cache npm install
```

## ドキュメント

- `Docs/spec.md` … 仕様書
- `Docs/task.md` … フェーズ別のTODO管理
- `Docs/development.md` … 開発メモ、コマンド例など
