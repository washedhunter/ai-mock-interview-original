"""Behaviour added after the code review: abuse limits, proxy headers, upload bounds, races."""

import io
import uuid
import wave
from pathlib import Path

from sqlalchemy import select, update

from interview_api.ai import get_ai, get_transcriber
from interview_api.ai.mock import MockInterviewAI, MockTranscriber
from interview_api.ai.transcribe import probe_duration
from interview_api.db import _session_factory
from interview_api.main import app
from interview_api.models import Answer, Interview, Question
from interview_api.ratelimit import RateLimiter

from .conftest import answer, new_interview, signup


def wav_bytes(seconds: float, rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(seconds * rate))
    return buf.getvalue()


def test_client_ip_is_the_rightmost_forwarded_entry(client, settings, monkeypatch):
    """A spoofed first X-Forwarded-For entry doesn't give a fresh rate-limit bucket."""
    monkeypatch.setattr(settings, "rate_logins_per_15min", 2)
    for i in range(2):
        client.post(
            "/api/auth/login",
            json={"email": "a@example.com", "password": "x"},
            headers={"x-forwarded-for": f"10.0.0.{i}, 203.0.113.7"},
        )
    r = client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "x"},
        headers={"x-forwarded-for": "10.9.9.9, 203.0.113.7"},
    )
    assert r.status_code == 429


def test_proxy_client_ip_header_wins_over_forwarded_for(client, settings, monkeypatch):
    """Behind a hop that rewrites X-Forwarded-For, users still get separate per-IP buckets."""
    monkeypatch.setattr(settings, "rate_logins_per_15min", 1)
    body = {"email": "a@example.com", "password": "x"}
    shared_hop = {"x-forwarded-for": "10.1.1.1"}  # what the internal hop would add for everyone
    assert (
        client.post(
            "/api/auth/login",
            json=body,
            headers={**shared_hop, "x-interview-client-ip": "198.51.100.1"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json=body,
            headers={**shared_hop, "x-interview-client-ip": "198.51.100.2"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json=body,
            headers={**shared_hop, "x-interview-client-ip": "198.51.100.1"},
        ).status_code
        == 429
    )


def test_signups_per_ip_are_capped(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "rate_signups_per_hour", 2)
    signup(client, "s1@example.com")
    signup(client, "s2@example.com")
    r = client.post(
        "/api/auth/signup", json={"email": "s3@example.com", "password": "long enough", "name": "S"}
    )
    assert r.status_code == 429


def test_only_failed_logins_count_against_an_email(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "rate_login_failures_per_hour", 2)
    signup(client)
    client.post("/api/auth/logout")
    good = {"email": "asha@example.com", "password": "correct horse 1"}
    for _ in range(3):  # successes don't use up the budget
        assert client.post("/api/auth/login", json=good).status_code == 200
    bad = {"email": "asha@example.com", "password": "wrong"}
    assert client.post("/api/auth/login", json=bad).status_code == 401
    assert client.post("/api/auth/login", json=bad).status_code == 401
    assert client.post("/api/auth/login", json=bad).status_code == 429


def test_cookie_is_secure_behind_https(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "cookie_secure", "auto")
    r = client.post(
        "/api/auth/signup",
        json={"email": "tls@example.com", "password": "long enough", "name": "T"},
        headers={"x-forwarded-proto": "https"},
    )
    assert "secure" in r.headers["set-cookie"].lower()


def test_cookie_not_secure_over_plain_http(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "cookie_secure", "auto")
    r = client.post(
        "/api/auth/signup", json={"email": "h@example.com", "password": "long enough", "name": "H"}
    )
    assert "secure" not in r.headers["set-cookie"].lower()


def test_probe_duration_reads_wav_length(tmp_path):
    p = tmp_path / "a.wav"
    p.write_bytes(wav_bytes(3.0))
    assert abs(probe_duration(p) - 3.0) < 0.05
    junk = tmp_path / "b.webm"
    junk.write_bytes(b"not audio")
    assert probe_duration(junk) is None


def test_too_long_audio_is_rejected_before_transcription(client, user, settings):
    calls = []

    class Spy(MockTranscriber):
        def transcribe(self, path):
            calls.append(path)
            return super().transcribe(path)

    app.dependency_overrides[get_transcriber] = Spy
    iv = new_interview(client)
    q = iv["questions"][0]
    long_audio = wav_bytes(settings.max_answer_seconds + 60)
    r = client.post(
        f"/api/interviews/{iv['id']}/questions/{q['id']}/answer",
        files={"audio": ("a.wav", io.BytesIO(long_audio), "audio/wav")},
    )
    assert r.status_code == 413
    assert calls == []  # no CPU / quota spent


def test_oversized_body_rejected_from_content_length(client, user, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_audio_bytes", 10_000)
    iv = new_interview(client)
    q = iv["questions"][0]
    r = client.post(
        f"/api/interviews/{iv['id']}/questions/{q['id']}/answer",
        files={"audio": ("a.webm", io.BytesIO(b"\0" * 200_000), "audio/webm")},
    )
    assert r.status_code == 413


def test_global_ai_budget(client, user, settings, monkeypatch):
    monkeypatch.setattr(settings, "rate_ai_calls_per_hour", 1)
    new_interview(client)
    r = client.post("/api/interviews", json={"role": "Data Analyst", "level": "Junior"})
    assert r.status_code == 429


def test_answer_landing_after_finish_is_refused(client, user):
    """The interview is completed while the answer is being transcribed/scored."""
    iv = new_interview(client)
    answer(client, iv, 0)
    iv_id = uuid.UUID(iv["id"])

    class FinishesMeanwhile(MockTranscriber):
        def transcribe(self, path):
            with _session_factory()() as db:
                db.execute(
                    update(Interview).where(Interview.id == iv_id).values(status="completed")
                )
                db.commit()
            return super().transcribe(path)

    app.dependency_overrides[get_transcriber] = FinishesMeanwhile
    r = answer(client, iv, 1)
    assert r.status_code == 409
    with _session_factory()() as db:
        q2 = db.execute(select(Question).where(Question.id == uuid.UUID(iv["questions"][1]["id"])))
        assert q2.scalar_one().answer is None


def test_complete_retries_if_an_answer_lands_during_the_debrief(client, user):
    iv = new_interview(client)
    answer(client, iv, 0)
    other_q = uuid.UUID(iv["questions"][1]["id"])
    first = uuid.UUID(iv["questions"][0]["id"])

    class AnswerArrives(MockInterviewAI):
        def summarize(self, role, level, items):
            with _session_factory()() as db:
                src = db.execute(select(Answer).where(Answer.question_id == first)).scalar_one()
                cols = {
                    c.key: getattr(src, c.key)
                    for c in Answer.__table__.columns
                    if c.key not in ("id", "question_id", "created_at")
                }
                db.add(Answer(question_id=other_q, **cols))
                db.commit()
            return super().summarize(role, level, items)

    app.dependency_overrides[get_ai] = AnswerArrives
    r = client.post(f"/api/interviews/{iv['id']}/complete")
    assert r.status_code == 409
    app.dependency_overrides.pop(get_ai)
    done = client.post(f"/api/interviews/{iv['id']}/complete").json()
    assert done["status"] == "completed" and done["answered_count"] == 2


def test_rate_limiter_evicts_stale_keys():
    now = [0.0]
    rl = RateLimiter(clock=lambda: now[0], purge_every=3)
    rl.check("a", 5, 60)
    rl.check("b", 5, 60)
    assert len(rl) == 2
    now[0] = 4000.0  # past the longest window
    rl.check("c", 5, 60)  # third call triggers a purge
    assert len(rl) == 1


def test_audio_dir_default_is_relative_to_workdir(settings):
    assert not Path(settings.audio_dir).is_absolute()
