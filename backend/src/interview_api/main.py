"""FastAPI app. Run with `uvicorn interview_api.main:app`."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .ai import get_transcriber
from .ai.base import AIError
from .config import get_settings
from .routers import auth, interviews, meta, progress

log = logging.getLogger("interview_api")


def _warm_up() -> None:
    t = get_transcriber()
    if hasattr(t, "warm_up"):
        try:
            t.warm_up()
            log.info("Whisper model loaded: %s", t.model_name)
        except Exception:  # never block start-up; the first answer will retry the load
            log.exception("Whisper warm-up failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().warm_up_transcriber:
        threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(
    title="AI Mock Interview API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.exception_handler(AIError)
async def _ai_error(request: Request, exc: AIError) -> JSONResponse:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    log.warning("AI error on %s: %s", request.url.path, exc)
    return JSONResponse({"detail": str(exc)}, status_code=exc.status, headers=headers)


for r in (meta.router, auth.router, interviews.router, progress.router):
    app.include_router(r)
