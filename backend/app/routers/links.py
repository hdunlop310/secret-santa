"""Opening links from emails, and the lost-link page."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.access import LOST_LINK_LIFETIME, open_link, parse_token
from app.email import send_safely, templates
from app.models import Group, Participant
from app.routers.groups import Sender, check_email_rate
from app.schemas import LostLinkRequest, OpenedLink
from app.security import DB, NOT_FOUND, issue_link
from app.services import admin_link, participant_link

router = APIRouter()


@router.post("/links/open/{token}", response_model=OpenedLink)
def open_from_email(token: str, db: DB) -> OpenedLink:
    """Swap a signed email link for a fresh working link. Older links keep working."""
    parsed = parse_token(token) if len(token) <= 128 else None
    if parsed is None:
        raise NOT_FOUND
    kind, ident = parsed
    if kind == "a":
        group = db.get(Group, ident)
        if group is None:
            raise NOT_FOUND
        link = admin_link(issue_link(db, group, None))
        db.commit()
        return OpenedLink(kind="admin", link=link)
    participant = db.get(Participant, ident)
    if participant is None:
        raise NOT_FOUND
    participant.joined_at = participant.joined_at or datetime.now(UTC)
    link = participant_link(issue_link(db, participant.group, participant))
    db.commit()
    return OpenedLink(kind="participant", link=link)


@router.post("/links/lost", status_code=status.HTTP_202_ACCEPTED)
def lost_link(body: LostLinkRequest, request: Request, db: DB, sender: Sender) -> dict[str, str]:
    """Email links to every group this address is in. The response never says whether
    it's in any, so the page can't be used to find out who uses the app."""
    check_email_rate(db, request, body.email)
    expires = datetime.now(UTC) + LOST_LINK_LIFETIME
    found: list[tuple[str, str]] = []
    admin_groups = db.scalars(select(Group).where(Group.admin_email == body.email)).all()
    for group in admin_groups:
        found.append((group.name, f"{open_link('a', group.id, expires)}?to=group"))
    admin_ids = {g.id for g in admin_groups}
    for p in db.scalars(select(Participant).where(Participant.email == body.email)).all():
        if p.group_id in admin_ids and p.is_admin:
            continue  # the organiser's link above covers their own wish list
        found.append((p.group.name, f"{open_link('p', p.id, expires)}?to=wishlist"))
    if found:
        send_safely(sender, templates.lost_links(body.email, found))
    return {"status": "sent"}
