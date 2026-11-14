"""All settings come from environment variables (or a local .env file)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- database -----------------------------------------------------------------------------
    database_url: str = "postgresql+psycopg://interview:interview@localhost:5432/interview"

    # --- AI -------------------------------------------------------------------------------------
    # auto = Gemini when GEMINI_API_KEY is set, otherwise canned responses (labelled "demo mode").
    ai_mode: Literal["auto", "live", "mock"] = "auto"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_s: float = 90.0
    gemini_max_attempts: int = 4

    # local = faster-whisper in this process; groq = Whisper on Groq's API; mock = canned transcript
    transcriber: Literal["local", "groq", "mock"] = "local"
    whisper_model: str = "base.en"
    whisper_compute_type: str = "int8"
    whisper_cpu_threads: int = 0  # 0 = let CTranslate2 decide
    whisper_download_root: str | None = None
    warm_up_transcriber: bool = True  # load the Whisper model at start-up, not on the first answer
    groq_api_key: str = ""
    groq_whisper_model: str = "whisper-large-v3-turbo"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # --- audio --------------------------------------------------------------------------------
    keep_audio: bool = False  # raw audio is deleted right after transcription unless this is true
    audio_dir: str = "audio"  # only used when keep_audio is true
    max_audio_bytes: int = 15 * 1024 * 1024
    max_answer_seconds: int = 240

    # --- accounts -----------------------------------------------------------------------------
    session_cookie_name: str = "mi_session"
    session_days: int = 14
    cookie_secure: bool = False  # set true behind HTTPS
    trust_proxy_headers: bool = (
        True  # use X-Forwarded-For for the client IP (the Next proxy sets it)
    )

    # --- rate limits (per user unless noted) ----------------------------------------------------
    rate_interviews_per_hour: int = 10
    rate_answers_per_hour: int = 60
    rate_completions_per_hour: int = 20
    rate_logins_per_15min: int = 20  # per client IP and per email

    # --- interview + scoring ------------------------------------------------------------------
    min_questions: int = 3
    max_questions: int = 8
    default_questions: int = 5
    content_weight: float = Field(
        0.7, ge=0, le=1
    )  # overall = content_weight*content + (1-w)*clarity
    clarity_computed_weight: float = Field(0.6, ge=0, le=1)  # clarity = w*computed + (1-w)*LLM
    long_pause_seconds: float = 2.0
    ideal_wpm_low: float = 110.0
    ideal_wpm_high: float = 170.0

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        """Managed Postgres add-ons hand out postgres:// or postgresql:// URLs; SQLAlchemy needs
        the driver named (psycopg 3)."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    @model_validator(mode="after")
    def _check(self) -> Settings:
        if self.ai_mode == "live" and not self.gemini_api_key:
            raise ValueError("AI_MODE=live needs GEMINI_API_KEY")
        if self.transcriber == "groq" and not self.groq_api_key:
            raise ValueError("TRANSCRIBER=groq needs GROQ_API_KEY")
        if not self.min_questions <= self.default_questions <= self.max_questions:
            raise ValueError("DEFAULT_QUESTIONS must be between MIN_QUESTIONS and MAX_QUESTIONS")
        return self

    @property
    def gemini_enabled(self) -> bool:
        return self.ai_mode == "live" or (self.ai_mode == "auto" and bool(self.gemini_api_key))


@lru_cache
def get_settings() -> Settings:
    return Settings()
