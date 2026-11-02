"""Signed "open" links that emails carry instead of personal links.

Personal and admin tokens are stored only as hashes, so an email sent later (a reminder,
the draw, a lost-link request) can't include them. It carries a signed link instead:
an HMAC over who it's for and when it expires. Opening it issues a fresh random link
token (stored hashed) for that person, so older links keep working.
"""

import hashlib
import hmac
import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from app.config import get_settings

Kind = Literal["p", "a"]  # participant, or a group's admin
_TOKEN_RE = re.compile(r"^([pa])(\d{1,12})\.(\d{1,12})\.([0-9a-f]{32})$")

LOST_LINK_LIFETIME = timedelta(hours=24)
KEEP_AFTER_GIFT_DATE = timedelta(days=30)  # matches when the group is deleted


def _signature(kind: Kind, ident: int, expires: int) -> str:
    key = get_settings().secret_key.encode()
    message = f"open:{kind}:{ident}:{expires}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()[:32]


def make_token(kind: Kind, ident: int, expires_at: datetime) -> str:
    expires = int(expires_at.timestamp())
    return f"{kind}{ident}.{expires}.{_signature(kind, ident, expires)}"


def parse_token(token: str, now: datetime | None = None) -> tuple[Kind, int] | None:
    match = _TOKEN_RE.match(token)
    if not match:
        return None
    kind, ident, expires = match.group(1), int(match.group(2)), int(match.group(3))
    signature = match.group(4)
    if not hmac.compare_digest(signature, _signature(kind, ident, expires)):  # type: ignore[arg-type]
        return None
    if (now or datetime.now(UTC)).timestamp() > expires:
        return None
    return kind, ident  # type: ignore[return-value]


def until_group_deleted(gift_date: date) -> datetime:
    return datetime.combine(gift_date, time.max, tzinfo=UTC) + KEEP_AFTER_GIFT_DATE


def open_link(kind: Kind, ident: int, expires_at: datetime) -> str:
    return f"{get_settings().app_base_url}/open/{make_token(kind, ident, expires_at)}"
