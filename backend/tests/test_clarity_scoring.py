import pytest

from interview_api.ai.base import Word
from interview_api.ai.schemas import AnswerAssessment
from interview_api.clarity import compute_clarity, count_fillers
from interview_api.ratelimit import RateLimiter
from interview_api.scoring import combine, content_score


def words_at(tokens, start=0.0, step=0.4, dur=0.3, pause_after=None, pause=0.0):
    out, t = [], start
    for i, tok in enumerate(tokens):
        out.append(Word(tok, round(t, 3), round(t + dur, 3)))
        t += step
        if pause_after is not None and i == pause_after:
            t += pause
    return out


@pytest.mark.parametrize(
    "text,expected",
    [
        ("um so uh I think umm yes", {"um": 2, "uh": 1}),
        ("I would like to explain", {}),  # verb "like" is not a filler
        ("it was, like, really slow", {"like": 1}),
        ("it was like, slow", {"like": 1}),
        ("what kind of database did you use", {}),
        ("it is kind of slow and sort of broken", {"kind of": 1, "sort of": 1}),
        ("you know, I mean, basically it works", {"you know": 1, "i mean": 1, "basically": 1}),
        ("Um. Uh, hmm.", {"um": 1, "uh": 1, "hmm": 1}),
    ],
)
def test_count_fillers(text, expected):
    assert dict(count_fillers(text.split())) == expected


def test_pace_in_band_no_fillers_no_pauses_scores_100():
    # 30 words, one every 0.4 s -> 150 wpm
    m = compute_clarity(words_at(["word"] * 30))
    assert m.wpm == pytest.approx(30 / (29 * 0.4 + 0.3) * 60, rel=1e-3)
    assert 110 <= m.wpm <= 170
    assert m.computed_score == 100.0
    assert m.long_pause_count == 0 and m.filler_count == 0


def test_slow_pace_penalty():
    m = compute_clarity(words_at(["word"] * 30, step=1.0))  # ~61 wpm
    expected_pen = min(30, (110 - m.wpm) * 0.5)
    assert m.computed_score == pytest.approx(100 - expected_pen, abs=0.1)
    assert "slow" in m.notes[0]


def test_fast_pace_penalty_is_capped():
    m = compute_clarity(words_at(["word"] * 60, step=0.1, dur=0.08))  # ~600 wpm
    assert m.computed_score == 70.0


def test_filler_penalty():
    toks = ["um"] * 3 + ["word"] * 27  # 10 per 100 words -> 40, capped at 35
    m = compute_clarity(words_at(toks))
    assert m.filler_count == 3 and m.fillers_per_100 == 10.0
    assert m.computed_score == 65.0


def test_long_pauses():
    m = compute_clarity(words_at(["word"] * 30, pause_after=10, pause=3.0))
    assert m.long_pause_count == 1
    assert m.longest_pause_s == pytest.approx(3.1, abs=0.01)
    minutes = m.speaking_seconds / 60
    assert m.computed_score == pytest.approx(100 - 6 / max(minutes, 0.5), abs=0.2)


def test_empty():
    m = compute_clarity([])
    assert m.word_count == 0 and m.computed_score == 0.0


def _assessment(r, c, d, s, clarity):
    return AnswerAssessment(
        relevance=r,
        correctness=c,
        depth=d,
        structure=s,
        clarity=clarity,
        summary="x",
        strengths=[],
        improvements=[],
        clarity_feedback="",
        example_answer="",
    )


def test_content_and_combined_scores():
    a = _assessment(8, 6, 4, 6, 7)
    assert content_score(a) == 60.0
    s = combine(a, computed_clarity=90.0, content_weight=0.7, clarity_computed_weight=0.6)
    assert s.clarity == pytest.approx(0.6 * 90 + 0.4 * 70)
    assert s.overall == pytest.approx(0.7 * 60 + 0.3 * s.clarity, abs=0.06)


def test_assessment_clamps_out_of_range_scores():
    a = _assessment(14, -2, "7", 6.6, 10)
    assert (a.relevance, a.correctness, a.depth, a.structure) == (10, 0, 7, 7)


def test_rate_limiter_window():
    now = [0.0]
    rl = RateLimiter(clock=lambda: now[0])
    rl.check("k", 2, 60)
    rl.check("k", 2, 60)
    with pytest.raises(Exception) as e:
        rl.check("k", 2, 60)
    assert e.value.status_code == 429 and e.value.headers["Retry-After"] == "60"
    rl.check("other", 2, 60)  # separate key
    now[0] = 60.5  # window slid past both hits
    rl.check("k", 2, 60)
