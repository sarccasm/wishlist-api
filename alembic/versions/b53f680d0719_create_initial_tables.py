"""create the complete initial schema

Revision ID: b53f680d0719
Revises:
Create Date: 2025-09-16 15:00:26.503970
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b53f680d0719"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "wishlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_wishlists_title", "wishlists", ["title"], unique=False)

    op.create_table(
        "wish_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("wishlist_id", sa.Integer(), sa.ForeignKey("wishlists.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_wish_items_title", "wish_items", ["title"], unique=False)

    op.create_table(
        "wish_item_statuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("wish_items.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("marked", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("wish_item_statuses")
    op.drop_index("ix_wish_items_title", table_name="wish_items")
    op.drop_table("wish_items")
    op.drop_index("ix_wishlists_title", table_name="wishlists")
    op.drop_table("wishlists")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
