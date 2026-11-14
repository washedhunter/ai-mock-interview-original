# Backend: FastAPI + faster-whisper (CPU). The Whisper model is downloaded at build time so the
# container starts without network access to Hugging Face.
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev
COPY alembic.ini ./
COPY alembic ./alembic

# Space-separated faster-whisper models to bake in (empty = none, e.g. for TRANSCRIBER=groq/mock).
# /app/audio is only written when KEEP_AUDIO=true (compose mounts a volume there).
RUN useradd --create-home --uid 10001 app && mkdir -p /models /app/audio && chown app /models /app/audio
USER app

ARG WHISPER_PRELOAD="base.en"
ENV WHISPER_DOWNLOAD_ROOT=/models HF_HUB_DISABLE_TELEMETRY=1
RUN if [ -n "$WHISPER_PRELOAD" ]; then interview-api download-model $WHISPER_PRELOAD; fi
ENV HF_HUB_OFFLINE=1

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=4)"
# One worker: the rate limiter and the Whisper model live in process memory.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn interview_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
