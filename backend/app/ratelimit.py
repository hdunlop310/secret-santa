"""In-process sliding-window rate limiter.

Good enough for a single API instance. If the API ever runs as several instances, move
the counters to Postgres or Redis.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import get_settings


class RateLimiter:
    def __init__(self, window_seconds: float = 3600) -> None:
        self.window = window_seconds
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, bucket: str, key: str, limit: int, now: float | None = None) -> bool:
        """Record a hit; return False if the key is over its limit for the window."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[(bucket, key)]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def check(self, bucket: str, key: str, limit: int) -> None:
        if not self.hit(bucket, key, limit):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
            )

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


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
