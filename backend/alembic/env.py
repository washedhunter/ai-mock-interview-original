from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text

from interview_api.config import get_settings
from interview_api.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    # Tests pass a URL explicitly; everything else uses DATABASE_URL.
    return config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            # Serverless hosts can start several containers at once, and each runs
            # `alembic upgrade head` on boot; a transaction-scoped advisory lock makes them take turns.
            connection.execute(text("SELECT pg_advisory_xact_lock(724110)"))
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
