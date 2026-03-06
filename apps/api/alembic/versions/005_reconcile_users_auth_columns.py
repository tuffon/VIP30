"""reconcile users auth columns

Revision ID: 005_reconcile_users_auth_columns
Revises: 004_add_user_role
Create Date: 2026-03-06 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_reconcile_users_auth_columns"
down_revision: Union[str, None] = "004_add_user_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("users")}

    if "role" not in columns:
        op.add_column(
            "users",
            sa.Column("role", sa.String(length=20), nullable=True, server_default="member"),
        )

    if "last_login_at" not in columns:
        op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))

    if "last_login_ip" not in columns:
        op.add_column("users", sa.Column("last_login_ip", sa.String(length=45), nullable=True))

    if "login_method" not in columns:
        op.add_column("users", sa.Column("login_method", sa.String(length=50), nullable=True))

    op.execute(sa.text("UPDATE users SET role = 'member' WHERE role IS NULL OR role = ''"))
    op.alter_column("users", "role", existing_type=sa.String(length=20), nullable=False, server_default="member")


def downgrade() -> None:
    # Reconciliation migration: no-op downgrade to avoid destructive column removal.
    pass
