"""ORM models. The schema itself is created by Alembic (alembic/versions)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # stored lower-cased
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # SHA-256 of the cookie value
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(80))
    level: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20), default="in_progress"
    )  # in_progress | completed
    ai_model: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # aggregates, filled on completion (0-100)
    overall_score: Mapped[float | None] = mapped_column(Float)
    content_score: Mapped[float | None] = mapped_column(Float)
    clarity_score: Mapped[float | None] = mapped_column(Float)
    # {"summary": str, "strengths": [str], "priorities": [str]}
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    questions: Mapped[list[Question]] = relationship(
        back_populates="interview", order_by="Question.position", cascade="all, delete-orphan"
    )


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("interview_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # behavioural | technical
    skill: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(Text)
    guidance: Mapped[str] = mapped_column(
        Text
    )  # what a strong answer covers (shown after answering)

    interview: Mapped[Interview] = relationship(back_populates="questions")
    answer: Mapped[Answer | None] = relationship(
        back_populates="question", cascade="all, delete-orphan", uselist=False
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # transcription
    transcript: Mapped[str] = mapped_column(Text)
    words: Mapped[list[dict[str, Any]]] = mapped_column(JSON)  # [{"w", "start", "end"}]
    transcriber: Mapped[str] = mapped_column(String(80))
    audio_seconds: Mapped[float] = mapped_column(Float)  # length of the recording
    audio_kept: Mapped[bool] = mapped_column(default=False)

    # clarity metrics (computed from the transcript + word timestamps)
    speaking_seconds: Mapped[float] = mapped_column(Float)
    word_count: Mapped[int] = mapped_column(Integer)
    wpm: Mapped[float] = mapped_column(Float)
    filler_count: Mapped[int] = mapped_column(Integer)
    fillers: Mapped[dict[str, int]] = mapped_column(JSON)
    long_pause_count: Mapped[int] = mapped_column(Integer)
    longest_pause_s: Mapped[float] = mapped_column(Float)

    # scores (0-10 rubric dimensions, 0-100 composites)
    relevance: Mapped[int] = mapped_column(Integer)
    correctness: Mapped[int] = mapped_column(Integer)
    depth: Mapped[int] = mapped_column(Integer)
    structure: Mapped[int] = mapped_column(Integer)
    clarity_llm: Mapped[int] = mapped_column(Integer)
    content_score: Mapped[float] = mapped_column(Float)
    clarity_computed: Mapped[float] = mapped_column(Float)
    clarity_score: Mapped[float] = mapped_column(Float)
    overall_score: Mapped[float] = mapped_column(Float)

    # {"summary", "strengths": [], "improvements": [], "clarity_feedback", "clarity_notes": []}
    feedback: Mapped[dict[str, Any]] = mapped_column(JSON)
    example_answer: Mapped[str] = mapped_column(Text)
    ai_model: Mapped[str] = mapped_column(String(80))

    question: Mapped[Question] = relationship(back_populates="answer")
