import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Workspace(SQLModel, table=True):
    __tablename__ = "workspaces"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    owner_user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True, unique=True)
    email: str = Field(max_length=255, unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field(default=None)
    last_login_ip: Optional[str] = Field(default=None, max_length=45)
    login_method: Optional[str] = Field(default=None, max_length=50)


class OTPCode(SQLModel, table=True):
    __tablename__ = "otp_codes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(max_length=255, index=True)
    code_hash: str = Field(max_length=255)
    expires_at: datetime
    attempts: int = Field(default=0)
    used_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CreditGrant(SQLModel, table=True):
    __tablename__ = "credit_grants"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True)
    amount: int = Field(gt=0)
    source: str = Field(max_length=100)
    granted_by: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = Field(default=None)


class CreditConsumption(SQLModel, table=True):
    __tablename__ = "credit_consumptions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True)
    job_id: uuid.UUID = Field(unique=True, index=True)
    amount: int = Field(gt=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ComparisonJob(SQLModel, table=True):
    __tablename__ = "comparison_jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", index=True)
    created_by: uuid.UUID = Field(foreign_key="users.id")

    state: str = Field(default="queued", max_length=50, index=True)

    progress_percent: int = Field(default=0, ge=0, le=100)
    current_step: Optional[str] = Field(default=None, max_length=100)

    primary_filename: Optional[str] = Field(default=None, max_length=255)
    comparison_filename: Optional[str] = Field(default=None, max_length=255)
    primary_s3_key: Optional[str] = Field(default=None, max_length=500)
    comparison_s3_key: Optional[str] = Field(default=None, max_length=500)
    output_mode: Optional[str] = Field(default="internal", max_length=20)

    result_s3_key: Optional[str] = Field(default=None, max_length=500)
    narrative_s3_key: Optional[str] = Field(default=None, max_length=500)

    error_code: Optional[str] = Field(default=None, max_length=50)
    error_message: Optional[str] = Field(default=None)
    retry_count: int = Field(default=0)

    rq_job_id: Optional[str] = Field(default=None, max_length=100, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
