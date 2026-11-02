"""extra link tokens per admin or participant

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "link_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "participant_id",
            sa.Integer(),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_link_tokens_group_id", "link_tokens", ["group_id"])
    op.create_index("ix_link_tokens_participant_id", "link_tokens", ["participant_id"])


def downgrade() -> None:
    op.drop_index("ix_link_tokens_participant_id", table_name="link_tokens")
    op.drop_index("ix_link_tokens_group_id", table_name="link_tokens")
    op.drop_table("link_tokens")
