"""Signed unsubscribe links.

Footers can't carry personal link tokens (only their hashes are stored, and they grant
far more than unsubscribing). Instead each link is an HMAC over who it's for, so it can
only ever stop reminders for that one participant or admin.
"""

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Literal

from app.config import get_settings

Kind = Literal["p", "a"]  # participant, or a group's admin
_TOKEN_RE = re.compile(r"^([pa])(\d{1,12})\.([0-9a-f]{32})$")


@dataclass(frozen=True)
class UnsubscribeLinks:
    page: str  # the frontend page linked from the email footer
    one_click: str  # RFC 8058 List-Unsubscribe target on the API


def _signature(kind: Kind, ident: int) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, f"unsubscribe:{kind}:{ident}".encode(), hashlib.sha256).hexdigest()[:32]


def make_token(kind: Kind, ident: int) -> str:
    return f"{kind}{ident}.{_signature(kind, ident)}"


def parse_token(token: str) -> tuple[Kind, int] | None:
    match = _TOKEN_RE.match(token)
    if not match:
        return None
    kind, ident, signature = match.group(1), int(match.group(2)), match.group(3)
    if not hmac.compare_digest(signature, _signature(kind, ident)):  # type: ignore[arg-type]
        return None
    return kind, ident  # type: ignore[return-value]


def links(kind: Kind, ident: int) -> UnsubscribeLinks:
    settings = get_settings()
    token = make_token(kind, ident)
    return UnsubscribeLinks(
        page=f"{settings.app_base_url}/unsubscribe/{token}",
        one_click=f"{settings.api_base_url}/unsubscribe/{token}",
    )
