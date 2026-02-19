"""add role column to users for RBAC

Revision ID: 004_add_user_role
Revises: 003_output_mode_nullable
Create Date: 2026-02-19 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_add_user_role"
down_revision: Union[str, None] = "003_output_mode_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    if "role" not in columns:
        op.add_column(
            "users",
            sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        )

    op.execute(sa.text("UPDATE users SET role = 'member' WHERE role IS NULL OR role = ''"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    if "role" in columns:
        op.drop_column("users", "role")
