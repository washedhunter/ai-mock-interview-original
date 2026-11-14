"""How the rubric scores combine. All weights come from settings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .ai.schemas import AnswerAssessment

RUBRIC = ("relevance", "correctness", "depth", "structure")


@dataclass
class AnswerScores:
    content: float  # 0-100
    clarity: float  # 0-100
    overall: float  # 0-100


def content_score(a: AnswerAssessment) -> float:
    """Mean of the four rubric dimensions (0-10), scaled to 0-100."""
    return round(sum(getattr(a, k) for k in RUBRIC) / len(RUBRIC) * 10, 1)


def combine(
    a: AnswerAssessment,
    computed_clarity: float,
    *,
    content_weight: float = 0.7,
    clarity_computed_weight: float = 0.6,
) -> AnswerScores:
    content = content_score(a)
    clarity = (
        clarity_computed_weight * computed_clarity + (1 - clarity_computed_weight) * a.clarity * 10
    )
    overall = content_weight * content + (1 - content_weight) * clarity
    return AnswerScores(round(content, 1), round(clarity, 1), round(overall, 1))


def mean(values: Sequence[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None
