import pytest

from interview_api.config import Settings


@pytest.mark.parametrize(
    "url,expected",
    [
        ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgresql://u:p@h/db?sslmode=require", "postgresql+psycopg://u:p@h/db?sslmode=require"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ],
)
def test_database_url_gets_psycopg_driver(url, expected):
    assert Settings(database_url=url).database_url == expected


def test_live_mode_requires_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        Settings(ai_mode="live", gemini_api_key="")


def test_groq_requires_key():
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        Settings(transcriber="groq", groq_api_key="")


def test_auto_mode_uses_gemini_only_with_a_key():
    assert Settings(ai_mode="auto", gemini_api_key="k").gemini_enabled
    assert not Settings(ai_mode="auto", gemini_api_key="").gemini_enabled
