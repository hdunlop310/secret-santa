"""Sliding-window rate limits, stored in Postgres.

Kept in the database rather than in memory because serverless hosts run many short-lived
copies of the app that share nothing else. Keys (IP addresses, email addresses) are
stored only as SHA-256 hashes, and rows older than a day are deleted by the jobs.
"""

import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import RateLimitHit

WINDOW = timedelta(hours=1)
KEEP = timedelta(days=1)


def _key_hash(bucket: str, key: str) -> str:
    return hashlib.sha256(f"{bucket}:{key.lower()}".encode()).hexdigest()


class RateLimiter:
    def hit(
        self, db: Session, bucket: str, key: str, limit: int, now: datetime | None = None
    ) -> bool:
        """Record a hit and commit it; return False, recording nothing, if over the limit."""
        now = now or datetime.now(UTC)
        key_hash = _key_hash(bucket, key)
        recent = db.scalar(
            select(func.count()).where(
                RateLimitHit.bucket == bucket,
                RateLimitHit.key_hash == key_hash,
                RateLimitHit.hit_at > now - WINDOW,
            )
        )
        if recent >= limit:
            return False
        db.add(RateLimitHit(bucket=bucket, key_hash=key_hash, hit_at=now))
        db.commit()
        return True

    def check(self, db: Session, bucket: str, key: str, limit: int) -> None:
        if not self.hit(db, bucket, key, limit):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
            )

    def delete_old(self, db: Session, now: datetime) -> int:
        result = db.execute(delete(RateLimitHit).where(RateLimitHit.hit_at < now - KEEP))
        return result.rowcount or 0


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """The caller's IP. Behind N trusted proxies, the Nth X-Forwarded-For entry from the
    right is the address the outermost proxy saw; anything further left is client-supplied."""
    hops = get_settings().trusted_proxy_hops
    if hops > 0:
        forwarded = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",")]
        forwarded = [h for h in forwarded if h]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.client.host if request.client else "unknown"
