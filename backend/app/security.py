"""Link tokens and the auth dependencies built on them.

Admin and participant tokens are random 256-bit values. Only their SHA-256 hashes are
stored, so a database leak does not expose working links. Tokens are never logged.

Each admin or participant has a main token plus up to MAX_EXTRA_LINKS extra ones
(link_tokens), created when they open a link from an email, so a new link never breaks
an older one. The organiser's admin link also works as their own participant link when
they take part, so they only ever need one link.
"""

import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Group, LinkToken, Participant

TOKEN_BYTES = 32
MAX_EXTRA_LINKS = 20


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


def _extra_link(db: Session, token: str) -> LinkToken | None:
    link = db.scalar(select(LinkToken).where(LinkToken.token_hash == hash_token(token)))
    if link is None or not tokens_match(token, link.token_hash):
        return None
    return link


def find_admin_group(db: Session, token: str) -> Group | None:
    token_hash = hash_token(token)
    group = db.scalar(select(Group).where(Group.admin_token_hash == token_hash))
    if group is not None and tokens_match(token, group.admin_token_hash):
        return group
    link = _extra_link(db, token)
    if link is not None and link.participant_id is None:
        return db.get(Group, link.group_id)
    return None


def admin_participant(group: Group) -> Participant | None:
    """The organiser's own participant record, if they're taking part."""
    return next((p for p in group.participants if p.is_admin), None)


def find_participant(db: Session, token: str, allow_admin: bool = True) -> Participant | None:
    """A participant from their own link, or the organiser from their admin link."""
    token_hash = hash_token(token)
    participant = db.scalar(select(Participant).where(Participant.token_hash == token_hash))
    if participant is not None and tokens_match(token, participant.token_hash):
        return participant
    link = _extra_link(db, token)
    if link is not None and link.participant_id is not None:
        return db.get(Participant, link.participant_id)
    if not allow_admin:
        return None
    group = find_admin_group(db, token)
    return admin_participant(group) if group is not None else None


def issue_link(db: Session, group: Group, participant: Participant | None) -> str:
    """Create an extra working link (admin when participant is None), dropping the oldest
    beyond MAX_EXTRA_LINKS. The caller commits."""
    token = new_token()
    db.add(
        LinkToken(
            group_id=group.id,
            participant_id=participant.id if participant else None,
            token_hash=hash_token(token),
        )
    )
    db.flush()
    holder = (
        LinkToken.participant_id == participant.id
        if participant
        else (LinkToken.group_id == group.id) & LinkToken.participant_id.is_(None)
    )
    ids = db.scalars(select(LinkToken.id).where(holder).order_by(LinkToken.id.desc())).all()
    for old_id in ids[MAX_EXTRA_LINKS:]:
        db.delete(db.get(LinkToken, old_id))
    return token


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


def require_own_participant(db: DB, token: Token) -> Participant:
    """A participant's own link only: the organiser's admin link doesn't count."""
    participant = find_participant(db, token, allow_admin=False)
    if participant is None:
        raise NOT_FOUND
    return participant


AdminGroup = Annotated[Group, Depends(require_admin)]
OwnParticipant = Annotated[Participant, Depends(require_own_participant)]
CurrentParticipant = Annotated[Participant, Depends(require_participant)]
Member = Annotated[Caller, Depends(require_member)]
