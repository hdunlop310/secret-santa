from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.config import get_settings
from app.linkpreview import fetch_preview
from app.models import Participant, WishlistItem
from app.ratelimit import limiter
from app.schemas import (
    MAX_ITEMS,
    ItemCreate,
    ItemOrder,
    ItemUpdate,
    LinkPreviewOut,
    LinkPreviewRequest,
    Me,
    MeUpdate,
    WishlistItemOut,
)
from app.security import DB, CurrentParticipant
from app.services import group_public

router = APIRouter()


def _me(participant: Participant) -> Me:
    return Me(
        id=participant.id,
        name=participant.name,
        is_admin=participant.is_admin,
        secret_surprise=participant.secret_surprise,
        group=group_public(participant.group),
        items=[WishlistItemOut.model_validate(i, from_attributes=True) for i in participant.items],
    )


@router.get("/me", response_model=Me)
def get_me(participant: CurrentParticipant, db: DB) -> Me:
    if participant.joined_at is None:
        # Someone the admin added by email counts as joined once they open their link.
        participant.joined_at = datetime.now(UTC)
        db.commit()
    return _me(participant)


@router.put("/me", response_model=Me)
def update_me(body: MeUpdate, participant: CurrentParticipant, db: DB) -> Me:
    if body.name is not None:
        participant.name = body.name
    if body.secret_surprise is not None and body.secret_surprise != participant.secret_surprise:
        participant.secret_surprise = body.secret_surprise
        _touch(participant)
    db.commit()
    return _me(participant)


def _touch(participant: Participant) -> None:
    """Record a wish-list change so the giver can see it was updated."""
    participant.wishlist_updated_at = datetime.now(UTC)


def _own_item(db: DB, participant: Participant, item_id: int) -> WishlistItem:
    item = db.get(WishlistItem, item_id)
    if item is None or item.participant_id != participant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


@router.post("/me/items", status_code=status.HTTP_201_CREATED, response_model=WishlistItemOut)
def add_item(body: ItemCreate, participant: CurrentParticipant, db: DB) -> WishlistItemOut:
    count, last = db.execute(
        select(func.count(), func.max(WishlistItem.sort_order)).where(
            WishlistItem.participant_id == participant.id
        )
    ).one()
    if count >= MAX_ITEMS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"A wish list can have up to {MAX_ITEMS} items"
        )
    item = WishlistItem(
        participant_id=participant.id,
        sort_order=(last or 0) + 1,
        **body.model_dump(),
    )
    db.add(item)
    _touch(participant)
    db.commit()
    return WishlistItemOut.model_validate(item, from_attributes=True)


@router.patch("/me/items/{item_id}", response_model=WishlistItemOut)
def update_item(
    item_id: int, body: ItemUpdate, participant: CurrentParticipant, db: DB
) -> WishlistItemOut:
    item = _own_item(db, participant, item_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("title", "") is None:
        del changes["title"]  # the title can be changed but not cleared
    if "url" in changes and changes["url"] != item.url and "image_url" not in changes:
        changes["image_url"] = None  # a new link makes the old preview image wrong
    for field, value in changes.items():
        setattr(item, field, value)
    _touch(participant)
    db.commit()
    return WishlistItemOut.model_validate(item, from_attributes=True)


@router.delete("/me/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, participant: CurrentParticipant, db: DB) -> None:
    db.delete(_own_item(db, participant, item_id))
    _touch(participant)
    db.commit()


@router.put("/me/items/order", response_model=list[WishlistItemOut])
def reorder_items(
    body: ItemOrder, participant: CurrentParticipant, db: DB
) -> list[WishlistItemOut]:
    items = {item.id: item for item in participant.items}
    if sorted(body.ids) != sorted(items):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "The order must list every item exactly once"
        )
    for position, item_id in enumerate(body.ids, start=1):
        items[item_id].sort_order = position
    _touch(participant)
    db.commit()
    return [WishlistItemOut.model_validate(items[i], from_attributes=True) for i in body.ids]


@router.post("/link-preview", response_model=LinkPreviewOut)
def link_preview(body: LinkPreviewRequest, participant: CurrentParticipant) -> LinkPreviewOut:
    """Best-effort title and image for a pasted link. Never fails: empty fields on error."""
    limit = get_settings().rate_limit_link_preview
    if not limiter.hit("link_preview", str(participant.id), limit):
        return LinkPreviewOut()
    preview = fetch_preview(body.url)
    return LinkPreviewOut(title=preview.title, image_url=preview.image_url)
