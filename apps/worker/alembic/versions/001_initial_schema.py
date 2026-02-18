"""initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-02-14 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "otp_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_otp_codes_email"), "otp_codes", ["email"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("last_login_ip", sa.String(length=45), nullable=True),
        sa.Column("login_method", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_workspace_id"), "users", ["workspace_id"], unique=False)

    op.create_foreign_key(
        "fk_workspaces_owner_user_id_users",
        "workspaces",
        "users",
        ["owner_user_id"],
        ["id"],
    )

    op.create_table(
        "credit_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_credit_grants_amount_positive"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_credit_grants_workspace_id"), "credit_grants", ["workspace_id"], unique=False)

    op.create_table(
        "credit_consumptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_credit_consumptions_amount_positive"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(op.f("ix_credit_consumptions_job_id"), "credit_consumptions", ["job_id"], unique=True)
    op.create_index(
        op.f("ix_credit_consumptions_workspace_id"),
        "credit_consumptions",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "comparison_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column("primary_filename", sa.String(length=255), nullable=True),
        sa.Column("comparison_filename", sa.String(length=255), nullable=True),
        sa.Column("primary_s3_key", sa.String(length=500), nullable=True),
        sa.Column("comparison_s3_key", sa.String(length=500), nullable=True),
        sa.Column("result_s3_key", sa.String(length=500), nullable=True),
        sa.Column("narrative_s3_key", sa.String(length=500), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("rq_job_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_comparison_jobs_progress_percent_bounds",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comparison_jobs_rq_job_id"), "comparison_jobs", ["rq_job_id"], unique=False)
    op.create_index(op.f("ix_comparison_jobs_state"), "comparison_jobs", ["state"], unique=False)
    op.create_index(op.f("ix_comparison_jobs_workspace_id"), "comparison_jobs", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_comparison_jobs_workspace_id"), table_name="comparison_jobs")
    op.drop_index(op.f("ix_comparison_jobs_state"), table_name="comparison_jobs")
    op.drop_index(op.f("ix_comparison_jobs_rq_job_id"), table_name="comparison_jobs")
    op.drop_table("comparison_jobs")

    op.drop_index(op.f("ix_credit_consumptions_workspace_id"), table_name="credit_consumptions")
    op.drop_index(op.f("ix_credit_consumptions_job_id"), table_name="credit_consumptions")
    op.drop_table("credit_consumptions")

    op.drop_index(op.f("ix_credit_grants_workspace_id"), table_name="credit_grants")
    op.drop_table("credit_grants")

    op.drop_constraint("fk_workspaces_owner_user_id_users", "workspaces", type_="foreignkey")
    op.drop_index(op.f("ix_users_workspace_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_otp_codes_email"), table_name="otp_codes")
    op.drop_table("otp_codes")

    op.drop_table("workspaces")
