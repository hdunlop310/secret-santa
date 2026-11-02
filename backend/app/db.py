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
    if settings.database_pooling:
        return create_engine(settings.database_url, pool_pre_ping=True)
    # Serverless: no pool of our own, and no server-side prepared statements, which a
    # transaction-mode pooler such as PgBouncer can't follow between connections.
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
