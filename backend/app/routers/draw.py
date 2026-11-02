from fastapi import APIRouter, BackgroundTasks, Query
from sqlalchemy import select

from app.draw import check_can_draw, check_draw_rate, notify_draw, run_draw
from app.models import Assignment, Participant
from app.routers.groups import Sender
from app.schemas import DrawRequest, DrawResult, GifteeOut, GifteeResponse, WishlistItemOut
from app.security import DB, NOT_FOUND, AdminGroup, CurrentParticipant

router = APIRouter()


@router.post("/groups/{group_id}/draw", response_model=DrawResult)
def draw(
    group_id: int,
    body: DrawRequest,
    group: AdminGroup,
    db: DB,
    sender: Sender,
    background: BackgroundTasks,
) -> DrawResult:
    if group.id != group_id:
        raise NOT_FOUND
    check_can_draw(group, body.confirm_redraw)
    redraw = group.draw_status == "drawn"
    check_draw_rate(group)
    run_draw(db, group)
    db.commit()
    notify_draw(background, sender, group, redraw)
    return DrawResult(
        draw_status=group.draw_status,
        drawn_at=group.drawn_at,
        participant_count=len(group.participants),
    )


@router.delete("/groups/{group_id}/participants/{participant_id}", status_code=204)
def remove_participant(
    group_id: int,
    participant_id: int,
    group: AdminGroup,
    db: DB,
    sender: Sender,
    background: BackgroundTasks,
    confirm_redraw: bool = Query(False),
) -> None:
    """Remove someone and their data. After the draw this redraws, after confirmation."""
    participant = db.get(Participant, participant_id)
    if group.id != group_id or participant is None or participant.group_id != group.id:
        raise NOT_FOUND
    drawn = group.draw_status == "drawn"
    if drawn:
        check_can_draw(group, confirm_redraw)
        check_draw_rate(group)
    db.delete(participant)
    if drawn:
        try:
            run_draw(db, group)
        except Exception:
            db.rollback()
            raise
    db.commit()
    if drawn:
        notify_draw(background, sender, group, redraw=True)


@router.get("/me/giftee", response_model=GifteeResponse)
def my_giftee(participant: CurrentParticipant, db: DB) -> GifteeResponse:
    """The caller's own giftee and nothing else."""
    group = participant.group
    if group.draw_status != "drawn":
        return GifteeResponse(drawn=False)
    giftee = db.scalar(
        select(Participant)
        .join(Assignment, Assignment.giftee_id == Participant.id)
        .where(Assignment.group_id == group.id, Assignment.giver_id == participant.id)
    )
    if giftee is None:
        return GifteeResponse(drawn=False)
    updated = giftee.wishlist_updated_at
    return GifteeResponse(
        drawn=True,
        giftee=GifteeOut(
            name=giftee.name,
            secret_surprise=giftee.secret_surprise,
            items=[]
            if giftee.secret_surprise
            else [WishlistItemOut.model_validate(i, from_attributes=True) for i in giftee.items],
            updated_at=updated,
            updated_since_draw=bool(updated and group.drawn_at and updated > group.drawn_at),
        ),
    )
