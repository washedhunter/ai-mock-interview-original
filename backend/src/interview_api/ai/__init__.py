"""Provider selection from settings. Tests override these via FastAPI dependency overrides."""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import AIError, InterviewAI, Transcriber

__all__ = ["AIError", "get_ai", "get_transcriber"]


@lru_cache
def get_ai() -> InterviewAI:
    s = get_settings()
    if s.gemini_enabled:
        from .gemini import GeminiInterviewAI

        return GeminiInterviewAI(
            s.gemini_model,
            api_key=s.gemini_api_key,
            max_attempts=s.gemini_max_attempts,
            timeout_s=s.gemini_timeout_s,
        )
    from .mock import MockInterviewAI

    return MockInterviewAI()


@lru_cache
def get_transcriber() -> Transcriber:
    s = get_settings()
    if s.transcriber == "groq":
        from .transcribe import GroqWhisper

        return GroqWhisper(s.groq_api_key, s.groq_whisper_model, s.groq_base_url)
    if s.transcriber == "mock":
        from .mock import MockTranscriber

        return MockTranscriber()
    from .transcribe import LocalWhisper

    return LocalWhisper(
        s.whisper_model, s.whisper_compute_type, s.whisper_cpu_threads, s.whisper_download_root
    )
