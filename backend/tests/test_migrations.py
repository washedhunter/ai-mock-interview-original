"""Alembic migrations create exactly the schema the ORM models describe, and downgrade cleanly."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from interview_api.db import get_engine
from interview_api.models import Base

from .conftest import alembic_config


def test_models_match_migrations():
    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_downgrade_and_upgrade_again():
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    tables = set(inspect(get_engine()).get_table_names())
    assert tables <= {"alembic_version"}
    command.upgrade(cfg, "head")
    tables = set(inspect(get_engine()).get_table_names())
    assert {"users", "sessions", "interviews", "questions", "answers"} <= tables
    with get_engine().connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"
