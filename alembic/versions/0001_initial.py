"""initial schema: users, links, clicks

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "links",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_links_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_links_slug"), "links", ["slug"], unique=True)
    op.create_index("ix_links_user_id_created_at", "links", ["user_id", "created_at"])

    op.create_table(
        "clicks",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("link_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "clicked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("referrer", sa.String(length=2048), nullable=True),
        sa.Column("device_type", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["link_id"], ["links.id"], name="fk_clicks_link_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "device_type IN ('desktop', 'mobile', 'tablet', 'other')",
            name="ck_clicks_device_type",
        ),
    )
    op.create_index("ix_clicks_link_id_clicked_at", "clicks", ["link_id", "clicked_at"])


def downgrade() -> None:
    op.drop_index("ix_clicks_link_id_clicked_at", table_name="clicks")
    op.drop_table("clicks")
    op.drop_index("ix_links_user_id_created_at", table_name="links")
    op.drop_index(op.f("ix_links_slug"), table_name="links")
    op.drop_table("links")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
