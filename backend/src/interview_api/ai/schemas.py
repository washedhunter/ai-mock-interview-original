"""Structured-output schemas for Gemini. Gemini ignores some JSON-schema constraints, so every
response is re-validated (and clamped) with these Pydantic models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _clamp_score(v: object) -> int:
    try:
        x = round(float(v))  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError("score must be a number") from exc
    return max(0, min(10, x))


def _trimmed(items: list[str], limit: int) -> list[str]:
    return [s.strip() for s in items if s and s.strip()][:limit]


class GeneratedQuestion(BaseModel):
    kind: Literal["behavioural", "technical"]
    skill: str = Field(description="2-4 word name of the skill this question tests")
    question: str = Field(description="The question as the interviewer would say it aloud")
    what_good_looks_like: str = Field(
        description="2-3 sentences: the points a strong answer at this level covers"
    )

    @field_validator("skill", "question", "what_good_looks_like")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("skill")
    @classmethod
    def _short_skill(cls, v: str) -> str:
        return v[:80]


class QuestionSet(BaseModel):
    questions: list[GeneratedQuestion]


class AnswerAssessment(BaseModel):
    relevance: int = Field(description="0-10")
    correctness: int = Field(description="0-10")
    depth: int = Field(description="0-10")
    structure: int = Field(description="0-10")
    clarity: int = Field(description="0-10: how easy the answer is to follow when heard")
    summary: str = Field(description="One-sentence verdict on the answer")
    strengths: list[str] = Field(description="1-3 specific strengths")
    improvements: list[str] = Field(description="1-3 specific, actionable improvements")
    clarity_feedback: str = Field(description="1-2 sentences on how clearly it was communicated")
    example_answer: str = Field(description="A stronger answer, spoken style, first person")

    @field_validator("relevance", "correctness", "depth", "structure", "clarity", mode="before")
    @classmethod
    def _scores(cls, v: object) -> int:
        return _clamp_score(v)

    @field_validator("strengths", "improvements")
    @classmethod
    def _lists(cls, v: list[str]) -> list[str]:
        return _trimmed(v, 3)


class InterviewSummary(BaseModel):
    summary: str = Field(description="2-3 sentences on the whole interview")
    strengths: list[str] = Field(description="2-3 strengths across the interview")
    priorities: list[str] = Field(description="2-3 concrete things to practise next")

    @field_validator("strengths", "priorities")
    @classmethod
    def _lists(cls, v: list[str]) -> list[str]:
        return _trimmed(v, 3)
