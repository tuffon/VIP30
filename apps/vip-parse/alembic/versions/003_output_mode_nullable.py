"""make output_mode nullable with no default

Revision ID: 003_output_mode_nullable
Revises: 002_add_output_mode_to_comparison_jobs
Create Date: 2026-02-18 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_output_mode_nullable"
down_revision: Union[str, None] = "002_add_output_mode_to_comparison_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("comparison_jobs")}
    if "output_mode" in columns:
        op.alter_column(
            "comparison_jobs",
            "output_mode",
            existing_type=sa.String(length=20),
            nullable=True,
            server_default=None,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("comparison_jobs")}
    if "output_mode" in columns:
        op.execute(
            sa.text(
                "UPDATE comparison_jobs SET output_mode = 'internal' WHERE output_mode IS NULL"
            )
        )
        op.alter_column(
            "comparison_jobs",
            "output_mode",
            existing_type=sa.String(length=20),
            nullable=False,
            server_default="internal",
        )
