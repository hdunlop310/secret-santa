from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401 - registers the tables on Base.metadata
from app.config import get_settings
from app.db import Base

config = context.config
if config.config_file_name is not None:
    # Keep app loggers alive when migrations run in-process (tests, app startup).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def database_url() -> str:
    # Tests pass their own URL. Otherwise migrate over the direct connection: Neon's
    # pooled one runs PgBouncer in transaction mode, which migrations can't use.
    return config.attributes.get("database_url") or get_settings().migration_database_url


def run_migrations_offline() -> None:
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
