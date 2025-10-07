# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS base

ENV UV_CACHE_DIR=/tmp/.uv-cache \
    PATH="/root/.local/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md /app/
RUN uv sync --frozen

COPY src /app/src
COPY tests /app/tests

RUN mkdir -p /app/storage/uploads

ENV PYTHONPATH=/app/src \
    MEETINGAI_UPLOAD_DIR=/app/storage/uploads

CMD ["uv", "run", "uvicorn", "meetingai_backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
