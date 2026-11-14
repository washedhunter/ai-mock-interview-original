"""Delivery metrics from the transcript and Whisper's word timestamps.

computed clarity (0-100) = 100 - pace penalty - filler penalty - pause penalty
- pace: 0 inside the ideal band (110-170 words/min by default), else 0.5 points per wpm
  outside it, capped at 30.
- fillers: 4 points per filler word per 100 words, capped at 35.
- pauses: 6 points per long pause (>= 2 s by default) per minute of speaking, capped at 25.
The constants are deliberately simple so the score can be explained line by line.
"""

from __future__ import annotations

import itertools
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from .ai.base import Word

HARD_FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mm", "mhm"}
SOFT_FILLERS = {"basically", "literally"}
PHRASE_FILLERS = [("you", "know"), ("i", "mean"), ("kind", "of"), ("sort", "of")]
# "what kind of database" is not a filler; "it's kind of slow" is.
_NOT_HEDGE_BEFORE = {
    "what",
    "which",
    "this",
    "that",
    "the",
    "a",
    "any",
    "some",
    "every",
    "same",
    "other",
    "one",
    "these",
    "those",
    "each",
    "no",
    "all",
}

_strip = re.compile(r"[^a-z']")


@dataclass
class ClarityMetrics:
    word_count: int
    speaking_seconds: float
    wpm: float
    filler_count: int
    fillers: dict[str, int]
    fillers_per_100: float
    long_pause_count: int
    longest_pause_s: float
    computed_score: float
    notes: list[str] = field(default_factory=list)


def _norm(token: str) -> str:
    return _strip.sub("", token.lower())


def count_fillers(raw_tokens: Sequence[str]) -> Counter[str]:
    toks = [_norm(t) for t in raw_tokens]
    found: Counter[str] = Counter()
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in HARD_FILLERS or t in SOFT_FILLERS:
            found["um" if t in {"umm", "uhm", "mm", "mhm"} else "uh" if t == "uhh" else t] += 1
            i += 1
            continue
        if t == "like":
            # Only the interjection, which Whisper punctuates as "like," ("it was, like, slow").
            # ", like a holiday" introduces an example and is not counted.
            if raw_tokens[i].rstrip().endswith(","):
                found["like"] += 1
            i += 1
            continue
        if i + 1 < len(toks) and (t, toks[i + 1]) in PHRASE_FILLERS:
            prev = toks[i - 1] if i > 0 else ""
            if not (t in {"kind", "sort"} and prev in _NOT_HEDGE_BEFORE):
                found[f"{t} {toks[i + 1]}"] += 1
                i += 2
                continue
        i += 1
    return found


def compute_clarity(
    words: Sequence[Word],
    *,
    long_pause_s: float = 2.0,
    ideal_low: float = 110.0,
    ideal_high: float = 170.0,
) -> ClarityMetrics:
    tokens = [w.w for w in words]
    n = len(tokens)
    if n == 0:
        return ClarityMetrics(0, 0.0, 0.0, 0, {}, 0.0, 0, 0.0, 0.0, ["No speech detected."])

    speaking = max(words[-1].end - words[0].start, 0.001)
    wpm = n / speaking * 60
    fillers = count_fillers(tokens)
    filler_count = sum(fillers.values())
    per_100 = filler_count / n * 100

    gaps = [max(0.0, b.start - a.end) for a, b in itertools.pairwise(words)]
    long_pauses = [g for g in gaps if g >= long_pause_s]
    longest = max(gaps, default=0.0)

    if wpm < ideal_low:
        pace_pen = min(30.0, (ideal_low - wpm) * 0.5)
    elif wpm > ideal_high:
        pace_pen = min(30.0, (wpm - ideal_high) * 0.5)
    else:
        pace_pen = 0.0
    filler_pen = min(35.0, per_100 * 4)
    pause_pen = min(25.0, len(long_pauses) / max(speaking / 60, 0.5) * 6)
    score = max(0.0, 100.0 - pace_pen - filler_pen - pause_pen)

    notes = []
    band = f"{ideal_low:.0f}-{ideal_high:.0f}"
    if wpm < ideal_low:
        notes.append(f"Pace {wpm:.0f} words/min: on the slow side (aim for {band}).")
    elif wpm > ideal_high:
        notes.append(f"Pace {wpm:.0f} words/min: on the fast side (aim for {band}).")
    else:
        notes.append(f"Pace {wpm:.0f} words/min: comfortable (aim for {band}).")
    if filler_count:
        top = ", ".join(f'"{k}" x{v}' for k, v in fillers.most_common(4))
        notes.append(f"{filler_count} filler words ({per_100:.1f} per 100 words): {top}.")
    else:
        notes.append("No filler words detected.")
    if long_pauses:
        notes.append(
            f"{len(long_pauses)} long pause(s) of {long_pause_s:.0f} s or more; longest {longest:.1f} s."
        )
    else:
        notes.append(f"No pauses of {long_pause_s:.0f} s or more.")
    if n < 20:
        notes.append("Very short answer: delivery metrics are rough at this length.")

    return ClarityMetrics(
        word_count=n,
        speaking_seconds=round(speaking, 2),
        wpm=round(wpm, 1),
        filler_count=filler_count,
        fillers=dict(fillers),
        fillers_per_100=round(per_100, 2),
        long_pause_count=len(long_pauses),
        longest_pause_s=round(longest, 2),
        computed_score=round(score, 1),
        notes=notes,
    )
