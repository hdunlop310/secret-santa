from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Exclusion, Group, Participant
from app.schemas import GroupPublic, ParticipantStatus, ParticipantSummary

MAX_PARTICIPANTS = 50
MIN_PARTICIPANTS = 3


def admin_link(token: str) -> str:
    return f"{get_settings().app_base_url}/g/{token}"


def participant_link(token: str) -> str:
    return f"{get_settings().app_base_url}/p/{token}"


def invite_link(group: Group) -> str:
    return f"{get_settings().app_base_url}/join/{group.invite_token}"


def days_to_go(gift_date: date, today: date | None = None) -> int:
    return max(0, (gift_date - (today or date.today())).days)


def participant_status(p: Participant) -> ParticipantStatus:
    if p.joined_at is None:
        return "invited"
    if p.secret_surprise or p.items:
        return "wish_list_in"
    return "joined"


def group_public(group: Group) -> GroupPublic:
    return GroupPublic(
        id=group.id,
        name=group.name,
        gift_date=group.gift_date,
        budget_min=group.budget_min,
        budget_max=group.budget_max,
        message=group.message,
        admin_name=group.admin_name,
        draw_status=group.draw_status,
        days_to_go=days_to_go(group.gift_date),
    )


def participant_summaries(group: Group) -> list[ParticipantSummary]:
    return [
        ParticipantSummary(id=p.id, name=p.name, status=participant_status(p), is_admin=p.is_admin)
        for p in group.participants
    ]


def exclusion_pair_count(db: Session, group: Group) -> int:
    rows = db.execute(
        select(Exclusion.giver_id, Exclusion.giftee_id).where(Exclusion.group_id == group.id)
    )
    return len({frozenset(row) for row in rows})
