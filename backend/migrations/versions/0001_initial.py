"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("budget_min", sa.Integer(), nullable=False),
        sa.Column("budget_max", sa.Integer(), nullable=False),
        sa.Column("gift_date", sa.Date(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("admin_name", sa.String(60), nullable=False),
        sa.Column("admin_email", sa.String(254), nullable=False),
        sa.Column("admin_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invite_token", sa.String(64), nullable=False, unique=True),
        sa.Column("show_exclusions", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("draw_status", sa.String(16), nullable=False, server_default="not_drawn"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("budget_min >= 0", name="budget_min_non_negative"),
        sa.CheckConstraint("budget_max >= budget_min", name="budget_max_gte_min"),
        sa.CheckConstraint("draw_status IN ('not_drawn', 'drawn')", name="draw_status_valid"),
    )

    op.create_table(
        "participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("secret_surprise", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("group_id", "email", name="uq_participant_group_email"),
    )
    op.create_index("ix_participants_group_id", "participants", ["group_id"])

    op.create_table(
        "exclusions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "giver_id",
            sa.Integer(),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "giftee_id",
            sa.Integer(),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("group_id", "giver_id", "giftee_id", name="uq_exclusion_pair"),
        sa.CheckConstraint("giver_id <> giftee_id", name="exclusion_not_self"),
    )
    op.create_index("ix_exclusions_group_id", "exclusions", ["group_id"])

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "giver_id",
            sa.Integer(),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "giftee_id",
            sa.Integer(),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("draw_round", sa.Integer(), nullable=False),
        sa.UniqueConstraint("group_id", "draw_round", "giver_id", name="uq_assignment_giver"),
        sa.UniqueConstraint("group_id", "draw_round", "giftee_id", name="uq_assignment_giftee"),
        sa.CheckConstraint("giver_id <> giftee_id", name="assignment_not_self"),
    )
    op.create_index("ix_assignments_group_id", "assignments", ["group_id"])

    op.create_table(
        "wishlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "participant_id",
            sa.Integer(),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("image_url", sa.String(2048), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_index("ix_wishlist_items_participant_id", "wishlist_items", ["participant_id"])

    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "participant_id",
            sa.Integer(),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reminders_group_id", "reminders", ["group_id"])
    op.create_index("ix_reminders_send_at", "reminders", ["send_at"])


def downgrade() -> None:
    for table in (
        "reminders",
        "wishlist_items",
        "assignments",
        "exclusions",
        "participants",
        "groups",
    ):
        op.drop_table(table)
