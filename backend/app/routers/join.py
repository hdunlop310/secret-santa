from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app.email import send_safely, templates
from app.models import Group, Participant
from app.routers.groups import Sender, check_email_rate
from app.schemas import InvitePreview, JoinRequest
from app.security import DB, NOT_FOUND, hash_token, new_token
from app.services import MAX_PARTICIPANTS, participant_link
from app.unsubscribe import links as unsubscribe_links

router = APIRouter()


def _group_for_invite(db: DB, invite_token: str) -> Group:
    if len(invite_token) > 128:
        raise NOT_FOUND
    group = db.scalar(select(Group).where(Group.invite_token == invite_token))
    if group is None:
        raise NOT_FOUND
    return group


@router.get("/join/{invite_token}", response_model=InvitePreview)
def invite_preview(invite_token: str, db: DB) -> InvitePreview:
    group = _group_for_invite(db, invite_token)
    return InvitePreview(
        group_name=group.name,
        admin_name=group.admin_name,
        gift_date=group.gift_date,
        budget_min=group.budget_min,
        budget_max=group.budget_max,
        message=group.message,
    )


@router.post("/join/{invite_token}", status_code=status.HTTP_202_ACCEPTED)
def join(
    invite_token: str,
    body: JoinRequest,
    request: Request,
    db: DB,
    sender: Sender,
) -> dict[str, str]:
    """Join a group, or get a fresh link if this email is already in it.

    Both cases return the same response, so the endpoint can't be used to find out who
    is in a group. A re-send replaces the person's token: hashes can't be re-sent.
    """
    group = _group_for_invite(db, invite_token)
    check_email_rate(db, request, body.email)

    token = new_token()
    participant = db.scalar(
        select(Participant).where(Participant.group_id == group.id, Participant.email == body.email)
    )
    if participant is not None:
        participant.token_hash = hash_token(token)
        participant.joined_at = participant.joined_at or datetime.now(UTC)
        name = participant.name
    else:
        if group.draw_status == "drawn":
            raise HTTPException(status.HTTP_409_CONFLICT, "The draw has already happened")
        count = db.scalar(select(func.count()).where(Participant.group_id == group.id))
        if count >= MAX_PARTICIPANTS:
            raise HTTPException(status.HTTP_409_CONFLICT, "This group is full")
        name = body.name
        participant = Participant(
            group_id=group.id,
            name=body.name,
            email=body.email,
            token_hash=hash_token(token),
            joined_at=datetime.now(UTC),
        )
        db.add(participant)
    db.commit()
    send_safely(
        sender,
        templates.personal_link(
            group, name, body.email, participant_link(token), unsubscribe_links("p", participant.id)
        ),
    )
    return {"status": "sent"}
