from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.matching import MIN_PEOPLE, Pair, find_bottleneck
from app.models import Exclusion, Group
from app.schemas import (
    BottleneckOut,
    ExclusionPair,
    Exclusions,
    ExclusionsCheck,
    ExclusionsCheckRequest,
    ExclusionsUpdate,
    PersonRef,
)
from app.security import DB, NOT_FOUND, AdminGroup, Member

router = APIRouter()


def _exclusions(db: DB, group: Group) -> Exclusions:
    rows = db.execute(
        select(Exclusion.giver_id, Exclusion.giftee_id)
        .where(Exclusion.group_id == group.id)
        .order_by(Exclusion.giver_id, Exclusion.giftee_id)
    )
    return Exclusions(
        show_exclusions=group.show_exclusions,
        participants=[PersonRef(id=p.id, name=p.name) for p in group.participants],
        pairs=[ExclusionPair(giver_id=g, giftee_id=t) for g, t in rows],
    )


def _validated_pairs(group: Group, pairs: list[ExclusionPair]) -> set[Pair]:
    ids = {p.id for p in group.participants}
    result: set[Pair] = set()
    for pair in pairs:
        if pair.giver_id not in ids or pair.giftee_id not in ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Exclusions must be between group members"
            )
        if pair.giver_id == pair.giftee_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Someone can't be excluded from themselves"
            )
        result.add((pair.giver_id, pair.giftee_id))
    return result


@router.get("/groups/{group_id}/exclusions", response_model=Exclusions)
def get_exclusions(group_id: int, member: Member, db: DB) -> Exclusions:
    group = member.group
    if group.id != group_id:
        raise NOT_FOUND
    if not member.is_admin and not group.show_exclusions:
        raise NOT_FOUND
    return _exclusions(db, group)


@router.put("/groups/{group_id}/exclusions", response_model=Exclusions)
def set_exclusions(group_id: int, body: ExclusionsUpdate, group: AdminGroup, db: DB) -> Exclusions:
    if group.id != group_id:
        raise NOT_FOUND
    pairs = _validated_pairs(group, body.pairs)
    db.execute(delete(Exclusion).where(Exclusion.group_id == group.id))
    db.add_all(Exclusion(group_id=group.id, giver_id=g, giftee_id=t) for g, t in pairs)
    if body.show_exclusions is not None:
        group.show_exclusions = body.show_exclusions
    db.commit()
    return _exclusions(db, group)


@router.post("/groups/{group_id}/exclusions/check", response_model=ExclusionsCheck)
def check_exclusions(
    group_id: int, body: ExclusionsCheckRequest, group: AdminGroup
) -> ExclusionsCheck:
    """Would a valid draw exist with these (unsaved) exclusions? Uses the real matching code."""
    if group.id != group_id:
        raise NOT_FOUND
    pairs = _validated_pairs(group, body.pairs)
    people = [p.id for p in group.participants]
    if len(people) < MIN_PEOPLE:
        return ExclusionsCheck(possible=False, reason="too_few")
    bottleneck = find_bottleneck(people, pairs)
    if bottleneck is None:
        return ExclusionsCheck(possible=True)
    return ExclusionsCheck(
        possible=False,
        reason="stuck",
        bottleneck=BottleneckOut(
            side=bottleneck.side, people=list(bottleneck.people), options=list(bottleneck.options)
        ),
    )
