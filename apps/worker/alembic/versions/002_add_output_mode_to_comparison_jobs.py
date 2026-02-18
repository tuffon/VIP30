"""add output_mode to comparison_jobs

Revision ID: 002_add_output_mode_to_comparison_jobs
Revises: 001_initial_schema
Create Date: 2026-02-17 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_add_output_mode_to_comparison_jobs"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("comparison_jobs")}
    if "output_mode" not in columns:
        op.add_column(
            "comparison_jobs",
            sa.Column("output_mode", sa.String(length=20), nullable=False, server_default="internal"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("comparison_jobs")}
    if "output_mode" in columns:
        op.drop_column("comparison_jobs", "output_mode")
