"""Deterministic stand-ins for Gemini and Whisper.

Used by the tests, the Playwright end-to-end run, and the key-free demo mode (the UI labels it
"Demo mode: canned AI responses"). Nothing here pretends to judge an answer: the mock scores
depend only on the transcript's length, so they are obviously fake.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .base import QuestionContext, ScoredItem, Transcript, Word
from .gemini import split_kinds
from .schemas import AnswerAssessment, GeneratedQuestion, InterviewSummary

MOCK_MODEL = "mock-ai"

_BEHAVIOURAL = [
    ("Teamwork", "Tell me about a time you disagreed with a teammate. How did you resolve it?"),
    ("Ownership", "Describe a project where something went wrong. What did you do about it?"),
    ("Learning", "Tell me about a time you had to learn something new quickly."),
    ("Prioritisation", "Describe a time you had more work than time. How did you prioritise?"),
]
_TECHNICAL = {
    "default": [
        ("Fundamentals", "Explain a core concept from your field to a new colleague."),
        ("Debugging", "How would you investigate a problem that only happens in production?"),
        ("Trade-offs", "Describe a technical trade-off you would weigh when building {role} work."),
        ("Quality", "How do you check that your work is correct before you share it?"),
    ],
}


class MockInterviewAI:
    model_name = MOCK_MODEL

    def generate_questions(
        self, role: str, level: str, n: int, avoid: list[str]
    ) -> list[GeneratedQuestion]:
        b, t = split_kinds(n)
        beh = [("behavioural", s, q) for s, q in _BEHAVIOURAL][:b]
        tech = [("technical", s, q.format(role=role)) for s, q in _TECHNICAL["default"]]
        while len(tech) < t:  # n can be up to 8
            tech.append(("technical", "Fundamentals", f"Tell me about a {role} tool you rely on."))
        tech = tech[:t]
        while len(beh) < b:
            beh.append(
                (
                    "behavioural",
                    "Communication",
                    "Tell me about a time you explained something complex to a non-expert.",
                )
            )
        ordered: list[tuple[str, str, str]] = []
        while beh or tech:  # alternate, behavioural first
            if beh:
                ordered.append(beh.pop(0))
            if tech:
                ordered.append(tech.pop(0))
        return [
            GeneratedQuestion(
                kind=k,  # type: ignore[arg-type]
                skill=s,
                question=q,
                what_good_looks_like="A specific, structured answer with reasoning and a result.",
            )
            for k, s, q in ordered
        ]

    def assess_answer(self, ctx: QuestionContext, transcript: str) -> AnswerAssessment:
        words = len(transcript.split())
        base = max(1, min(8, words // 15 + 2))
        return AnswerAssessment(
            relevance=base,
            correctness=base,
            depth=max(0, base - 1),
            structure=base,
            clarity=base,
            summary=f"Demo mode: canned feedback for a {words}-word answer.",
            strengths=["Demo mode: you gave an answer of " + str(words) + " words."],
            improvements=["Demo mode: add a Gemini API key for real feedback."],
            clarity_feedback="Demo mode: the clarity metrics above are real; this sentence is not.",
            example_answer="Demo mode: with a Gemini API key, a stronger example answer appears here.",
        )

    def summarize(self, role: str, level: str, items: list[ScoredItem]) -> InterviewSummary:
        return InterviewSummary(
            summary=f"Demo mode: canned summary for a {level} {role} interview "
            f"with {len(items)} answered questions.",
            strengths=["Demo mode: completed the interview."],
            priorities=["Demo mode: add a Gemini API key for a real debrief."],
        )


MOCK_TRANSCRIPT = (
    "So um in my last project I worked with a teammate who wanted to rewrite the service. "
    "I suggested we measure first. We profiled it, found one slow query, and fixed that "
    "instead, which cut the response time in half."
)


class MockTranscriber:
    """Returns a fixed transcript with evenly spaced word timings (one 2.5 s pause)."""

    model_name = "mock-whisper"

    def transcribe(self, path: Path) -> Transcript:
        data = Path(path).read_bytes()
        tokens = MOCK_TRANSCRIPT.split()
        words, t = [], 0.5
        for i, tok in enumerate(tokens):
            if i == 12:
                t += 2.5  # a long pause, so the pause metric has something to find
            words.append(Word(w=tok, start=round(t, 2), end=round(t + 0.3, 2)))
            t += 0.4
        return Transcript(
            text=MOCK_TRANSCRIPT,
            words=words,
            duration=round(t + 0.5, 2),
            model=self.model_name,
            extra={"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()[:12]},
        )
