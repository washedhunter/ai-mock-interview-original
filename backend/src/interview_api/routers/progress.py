"""Score trends over time, by role and by skill."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import current_user
from ..db import get_db
from ..models import Interview, Question, User
from ..roles import ROLES
from ..schemas import ProgressOut, ProgressPoint, RoleStat, SkillStat
from ..scoring import mean

router = APIRouter(prefix="/api/progress", tags=["progress"])

# Skill name -> how to read it from a ProgressPoint (all on a 0-100 scale).
SKILLS = {
    "Overall": "overall",
    "Content": "content",
    "Clarity": "clarity",
    "Relevance": "relevance",
    "Correctness": "correctness",
    "Depth": "depth",
    "Structure": "structure",
    "Behavioural questions": "behavioural",
    "Technical questions": "technical",
}


def _point(iv: Interview) -> ProgressPoint:
    answers = [q.answer for q in iv.questions if q.answer is not None]

    def rubric(attr: str) -> float | None:
        m = mean([getattr(a, attr) for a in answers])
        return round(m * 10, 1) if m is not None else None

    def by_kind(kind: str) -> float | None:
        return mean([q.answer.overall_score for q in iv.questions if q.answer and q.kind == kind])

    total_words = sum(a.word_count for a in answers)
    return ProgressPoint(
        interview_id=iv.id,
        completed_at=iv.completed_at,  # type: ignore[arg-type]
        role=iv.role,
        level=iv.level,
        overall=iv.overall_score,
        content=iv.content_score,
        clarity=iv.clarity_score,
        relevance=rubric("relevance"),
        correctness=rubric("correctness"),
        depth=rubric("depth"),
        structure=rubric("structure"),
        behavioural=by_kind("behavioural"),
        technical=by_kind("technical"),
        wpm=mean([a.wpm for a in answers]),
        fillers_per_100=(
            round(sum(a.filler_count for a in answers) / total_words * 100, 2)
            if total_words
            else None
        ),
    )


@router.get("", response_model=ProgressOut)
def progress(
    role: str | None = Query(None, description="Only interviews for this role"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if role is not None and role not in ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown role: {role}")
    completed = list(
        db.execute(
            select(Interview)
            .where(Interview.user_id == user.id, Interview.status == "completed")
            .options(selectinload(Interview.questions).selectinload(Question.answer))
            .order_by(Interview.completed_at)
        ).scalars()
    )
    selected = [iv for iv in completed if role is None or iv.role == role]
    points = [_point(iv) for iv in selected]

    skills = []
    for name, attr in SKILLS.items():
        series = [getattr(p, attr) for p in points if getattr(p, attr) is not None]
        first = series[0] if series else None
        latest = series[-1] if series else None
        skills.append(
            SkillStat(
                skill=name,
                first=first,
                latest=latest,
                average=mean(series),
                change=round(latest - first, 1) if len(series) >= 2 else None,
            )
        )

    per_role: dict[str, list[float]] = defaultdict(list)
    for iv in completed:
        if iv.overall_score is not None:
            per_role[iv.role].append(iv.overall_score)
    by_role = [
        RoleStat(
            role=r,
            interviews=len(v),
            average_overall=mean(v),
            best_overall=max(v),
            latest_overall=v[-1],
        )
        for r, v in sorted(per_role.items())
    ]

    q_skills: dict[str, list[float]] = defaultdict(list)
    names: dict[str, str] = {}
    for iv in selected:
        for q in iv.questions:
            if q.answer is not None:
                key = q.skill.strip().lower()
                names.setdefault(key, q.skill.strip())
                q_skills[key].append(q.answer.overall_score)
    question_skills = sorted(
        (
            {"skill": names[k], "answers": len(v), "average_overall": mean(v), "kind": None}
            for k, v in q_skills.items()
        ),
        key=lambda d: (-d["answers"], d["skill"]),
    )[:15]

    return ProgressOut(
        role=role,
        roles_practised=sorted({iv.role for iv in completed}),
        points=points,
        skills=skills,
        by_role=by_role,
        question_skills=question_skills,
    )
