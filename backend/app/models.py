from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

DRAW_STATUSES = ("not_drawn", "drawn")


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint("budget_min >= 0", name="budget_min_non_negative"),
        CheckConstraint("budget_max >= budget_min", name="budget_max_gte_min"),
        CheckConstraint("draw_status IN ('not_drawn', 'drawn')", name="draw_status_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    budget_min: Mapped[int] = mapped_column(Integer)  # pence
    budget_max: Mapped[int] = mapped_column(Integer)  # pence
    gift_date: Mapped[date] = mapped_column(Date)
    message: Mapped[str | None] = mapped_column(Text)
    admin_name: Mapped[str] = mapped_column(String(60))
    admin_email: Mapped[str] = mapped_column(String(254))
    admin_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invite_token: Mapped[str] = mapped_column(String(64), unique=True)
    show_exclusions: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    draw_status: Mapped[str] = mapped_column(
        String(16), default="not_drawn", server_default="not_drawn"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    participants: Mapped[list["Participant"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="Participant.id",
    )


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("group_id", "email", name="uq_participant_group_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    email: Mapped[str] = mapped_column(String(254))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    secret_surprise: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Null until the person joins via the invite link or first opens a link the admin sent.
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    group: Mapped[Group] = relationship(back_populates="participants")
    items: Mapped[list["WishlistItem"]] = relationship(
        back_populates="participant",
        cascade="all, delete-orphan",
        order_by="WishlistItem.sort_order",
    )


class Exclusion(Base):
    __tablename__ = "exclusions"
    __table_args__ = (
        UniqueConstraint("group_id", "giver_id", "giftee_id", name="uq_exclusion_pair"),
        CheckConstraint("giver_id <> giftee_id", name="exclusion_not_self"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    giver_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    giftee_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("group_id", "draw_round", "giver_id", name="uq_assignment_giver"),
        UniqueConstraint("group_id", "draw_round", "giftee_id", name="uq_assignment_giftee"),
        CheckConstraint("giver_id <> giftee_id", name="assignment_not_self"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    giver_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    giftee_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    draw_round: Mapped[int] = mapped_column(Integer)


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(2048))
    price: Mapped[int | None] = mapped_column(Integer)  # pence
    image_url: Mapped[str | None] = mapped_column(String(2048))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    participant: Mapped[Participant] = relationship(back_populates="items")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[int | None] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(String(32))
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
