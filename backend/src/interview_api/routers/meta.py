from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..ai import get_ai, get_transcriber
from ..ai.base import InterviewAI, Transcriber
from ..config import get_settings
from ..db import get_db
from ..roles import LEVELS, ROLES
from ..schemas import MetaOut

router = APIRouter(tags=["meta"])


@router.get("/api/health")
@router.get("/health", include_in_schema=False)
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/api/meta", response_model=MetaOut)
def meta(ai: InterviewAI = Depends(get_ai), transcriber: Transcriber = Depends(get_transcriber)):
    s = get_settings()
    return MetaOut(
        roles=ROLES,
        levels=LEVELS,
        min_questions=s.min_questions,
        max_questions=s.max_questions,
        default_questions=s.default_questions,
        max_answer_seconds=s.max_answer_seconds,
        max_audio_bytes=s.max_audio_bytes,
        ai_mode="demo" if ai.model_name.startswith("mock") else "gemini",
        ai_model=ai.model_name,
        transcriber=transcriber.model_name,
    )
