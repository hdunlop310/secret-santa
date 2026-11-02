"""reminders, unsubscribe and participant creation time

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "groups", sa.Column("admin_unsubscribed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "participants",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_reminders_lookup", "reminders", ["group_id", "participant_id", "type"])


def downgrade() -> None:
    op.drop_index("ix_reminders_lookup", table_name="reminders")
    op.drop_column("participants", "created_at")
    op.drop_column("groups", "admin_unsubscribed_at")
