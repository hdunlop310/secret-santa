from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import RateLimitHit
from app.ratelimit import RateLimiter

T0 = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


@pytest.fixture
def limiter():
    return RateLimiter()


def test_blocks_after_limit_within_the_window(db, limiter):
    assert all(limiter.hit(db, "b", "k", 3, now=T0 + timedelta(minutes=m)) for m in (0, 1, 2))
    assert not limiter.hit(db, "b", "k", 3, now=T0 + timedelta(minutes=3))


def test_window_slides(db, limiter):
    for m in (0, 1, 2):
        limiter.hit(db, "b", "k", 3, now=T0 + timedelta(minutes=m))
    assert limiter.hit(db, "b", "k", 3, now=T0 + timedelta(minutes=61))


def test_keys_and_buckets_are_separate_and_case_insensitive(db, limiter):
    limiter.hit(db, "b", "Sam@Example.com", 1, now=T0)
    assert not limiter.hit(db, "b", "sam@example.com", 1, now=T0)
    assert limiter.hit(db, "b", "other", 1, now=T0)
    assert limiter.hit(db, "other", "sam@example.com", 1, now=T0)


def test_refused_hits_are_not_recorded(db, limiter):
    limiter.hit(db, "b", "k", 1, now=T0)
    for _ in range(5):
        limiter.hit(db, "b", "k", 1, now=T0)
    assert limiter.hit(db, "b", "k", 1, now=T0 + timedelta(minutes=61))


def test_check_raises_429(db, limiter):
    limiter.check(db, "b", "k", 1)
    with pytest.raises(HTTPException) as exc:
        limiter.check(db, "b", "k", 1)
    assert exc.value.status_code == 429


def test_keys_are_stored_only_as_hashes(db, limiter):
    limiter.hit(db, "email_to", "sam@example.com", 5, now=T0)
    limiter.hit(db, "email_ip", "203.0.113.7", 5, now=T0)
    rows = db.scalars(select(RateLimitHit)).all()
    stored = " ".join(f"{r.bucket} {r.key_hash}" for r in rows)
    assert "sam@example.com" not in stored and "203.0.113.7" not in stored
    assert all(len(r.key_hash) == 64 for r in rows)


def test_old_hits_are_deleted(db, limiter):
    limiter.hit(db, "b", "old", 5, now=T0 - timedelta(days=2))
    limiter.hit(db, "b", "new", 5, now=T0)
    assert limiter.delete_old(db, T0) == 1
    db.commit()
    assert len(db.scalars(select(RateLimitHit)).all()) == 1


def test_limits_are_shared_between_separate_sessions(engine, db, limiter):
    """What serverless needs: two app instances see each other's hits."""
    from sqlalchemy.orm import sessionmaker

    other = sessionmaker(bind=engine)()
    try:
        limiter.hit(db, "b", "k", 2, now=T0)
        limiter.hit(other, "b", "k", 2, now=T0)
        assert not limiter.hit(db, "b", "k", 2, now=T0)
    finally:
        other.close()
