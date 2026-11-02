from datetime import UTC, datetime

from fastapi import APIRouter

from app.models import Group, Participant
from app.security import DB, NOT_FOUND
from app.unsubscribe import parse_token

router = APIRouter()


@router.post("/unsubscribe/{token}")
def unsubscribe(token: str, db: DB) -> dict[str, str]:
    """Stop reminder emails. Links and draw notices still arrive.

    Also the RFC 8058 one-click target, so it works as a single bare POST.
    """
    parsed = parse_token(token)
    if parsed is None:
        raise NOT_FOUND
    kind, ident = parsed
    target = db.get(Participant, ident) if kind == "p" else db.get(Group, ident)
    if target is None:
        raise NOT_FOUND
    now = datetime.now(UTC)
    if isinstance(target, Participant):
        target.unsubscribed_at = target.unsubscribed_at or now
    else:
        target.admin_unsubscribed_at = target.admin_unsubscribed_at or now
    db.commit()
    return {"status": "unsubscribed"}
