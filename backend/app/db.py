from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    # PgBouncer in transaction mode (Neon's -pooler hosts) can't follow server-side
    # prepared statements between connections, so psycopg must never create them.
    connect_args = {"prepare_threshold": None} if settings.uses_pgbouncer else {}
    if settings.database_pooling:
        return create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
    # Serverless: no pool of our own; the database's pooler does the pooling.
    return create_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={"prepare_threshold": None},
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session
