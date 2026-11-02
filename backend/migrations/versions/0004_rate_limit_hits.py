"""rate limit hits in the database

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bucket", sa.String(32), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("hit_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_limit_lookup", "rate_limit_hits", ["bucket", "key_hash", "hit_at"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_lookup", table_name="rate_limit_hits")
    op.drop_table("rate_limit_hits")
