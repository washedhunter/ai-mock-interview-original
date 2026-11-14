"""Request/response models for the HTTP API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SignupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required")
        return v


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime


class MetaOut(BaseModel):
    roles: list[str]
    levels: list[str]
    min_questions: int
    max_questions: int
    default_questions: int
    max_answer_seconds: int
    max_audio_bytes: int
    ai_mode: str  # "gemini" | "demo"
    ai_model: str
    transcriber: str


class InterviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    level: str
    num_questions: int | None = None


class AnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    transcript: str
    transcriber: str
    audio_seconds: float
    audio_kept: bool
    speaking_seconds: float
    word_count: int
    wpm: float
    filler_count: int
    fillers: dict[str, int]
    long_pause_count: int
    longest_pause_s: float
    relevance: int
    correctness: int
    depth: int
    structure: int
    clarity_llm: int
    content_score: float
    clarity_computed: float
    clarity_score: float
    overall_score: float
    feedback: dict[str, Any]
    example_answer: str
    ai_model: str


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    position: int
    kind: str
    skill: str
    text: str
    guidance: str | None = None  # hidden until the question is answered
    answer: AnswerOut | None = None


class InterviewSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: str
    level: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    overall_score: float | None
    content_score: float | None
    clarity_score: float | None
    question_count: int
    answered_count: int


class InterviewOut(InterviewSummaryOut):
    ai_model: str
    summary: dict[str, Any] | None
    questions: list[QuestionOut]


class ProgressPoint(BaseModel):
    interview_id: uuid.UUID
    completed_at: datetime
    role: str
    level: str
    overall: float | None
    content: float | None
    clarity: float | None
    relevance: float | None
    correctness: float | None
    depth: float | None
    structure: float | None
    behavioural: float | None
    technical: float | None
    wpm: float | None
    fillers_per_100: float | None


class SkillStat(BaseModel):
    skill: str
    first: float | None
    latest: float | None
    average: float | None
    change: float | None


class RoleStat(BaseModel):
    role: str
    interviews: int
    average_overall: float | None
    best_overall: float | None
    latest_overall: float | None


class ProgressOut(BaseModel):
    role: str | None
    roles_practised: list[str]
    points: list[ProgressPoint]
    skills: list[SkillStat]
    by_role: list[RoleStat]
    question_skills: list[dict[str, Any]]  # per generated-question skill: avg overall, count
