# Repository Guidelines

## Project Structure & Module Organization

- `backend/` hosts the FastAPI service and worker code under `src/meetingai_backend`, plus `tests/` with unit and integration suites. Reusable scripts (for ad-hoc transcription) live in `backend/scripts/`.
- `frontend/` contains the Next.js app; application code lives in `src/`, static assets in `public/`, and configuration files (e.g., `eslint.config.mjs`, `next.config.ts`) sit at the root.
- `Docs/` tracks specs and planning notes, while `storage/` is a development-only scratch area for uploaded media. Keep generated data out of Git.

## Build, Test, and Development Commands

- Backend setup: `cd backend && UV_CACHE_DIR=../.uv-cache uv sync` then `source .venv/bin/activate`. Use `./dev.sh` to boot API + worker together for local work.
- Backend tests: `cd backend && uv run pytest`. Pass `-k` to target specific suites; integration cases need `ffmpeg` and Redis running (`redis-cli ping` should return `PONG`).
- Frontend workflow: `cd frontend && npm run dev` for hot reload, `npm run build` for production checks, `npm run lint` for ESLint, and `npm run test` to execute Jest.

## Coding Style & Naming Conventions

- Python code follows Black (line length 88) and isort’s Black profile. Use 4-space indentation and descriptive module names (`meetingai_backend.<feature>`). Keep worker tasks under `tasks/` packages.
- TypeScript/React files use Next.js conventions: colocate route handlers under `src/app`, components under `src/components`, and prefer PascalCase for components, camelCase for hooks/utilities. Tailwind utility classes are the default styling approach.

## Testing Guidelines

- Python tests reside in `backend/tests`. Name files `test_<feature>.py`; integration specs (e.g., `test_integration_transcription_flow.py`) verify the end-to-end transcription path and may require sample media in `tests/data/`.
- Frontend tests live beside source in `__tests__` folders or alongside components. Use Testing Library assertions and extend with `@testing-library/jest-dom`. Record new fixtures under `frontend/src/__mocks__` if needed.
- Aim to maintain coverage on critical ingestion and transcription paths; add regression tests when fixing bugs or expanding endpoints/UI flows.

## Commit & Pull Request Guidelines

- Follow Conventional Commit style observed in history (`feat(backend): ...`, `fix(frontend): ...`). Squash minor tidy-ups before pushing.
- Pull requests should include: purpose-driven description, linked issue or spec reference, manual test notes (commands run, screenshots for UI), and call out environment impacts (`.env`, Redis, FFmpeg).
- レビューコメントやPR内での回答は日本語で記載してください（回答は日本語が必須です）。

## Environment & Operations Tips

- Required services: Redis 5+, FFmpeg in `PATH`, and a valid `OPENAI_API_KEY`. Use the repository-level `.env` for local secrets; never commit it.
- When handling uploaded media, keep per-job assets inside `storage/` or temporary directories and purge artifacts after debugging to avoid large diffs.
