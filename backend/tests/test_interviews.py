from pathlib import Path

import pytest

from interview_api.ai import get_ai, get_transcriber
from interview_api.ai.base import AIError, Transcript, Word
from interview_api.ai.mock import MockInterviewAI, MockTranscriber
from interview_api.main import app

from .conftest import answer, fake_audio, new_interview, signup


class SpyTranscriber(MockTranscriber):
    """Records the path it was given and whether the file existed during transcription."""

    def __init__(self):
        self.paths: list[Path] = []
        self.existed: list[bool] = []

    def transcribe(self, path):
        self.paths.append(Path(path))
        self.existed.append(Path(path).exists())
        return super().transcribe(path)


class SilentTranscriber(MockTranscriber):
    def transcribe(self, path):
        return Transcript(text="", words=[], duration=4.0, model=self.model_name)


def test_meta(client):
    m = client.get("/api/meta").json()
    assert "Data Analyst" in m["roles"] and "Senior" in m["levels"]
    assert m["ai_mode"] == "demo"
    assert m["transcriber"] == "mock-whisper"


def test_create_interview_mix_and_hidden_guidance(client, user):
    iv = new_interview(client, n=5)
    assert iv["status"] == "in_progress" and iv["role"] == "Data Analyst"
    kinds = [q["kind"] for q in iv["questions"]]
    assert len(kinds) == 5 and kinds.count("behavioural") == 2 and kinds.count("technical") == 3
    assert [q["position"] for q in iv["questions"]] == [1, 2, 3, 4, 5]
    assert all(q["guidance"] is None for q in iv["questions"])  # revealed after answering


@pytest.mark.parametrize(
    "body",
    [
        {"role": "Astronaut", "level": "Junior"},
        {"role": "Data Analyst", "level": "Wizard"},
        {"role": "Data Analyst", "level": "Junior", "num_questions": 2},
        {"role": "Data Analyst", "level": "Junior", "num_questions": 9},
        {"role": "Data Analyst", "level": "Junior", "extra": 1},
    ],
)
def test_create_interview_validation(client, user, body):
    assert client.post("/api/interviews", json=body).status_code == 422


def test_full_flow_answer_complete_history(client, user):
    iv = new_interview(client, n=3)
    for i in range(3):
        r = answer(client, iv, i)
        assert r.status_code == 200, r.text
        q = r.json()
        a = q["answer"]
        assert q["guidance"]  # revealed now
        assert a["transcript"].startswith("So um in my last project")
        assert a["filler_count"] >= 1 and a["fillers"].get("um") == 1
        assert a["long_pause_count"] == 1
        assert 0 <= a["content_score"] <= 100 and 0 <= a["clarity_score"] <= 100
        assert a["audio_kept"] is False
        assert a["feedback"]["clarity_notes"]

    done = client.post(f"/api/interviews/{iv['id']}/complete")
    assert done.status_code == 200
    body = done.json()
    assert body["status"] == "completed" and body["completed_at"]
    overall = [q["answer"]["overall_score"] for q in body["questions"]]
    assert body["overall_score"] == pytest.approx(sum(overall) / 3, abs=0.06)
    assert body["summary"]["strengths"] and body["summary"]["skipped_questions"] == 0

    listed = client.get("/api/interviews").json()
    assert len(listed) == 1 and listed[0]["answered_count"] == 3

    # Completing again is a no-op; answering after completion is refused.
    assert client.post(f"/api/interviews/{iv['id']}/complete").status_code == 200
    assert answer(client, iv, 0).status_code == 409


def test_reanswer_replaces_previous(client, user):
    iv = new_interview(client)
    first = answer(client, iv, 0).json()["answer"]["id"]
    second = answer(client, iv, 0).json()["answer"]["id"]
    assert first != second
    detail = client.get(f"/api/interviews/{iv['id']}").json()
    assert detail["questions"][0]["answer"]["id"] == second


def test_complete_requires_an_answer_and_counts_skips(client, user):
    iv = new_interview(client, n=3)
    assert client.post(f"/api/interviews/{iv['id']}/complete").status_code == 409
    answer(client, iv, 0)
    body = client.post(f"/api/interviews/{iv['id']}/complete").json()
    assert body["summary"]["skipped_questions"] == 2


def test_upload_errors(client, user, settings, monkeypatch):
    iv = new_interview(client)
    q = iv["questions"][0]
    url = f"/api/interviews/{iv['id']}/questions/{q['id']}/answer"
    assert client.post(url, files=fake_audio(ctype="text/plain")).status_code == 415
    assert client.post(url, files=fake_audio(n=0)).status_code in (200, 422)
    monkeypatch.setattr(settings, "max_audio_bytes", 1000)
    assert client.post(url, files=fake_audio(n=5000)).status_code == 413
    bogus = f"/api/interviews/{iv['id']}/questions/00000000-0000-0000-0000-000000000000/answer"
    assert client.post(bogus, files=fake_audio()).status_code == 404


def test_codec_parameter_in_content_type_is_accepted(client, user):
    iv = new_interview(client)
    r = answer(client, iv, 0, ctype="audio/webm;codecs=opus")
    assert r.status_code == 200


def test_no_speech_is_422(client, user):
    app.dependency_overrides[get_transcriber] = SilentTranscriber
    iv = new_interview(client)
    r = answer(client, iv, 0)
    assert r.status_code == 422 and "No speech" in r.json()["detail"]


def test_raw_audio_deleted_after_transcription(client, user):
    spy = SpyTranscriber()
    app.dependency_overrides[get_transcriber] = lambda: spy
    iv = new_interview(client)
    assert answer(client, iv, 0).status_code == 200
    assert spy.existed == [True]  # the file was there while transcribing...
    assert not spy.paths[0].exists()  # ...and is gone afterwards
    assert not spy.paths[0].parent.exists()


def test_raw_audio_deleted_even_when_transcription_fails(client, user):
    seen = []

    class Boom(MockTranscriber):
        def transcribe(self, path):
            seen.append(Path(path))
            raise AIError("decoder exploded", status=422)

    app.dependency_overrides[get_transcriber] = Boom
    iv = new_interview(client)
    assert answer(client, iv, 0).status_code == 422
    assert seen and not seen[0].exists()


def test_keep_audio_opt_in(client, user, settings, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "keep_audio", True)
    monkeypatch.setattr(settings, "audio_dir", str(tmp_path))
    iv = new_interview(client)
    r = answer(client, iv, 0)
    assert r.json()["answer"]["audio_kept"] is True
    assert len(list(tmp_path.rglob("*.webm"))) == 1


def test_ai_errors_become_503_with_retry_after(client, user):
    class Busy(MockInterviewAI):
        def generate_questions(self, *a, **k):
            raise AIError("busy", retry_after=42, status=503)

    app.dependency_overrides[get_ai] = Busy
    r = client.post("/api/interviews", json={"role": "Data Analyst", "level": "Junior"})
    assert r.status_code == 503 and r.headers["retry-after"] == "42"


def test_previous_questions_are_passed_as_avoid_list(client, user):
    seen = []

    class Recording(MockInterviewAI):
        def generate_questions(self, role, level, n, avoid):
            seen.append(list(avoid))
            return super().generate_questions(role, level, n, avoid)

    app.dependency_overrides[get_ai] = Recording
    first = new_interview(client, role="Data Analyst")
    new_interview(client, role="Data Analyst")
    new_interview(client, role="Product Manager")
    assert seen[0] == []
    assert set(seen[1]) == {q["text"] for q in first["questions"]}
    assert seen[2] == []  # other roles' questions aren't relevant


def test_interview_rate_limit(client, user, settings, monkeypatch):
    monkeypatch.setattr(settings, "rate_interviews_per_hour", 2)
    new_interview(client)
    new_interview(client)
    r = client.post("/api/interviews", json={"role": "Data Analyst", "level": "Junior"})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_answer_rate_limit_is_per_user(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "rate_answers_per_hour", 1)
    signup(client, "a@example.com")
    iv = new_interview(client)
    assert answer(client, iv, 0).status_code == 200
    assert answer(client, iv, 1).status_code == 429
    client.post("/api/auth/logout")
    signup(client, "b@example.com")
    iv_b = new_interview(client)
    assert answer(client, iv_b, 0).status_code == 200


def test_delete_interview(client, user):
    iv = new_interview(client)
    answer(client, iv, 0)
    assert client.delete(f"/api/interviews/{iv['id']}").status_code == 204
    assert client.get(f"/api/interviews/{iv['id']}").status_code == 404


def test_word_timings_are_stored(client, user):
    class Two(MockTranscriber):
        def transcribe(self, path):
            words = [Word("Hello", 0.0, 0.4), Word("there.", 0.5, 0.9)]
            return Transcript("Hello there.", words, 1.2, self.model_name)

    app.dependency_overrides[get_transcriber] = Two
    iv = new_interview(client)
    answer(client, iv, 0)
    from interview_api.db import _session_factory
    from interview_api.models import Answer

    with _session_factory()() as db:
        a = db.query(Answer).one()
        assert a.words == [
            {"w": "Hello", "start": 0.0, "end": 0.4},
            {"w": "there.", "start": 0.5, "end": 0.9},
        ]
        assert a.word_count == 2 and a.audio_seconds == 1.2
