"""Create transformations and payloads tables

Revision ID: a10eeb321d04
Revises:
Create Date: 2026-10-20 17:58:21.039379
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a10eeb321d04"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payloads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("input_hash"),
    )
    op.create_table(
        "transformations",
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("input"),
    )


def downgrade() -> None:
    op.drop_table("transformations")
    op.drop_table("payloads")
