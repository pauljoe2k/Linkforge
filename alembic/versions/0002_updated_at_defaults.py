"""add defaults for updated_at columns

Revision ID: 0002_updated_at_defaults
Revises: 0001_initial
Create Date: 2026-10-22
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_updated_at_defaults"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("users", "links"):
        op.alter_column(
            table,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.text("now()"),
        )


def downgrade() -> None:
    for table in ("users", "links"):
        op.alter_column(
            table,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=None,
        )
