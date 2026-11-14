"""Whisper speech-to-text.

- LocalWhisper: faster-whisper (CTranslate2) on CPU, int8, word timestamps. Used by
  `docker compose up`. The model is downloaded into the image at build time.
- GroqWhisper: Whisper large-v3-turbo on Groq's API. Used by the free-tier deployment, where the
  container has too little memory for a useful local model.

Whisper tends to "clean up" disfluencies (it drops "um" and "uh"), which would hide filler words.
A disfluent initial prompt nudges it to keep them; how well that works is measured in the README.
"""

from __future__ import annotations

import threading
from pathlib import Path

import httpx

from .base import AIError, Transcript, Word

FILLER_PROMPT = "Um, so, uh, I think, like, the main thing was... you know, hmm, basically, er."


def _clean_words(raw: list[tuple[str, float, float]]) -> list[Word]:
    out = []
    for w, start, end in raw:
        w = w.strip()
        if w:
            out.append(Word(w=w, start=round(float(start), 3), end=round(float(end), 3)))
    return out


class LocalWhisper:
    def __init__(
        self,
        model: str = "base.en",
        compute_type: str = "int8",
        cpu_threads: int = 0,
        download_root: str | None = None,
    ):
        self.model_name = f"faster-whisper/{model}"
        self._spec = (model, compute_type, cpu_threads, download_root)
        self._model = None
        self._load_lock = threading.Lock()
        self._run_lock = threading.Lock()  # one transcription at a time: CPU-bound anyway

    def _get_model(self):
        with self._load_lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                model, compute_type, cpu_threads, root = self._spec
                self._model = WhisperModel(
                    model,
                    device="cpu",
                    compute_type=compute_type,
                    cpu_threads=cpu_threads,
                    download_root=root,
                )
            return self._model

    def transcribe(self, path: Path) -> Transcript:
        model = self._get_model()
        with self._run_lock:
            try:
                segments, info = model.transcribe(
                    str(path),
                    language="en",
                    word_timestamps=True,
                    vad_filter=True,  # skips silence; timestamps still refer to the original audio
                    initial_prompt=FILLER_PROMPT,
                    condition_on_previous_text=False,
                    beam_size=5,
                )
                raw = [
                    (w.word, w.start, w.end)
                    for seg in segments  # a generator: decoding happens here
                    for w in (seg.words or [])
                ]
            except Exception as exc:  # corrupt / unsupported audio
                raise AIError(
                    f"Could not decode the recording ({type(exc).__name__}).", status=422
                ) from exc
        words = _clean_words(raw)
        return Transcript(
            text=" ".join(w.w for w in words),
            words=words,
            duration=float(info.duration),
            model=self.model_name,
            language=info.language,
        )

    def warm_up(self) -> None:
        self._get_model()


class GroqWhisper:
    def __init__(
        self,
        api_key: str,
        model: str = "whisper-large-v3-turbo",
        base_url: str = "https://api.groq.com/openai/v1",
        timeout_s: float = 120.0,
        client: httpx.Client | None = None,
    ):
        self.model_name = f"groq/{model}"
        self._model = model
        self._url = base_url.rstrip("/") + "/audio/transcriptions"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.Client(timeout=timeout_s)

    def transcribe(self, path: Path) -> Transcript:
        path = Path(path)
        data = {
            "model": self._model,
            "language": "en",
            "response_format": "verbose_json",
            "timestamp_granularities[]": "word",
            "prompt": FILLER_PROMPT,
            "temperature": "0",
        }
        try:
            with path.open("rb") as fh:
                r = self._client.post(
                    self._url,
                    headers=self._headers,
                    data=data,
                    files={"file": (path.name, fh, "application/octet-stream")},
                )
        except httpx.HTTPError as exc:
            raise AIError(
                f"The transcription service could not be reached ({type(exc).__name__})."
            ) from exc
        if r.status_code == 429:
            retry = r.headers.get("retry-after")
            raise AIError(
                "The transcription service is busy. Please try again shortly.",
                retry_after=int(float(retry)) if retry else 30,
                status=503,
            )
        if r.status_code == 400:
            raise AIError("The transcription service could not read this recording.", status=422)
        if r.status_code >= 300:
            raise AIError(f"The transcription service failed (HTTP {r.status_code}).")
        body = r.json()
        words = _clean_words([(w["word"], w["start"], w["end"]) for w in body.get("words") or []])
        text = (body.get("text") or "").strip() or " ".join(w.w for w in words)
        duration = body.get("duration")
        if duration is None:
            duration = words[-1].end if words else 0.0
        return Transcript(text=text, words=words, duration=float(duration), model=self.model_name)
