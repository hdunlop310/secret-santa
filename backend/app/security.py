"""Link tokens and the auth dependencies built on them.

Admin and participant tokens are random 256-bit values. Only their SHA-256 hashes are
stored, so a database leak does not expose working links. Tokens are never logged.
"""

import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Group, Participant

TOKEN_BYTES = 32


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(token: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), stored_hash)


# One response for every auth failure, so a caller cannot tell a malformed token from an
# unknown one or a token for a different group.
NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")


def bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 128:
        raise NOT_FOUND
    return token.strip()


def find_admin_group(db: Session, token: str) -> Group | None:
    token_hash = hash_token(token)
    group = db.scalar(select(Group).where(Group.admin_token_hash == token_hash))
    if group is None or not tokens_match(token, group.admin_token_hash):
        return None
    return group


def find_participant(db: Session, token: str) -> Participant | None:
    token_hash = hash_token(token)
    participant = db.scalar(select(Participant).where(Participant.token_hash == token_hash))
    if participant is None or not tokens_match(token, participant.token_hash):
        return None
    return participant


DB = Annotated[Session, Depends(get_db)]
Token = Annotated[str, Depends(bearer_token)]


def require_admin(db: DB, token: Token) -> Group:
    group = find_admin_group(db, token)
    if group is None:
        raise NOT_FOUND
    return group


def require_participant(db: DB, token: Token) -> Participant:
    participant = find_participant(db, token)
    if participant is None:
        raise NOT_FOUND
    return participant


class Caller:
    """Either the admin of a group or one of its participants."""

    def __init__(self, group: Group, participant: Participant | None) -> None:
        self.group = group
        self.participant = participant

    @property
    def is_admin(self) -> bool:
        return self.participant is None


def require_member(db: DB, token: Token) -> Caller:
    group = find_admin_group(db, token)
    if group is not None:
        return Caller(group, None)
    participant = find_participant(db, token)
    if participant is not None:
        return Caller(participant.group, participant)
    raise NOT_FOUND


AdminGroup = Annotated[Group, Depends(require_admin)]
CurrentParticipant = Annotated[Participant, Depends(require_participant)]
Member = Annotated[Caller, Depends(require_member)]
