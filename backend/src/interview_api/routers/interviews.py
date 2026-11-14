from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..ai import get_ai, get_transcriber
from ..ai.base import AIError, InterviewAI, QuestionContext, ScoredItem, Transcriber
from ..ai.transcribe import probe_duration
from ..auth import current_user
from ..clarity import compute_clarity
from ..config import get_settings
from ..db import get_db
from ..models import Answer, Interview, Question, User
from ..ratelimit import limiter
from ..roles import LEVELS, ROLES
from ..schemas import (
    AnswerOut,
    InterviewCreate,
    InterviewOut,
    InterviewSummaryOut,
    QuestionOut,
)
from ..scoring import combine, mean

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interviews", tags=["interviews"])

AUDIO_SUFFIX = {
    "audio/webm": ".webm",
    "video/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "video/mp4": ".mp4",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
}


# ---- helpers ------------------------------------------------------------------------------------
def _own_interview(db: Session, user: User, interview_id: uuid.UUID) -> Interview:
    """Load an interview of the current user. Someone else's id is a 404, like a missing one."""
    iv = db.execute(
        select(Interview)
        .where(Interview.id == interview_id, Interview.user_id == user.id)
        .options(selectinload(Interview.questions).selectinload(Question.answer))
    ).scalar_one_or_none()
    if iv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return iv


def _release(db: Session) -> None:
    """End the read transaction so the pooled connection isn't held during slow AI calls.
    (expire_on_commit=False keeps the loaded objects usable.)"""
    db.commit()


def _lock_interview(db: Session, user: User, interview_id: uuid.UUID) -> Interview:
    """Re-load the interview with a row lock for the write phase. Serialises concurrent answers
    to the same interview and answer-vs-complete races."""
    iv = db.execute(
        select(Interview)
        .where(Interview.id == interview_id, Interview.user_id == user.id)
        .with_for_update()
        .options(selectinload(Interview.questions).selectinload(Question.answer))
        # The session still holds the objects loaded before the AI calls; overwrite them with
        # the current rows instead of trusting the stale copies.
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if iv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return iv


def _ai_budget(calls: int = 1) -> None:
    """Global cap across all users on paid/quota'd AI calls (Gemini and transcription)."""
    limit = get_settings().rate_ai_calls_per_hour
    for _ in range(calls):
        limiter.check("ai:global", limit, 3600)


def _question_out(q: Question, reveal: bool) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        position=q.position,
        kind=q.kind,
        skill=q.skill,
        text=q.text,
        guidance=q.guidance if (reveal or q.answer is not None) else None,
        answer=AnswerOut.model_validate(q.answer) if q.answer else None,
    )


def _summary_out(iv: Interview) -> InterviewSummaryOut:
    return InterviewSummaryOut(
        id=iv.id,
        role=iv.role,
        level=iv.level,
        status=iv.status,
        created_at=iv.created_at,
        completed_at=iv.completed_at,
        overall_score=iv.overall_score,
        content_score=iv.content_score,
        clarity_score=iv.clarity_score,
        question_count=len(iv.questions),
        answered_count=sum(1 for q in iv.questions if q.answer is not None),
    )


def interview_out(iv: Interview) -> InterviewOut:
    done = iv.status == "completed"
    return InterviewOut(
        **_summary_out(iv).model_dump(),
        ai_model=iv.ai_model,
        summary=iv.summary,
        questions=[_question_out(q, done) for q in iv.questions],
    )


# ---- endpoints ----------------------------------------------------------------------------------
@router.post("", response_model=InterviewOut, status_code=status.HTTP_201_CREATED)
def create_interview(
    body: InterviewCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    ai: InterviewAI = Depends(get_ai),
):
    s = get_settings()
    if body.role not in ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown role: {body.role}")
    if body.level not in LEVELS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown level: {body.level}")
    n = body.num_questions or s.default_questions
    if not s.min_questions <= n <= s.max_questions:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"num_questions must be {s.min_questions}-{s.max_questions}",
        )
    limiter.check(f"interviews:{user.id}", s.rate_interviews_per_hour, 3600)

    # Earlier questions for this role, so a new set doesn't repeat them.
    avoid = list(
        db.execute(
            select(Question.text)
            .join(Interview)
            .where(Interview.user_id == user.id, Interview.role == body.role)
            .order_by(Interview.created_at.desc())
            .limit(20)
        ).scalars()
    )
    _release(db)
    _ai_budget()
    generated = ai.generate_questions(body.role, body.level, n, avoid)

    iv = Interview(user_id=user.id, role=body.role, level=body.level, ai_model=ai.model_name)
    iv.questions = [
        Question(
            position=i, kind=g.kind, skill=g.skill, text=g.question, guidance=g.what_good_looks_like
        )
        for i, g in enumerate(generated, 1)
    ]
    db.add(iv)
    db.commit()
    return interview_out(_own_interview(db, user, iv.id))


@router.get("", response_model=list[InterviewSummaryOut])
def list_interviews(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Interview)
        .where(Interview.user_id == user.id)
        .options(selectinload(Interview.questions).selectinload(Question.answer))
        .order_by(Interview.created_at.desc())
    ).scalars()
    return [_summary_out(iv) for iv in rows]


@router.get("/{interview_id}", response_model=InterviewOut)
def get_interview(
    interview_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return interview_out(_own_interview(db, user, interview_id))


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(
    interview_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    iv = _own_interview(db, user, interview_id)
    db.delete(iv)
    db.commit()


def _save_upload(upload: UploadFile, dest: Path, max_bytes: int) -> int:
    size = 0
    with dest.open("wb") as fh:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    f"Recording is larger than {max_bytes // (1024 * 1024)} MB",
                )
            fh.write(chunk)
    return size


@router.post("/{interview_id}/questions/{question_id}/answer", response_model=QuestionOut)
def answer_question(
    interview_id: uuid.UUID,
    question_id: uuid.UUID,
    audio: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    ai: InterviewAI = Depends(get_ai),
    transcriber: Transcriber = Depends(get_transcriber),
):
    s = get_settings()
    iv = _own_interview(db, user, interview_id)
    if iv.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview is already finished")
    question = next((q for q in iv.questions if q.id == question_id), None)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")

    ctype = (audio.content_type or "").split(";")[0].strip().lower()
    if ctype not in AUDIO_SUFFIX:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported audio type: {ctype or 'unknown'}"
        )
    limiter.check(f"answers:{user.id}", s.rate_answers_per_hour, 3600)
    ctx = QuestionContext(
        role=iv.role,
        level=iv.level,
        kind=question.kind,
        skill=question.skill,
        question=question.text,
        guidance=question.guidance,
    )
    _release(db)  # don't hold a DB connection while transcribing and scoring

    # Raw audio lives only in a temp file and is deleted as soon as it is transcribed,
    # unless KEEP_AUDIO=true.
    tmpdir = Path(tempfile.mkdtemp(prefix="answer-"))
    tmp = tmpdir / f"answer{AUDIO_SUFFIX[ctype]}"
    kept_path: Path | None = None
    try:
        size = _save_upload(audio, tmp, s.max_audio_bytes)
        if size == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The recording is empty")
        # Check the length before spending CPU / transcription quota on it.
        seconds = probe_duration(tmp)
        if seconds is not None and seconds > s.max_answer_seconds + 30:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"Answers can be at most {s.max_answer_seconds // 60} minutes long",
            )
        _ai_budget(2)  # transcription + scoring
        transcript = transcriber.transcribe(tmp)
        if s.keep_audio:
            kept_dir = Path(s.audio_dir) / str(user.id)
            kept_dir.mkdir(parents=True, exist_ok=True)
            kept_path = kept_dir / f"{question_id}{tmp.suffix}"
            shutil.move(tmp, kept_path)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if transcript.duration > s.max_answer_seconds + 30:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Answers can be at most {s.max_answer_seconds // 60} minutes long",
        )
    if not transcript.words:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "No speech detected. Check that the right microphone is selected and try again.",
        )

    metrics = compute_clarity(
        transcript.words,
        long_pause_s=s.long_pause_seconds,
        ideal_low=s.ideal_wpm_low,
        ideal_high=s.ideal_wpm_high,
    )
    assessment = ai.assess_answer(ctx, transcript.text)
    scores = combine(
        assessment,
        metrics.computed_score,
        content_weight=s.content_weight,
        clarity_computed_weight=s.clarity_computed_weight,
    )

    # Write phase, under a row lock on the interview.
    iv = _lock_interview(db, user, interview_id)
    if iv.status != "in_progress":
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This interview was finished while your answer was scored"
        )
    question = next(q for q in iv.questions if q.id == question_id)
    if question.answer is not None:  # re-answering replaces the earlier attempt
        db.delete(question.answer)
        db.flush()
    question.answer = Answer(
        transcript=transcript.text,
        words=[{"w": w.w, "start": w.start, "end": w.end} for w in transcript.words],
        transcriber=transcript.model,
        audio_seconds=round(transcript.duration, 2),
        audio_kept=kept_path is not None,
        speaking_seconds=metrics.speaking_seconds,
        word_count=metrics.word_count,
        wpm=metrics.wpm,
        filler_count=metrics.filler_count,
        fillers=metrics.fillers,
        long_pause_count=metrics.long_pause_count,
        longest_pause_s=metrics.longest_pause_s,
        relevance=assessment.relevance,
        correctness=assessment.correctness,
        depth=assessment.depth,
        structure=assessment.structure,
        clarity_llm=assessment.clarity,
        content_score=scores.content,
        clarity_computed=metrics.computed_score,
        clarity_score=scores.clarity,
        overall_score=scores.overall,
        feedback={
            "summary": assessment.summary,
            "strengths": assessment.strengths,
            "improvements": assessment.improvements,
            "clarity_feedback": assessment.clarity_feedback,
            "clarity_notes": metrics.notes,
        },
        example_answer=assessment.example_answer,
        ai_model=ai.model_name,
    )
    db.commit()
    db.refresh(question)
    return _question_out(question, reveal=True)


@router.post("/{interview_id}/complete", response_model=InterviewOut)
def complete_interview(
    interview_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    ai: InterviewAI = Depends(get_ai),
):
    s = get_settings()
    iv = _own_interview(db, user, interview_id)
    if iv.status == "completed":
        return interview_out(iv)
    answered = [q for q in iv.questions if q.answer is not None]
    if not answered:
        raise HTTPException(status.HTTP_409_CONFLICT, "Answer at least one question first")
    limiter.check(f"complete:{user.id}", s.rate_completions_per_hour, 3600)

    items = [
        ScoredItem(
            question=q.text,
            kind=q.kind,
            skill=q.skill,
            content_score=q.answer.content_score,
            clarity_score=q.answer.clarity_score,
            summary=str(q.answer.feedback.get("summary", "")),
        )
        for q in answered
    ]
    answered_ids = {q.id for q in answered}
    _release(db)
    _ai_budget()
    summary = ai.summarize(iv.role, iv.level, items)

    iv = _lock_interview(db, user, interview_id)
    if iv.status == "completed":  # a parallel request finished it first
        db.rollback()
        return interview_out(_own_interview(db, user, interview_id))
    answered = [q for q in iv.questions if q.answer is not None]
    if {q.id for q in answered} != answered_ids:
        # An answer landed while the debrief was being written; ask the client to retry so the
        # summary and the aggregates cover the same answers.
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An answer was still being saved. Please finish again."
        )
    skipped = len(iv.questions) - len(answered)

    iv.overall_score = mean([q.answer.overall_score for q in answered])
    iv.content_score = mean([q.answer.content_score for q in answered])
    iv.clarity_score = mean([q.answer.clarity_score for q in answered])
    iv.summary = {**summary.model_dump(), "skipped_questions": skipped}
    iv.status = "completed"
    iv.completed_at = datetime.now(UTC)
    db.commit()
    return interview_out(_own_interview(db, user, iv.id))


__all__ = ["AIError", "router"]
