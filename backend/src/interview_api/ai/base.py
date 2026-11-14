"""Interfaces the routers depend on. Real (Gemini, Whisper) and mock implementations plug in."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .schemas import AnswerAssessment, GeneratedQuestion, InterviewSummary


class AIError(Exception):
    """An AI provider failed in a way the user should see (HTTP 502/503)."""

    def __init__(self, message: str, *, retry_after: int | None = None, status: int = 502):
        super().__init__(message)
        self.retry_after = retry_after
        self.status = status


@dataclass
class QuestionContext:
    role: str
    level: str
    kind: str
    skill: str
    question: str
    guidance: str


@dataclass
class ScoredItem:
    """One answered question, as passed to the end-of-interview summary."""

    question: str
    kind: str
    skill: str
    content_score: float
    clarity_score: float
    summary: str


class InterviewAI(Protocol):
    model_name: str

    def generate_questions(
        self, role: str, level: str, n: int, avoid: list[str]
    ) -> list[GeneratedQuestion]: ...

    def assess_answer(self, ctx: QuestionContext, transcript: str) -> AnswerAssessment: ...

    def summarize(self, role: str, level: str, items: list[ScoredItem]) -> InterviewSummary: ...


@dataclass
class Word:
    w: str
    start: float
    end: float


@dataclass
class Transcript:
    text: str
    words: list[Word]
    duration: float  # length of the audio in seconds
    model: str
    language: str = "en"
    extra: dict = field(default_factory=dict)


class Transcriber(Protocol):
    model_name: str

    def transcribe(self, path: Path) -> Transcript: ...
