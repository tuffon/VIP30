import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from vip_shared.db.models import ComparisonJob
from vip_shared.services.credits import CreditService


class InsufficientCreditsError(Exception):
    pass


class InvalidStateTransitionError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


class JobService:
    QUEUED = "queued"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    WRITING = "writing"
    COMPLETED = "completed"
    FAILED = "failed"

    TERMINAL_STATES = {COMPLETED, FAILED}
    VALID_TRANSITIONS = {
        QUEUED: {PARSING, FAILED},
        PARSING: {ANALYZING, FAILED},
        ANALYZING: {WRITING, FAILED},
        WRITING: {COMPLETED, FAILED},
    }
    DEFAULT_PROGRESS = {
        PARSING: 10,
        ANALYZING: 40,
        WRITING: 70,
        COMPLETED: 100,
    }

    @staticmethod
    async def create_job(
        db: AsyncSession,
        workspace_id: uuid.UUID,
        created_by: uuid.UUID,
        primary_filename: Optional[str] = None,
        comparison_filename: Optional[str] = None,
        primary_s3_key: Optional[str] = None,
        comparison_s3_key: Optional[str] = None,
    ) -> ComparisonJob:
        balance = await CreditService.get_balance(db, workspace_id)
        if balance < 1:
            raise InsufficientCreditsError("insufficient_credits")

        job = ComparisonJob(
            workspace_id=workspace_id,
            created_by=created_by,
            state=JobService.QUEUED,
            progress_percent=0,
            primary_filename=primary_filename,
            comparison_filename=comparison_filename,
            primary_s3_key=primary_s3_key,
            comparison_s3_key=comparison_s3_key,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def get_job(
        db: AsyncSession,
        job_id: uuid.UUID,
        workspace_id: Optional[uuid.UUID] = None,
    ) -> Optional[ComparisonJob]:
        job = await db.get(ComparisonJob, job_id)
        if not job:
            return None

        if workspace_id and job.workspace_id != workspace_id:
            return None

        return job

    @staticmethod
    async def transition_state(
        db: AsyncSession,
        job_id: uuid.UUID,
        new_state: str,
    ) -> ComparisonJob:
        job = await JobService.get_job(db, job_id)
        if not job:
            raise JobNotFoundError("job_not_found")

        current_state = job.state
        if current_state in JobService.TERMINAL_STATES:
            raise InvalidStateTransitionError(
                f"Cannot transition terminal job from '{current_state}' to '{new_state}'"
            )

        allowed = JobService.VALID_TRANSITIONS.get(current_state, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"Invalid transition from '{current_state}' to '{new_state}'"
            )

        job.state = new_state
        job.updated_at = datetime.utcnow()
        if new_state in JobService.DEFAULT_PROGRESS:
            job.progress_percent = JobService.DEFAULT_PROGRESS[new_state]

        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def update_progress(
        db: AsyncSession,
        job_id: uuid.UUID,
        progress_percent: int,
        current_step: Optional[str] = None,
    ) -> ComparisonJob:
        job = await JobService.get_job(db, job_id)
        if not job:
            raise JobNotFoundError("job_not_found")

        job.progress_percent = progress_percent
        job.current_step = current_step
        job.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def complete_job(
        db: AsyncSession,
        job_id: uuid.UUID,
        result_s3_key: str,
        narrative_s3_key: Optional[str] = None,
        consume_credit: bool = True,
    ) -> ComparisonJob:
        job = await JobService.transition_state(db, job_id, JobService.COMPLETED)
        job.completed_at = datetime.utcnow()
        job.result_s3_key = result_s3_key
        job.narrative_s3_key = narrative_s3_key
        job.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(job)

        if consume_credit:
            await CreditService.consume_credit(db, workspace_id=job.workspace_id, job_id=job.id, amount=1)
        return job

    @staticmethod
    async def fail_job(
        db: AsyncSession,
        job_id: uuid.UUID,
        error_code: str,
        error_message: str,
    ) -> ComparisonJob:
        job = await JobService.get_job(db, job_id)
        if not job:
            raise JobNotFoundError("job_not_found")

        if job.state in JobService.TERMINAL_STATES:
            raise InvalidStateTransitionError(
                f"Cannot transition terminal job from '{job.state}' to '{JobService.FAILED}'"
            )

        job.state = JobService.FAILED
        job.error_code = error_code
        job.error_message = error_message
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(job)
        return job
