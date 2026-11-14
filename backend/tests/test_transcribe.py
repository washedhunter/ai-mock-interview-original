"""Transcribers with fakes: no Whisper model is loaded and no network call is made."""

from types import SimpleNamespace

import httpx
import pytest

from interview_api.ai.base import AIError
from interview_api.ai.transcribe import FILLER_PROMPT, GroqWhisper, LocalWhisper


@pytest.fixture
def audio(tmp_path):
    p = tmp_path / "a.webm"
    p.write_bytes(b"fake")
    return p


def groq_with(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GroqWhisper("k", client=client)


def test_groq_parses_words_and_sends_word_granularity(audio):
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.content.decode(errors="ignore")
        return httpx.Response(
            200,
            json={
                "text": " Um, hello there.",
                "duration": 3.2,
                "words": [
                    {"word": "Um,", "start": 0.0, "end": 0.3},
                    {"word": " hello", "start": 0.5, "end": 0.9},
                    {"word": "there.", "start": 1.0, "end": 1.4},
                ],
            },
        )

    t = groq_with(handler).transcribe(audio)
    assert t.text == "Um, hello there."
    assert [w.w for w in t.words] == ["Um,", "hello", "there."]
    assert t.duration == 3.2 and t.model == "groq/whisper-large-v3-turbo"
    assert seen["auth"] == "Bearer k"
    assert 'name="timestamp_granularities[]"' in seen["body"] and "word" in seen["body"]
    assert "verbose_json" in seen["body"] and FILLER_PROMPT in seen["body"]


def test_groq_rate_limit(audio):
    g = groq_with(lambda r: httpx.Response(429, headers={"retry-after": "12"}))
    with pytest.raises(AIError) as e:
        g.transcribe(audio)
    assert e.value.status == 503 and e.value.retry_after == 12


def test_groq_bad_audio_is_422(audio):
    g = groq_with(lambda r: httpx.Response(400, json={"error": {"message": "bad file"}}))
    with pytest.raises(AIError) as e:
        g.transcribe(audio)
    assert e.value.status == 422


def test_groq_network_error(audio):
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(AIError):
        groq_with(handler).transcribe(audio)


def test_local_whisper_uses_word_timestamps_and_filler_prompt(audio, monkeypatch):
    calls = {}

    class FakeModel:
        def transcribe(self, path, **kw):
            calls.update(kw, path=path)
            seg = SimpleNamespace(
                words=[
                    SimpleNamespace(word=" Um,", start=0.1, end=0.3),
                    SimpleNamespace(word=" ", start=0.3, end=0.3),  # blank tokens are dropped
                    SimpleNamespace(word=" yes.", start=2.9, end=3.2),
                ]
            )
            return iter([seg]), SimpleNamespace(duration=4.0, language="en")

    lw = LocalWhisper("base.en")
    monkeypatch.setattr(lw, "_get_model", lambda: FakeModel())
    t = lw.transcribe(audio)
    assert [w.w for w in t.words] == ["Um,", "yes."]
    assert t.text == "Um, yes." and t.duration == 4.0 and t.model == "faster-whisper/base.en"
    assert calls["word_timestamps"] is True and calls["vad_filter"] is True
    assert calls["initial_prompt"] == FILLER_PROMPT and calls["language"] == "en"


def test_local_whisper_decode_error_is_422(audio, monkeypatch):
    class Broken:
        def transcribe(self, path, **kw):
            raise RuntimeError("Invalid data found when processing input")

    lw = LocalWhisper()
    monkeypatch.setattr(lw, "_get_model", lambda: Broken())
    with pytest.raises(AIError) as e:
        lw.transcribe(audio)
    assert e.value.status == 422
