"""draw and wish list timestamps

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("groups", sa.Column("drawn_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "participants",
        sa.Column("wishlist_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("participants", "wishlist_updated_at")
    op.drop_column("groups", "drawn_at")
