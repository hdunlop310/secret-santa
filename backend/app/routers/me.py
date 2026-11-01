from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas import Me, WishlistItemOut
from app.security import DB, CurrentParticipant
from app.services import group_public

router = APIRouter()


@router.get("/me", response_model=Me)
def get_me(participant: CurrentParticipant, db: DB) -> Me:
    if participant.joined_at is None:
        # Someone the admin added by email counts as joined once they open their link.
        participant.joined_at = datetime.now(UTC)
        db.commit()
    return Me(
        id=participant.id,
        name=participant.name,
        is_admin=participant.is_admin,
        secret_surprise=participant.secret_surprise,
        group=group_public(participant.group),
        items=[WishlistItemOut.model_validate(i, from_attributes=True) for i in participant.items],
    )
