"""Test setup. Everything external is mocked: no Gemini, Groq or Whisper call can happen.

Tests need a PostgreSQL database (the same engine as production). Locally:
    docker run -d --rm --name mi-testdb -p 55432:5432 -e POSTGRES_PASSWORD=postgres postgres:17
CI uses a Postgres service container. Override with TEST_DATABASE_URL.
"""

from __future__ import annotations

import os

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:55432/postgres"
)
# Set before the app is imported. Real env vars beat any backend/.env file, so a developer's
# real keys are never picked up by the tests.
os.environ.update(
    DATABASE_URL=TEST_DB,
    AI_MODE="mock",
    TRANSCRIBER="mock",
    GEMINI_API_KEY="",
    GROQ_API_KEY="",
    WARM_UP_TRANSCRIBER="false",
    KEEP_AUDIO="false",
    COOKIE_SECURE="false",
)

import io  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from interview_api.config import get_settings  # noqa: E402
from interview_api.db import get_engine  # noqa: E402
from interview_api.ratelimit import limiter  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
TABLES = ["answers", "questions", "interviews", "sessions", "users"]


def alembic_config(url: str = TEST_DB) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.attributes["database_url"] = url
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _schema():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    command.upgrade(alembic_config(), "head")
    yield


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
    limiter.reset()

    # Belt and braces: fail loudly if anything tries to build a real Gemini client.
    import google.genai

    def _blocked(*a, **k):
        raise AssertionError("tests must not create a real Gemini client")

    monkeypatch.setattr(google.genai, "Client", _blocked)
    yield
    from interview_api.main import app

    app.dependency_overrides.clear()


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def client():
    from interview_api.main import app

    with TestClient(app) as c:
        yield c


def signup(client: TestClient, email: str = "asha@example.com", password: str = "correct horse 1"):
    r = client.post("/api/auth/signup", json={"email": email, "password": password, "name": "Asha"})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def user(client):
    return signup(client)


def fake_audio(n: int = 2048, ctype: str = "audio/webm"):
    return {"audio": ("answer.webm", io.BytesIO(b"\x1a\x45\xdf\xa3" + b"\0" * n), ctype)}


def new_interview(
    client: TestClient, role: str = "Data Analyst", level: str = "Junior", n: int = 3
):
    r = client.post("/api/interviews", json={"role": role, "level": level, "num_questions": n})
    assert r.status_code == 201, r.text
    return r.json()


def answer(client: TestClient, iv: dict, idx: int = 0, **kw):
    q = iv["questions"][idx]
    return client.post(
        f"/api/interviews/{iv['id']}/questions/{q['id']}/answer", files=fake_audio(**kw)
    )
