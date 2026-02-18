import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from sqlmodel import desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from vip_shared.db.models import ComparisonJob, User
from src.dependencies.auth import require_auth
from src.dependencies.database import get_db
from vip_shared.services.jobs import InsufficientCreditsError, JobService
from src.tasks import run_bid_comp_keys
from vip_shared.utils.s3_client import get_bucket, get_s3


jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])

_redis_url = os.getenv("REDIS_URL")
_r = Redis.from_url(_redis_url) if _redis_url else None
_q = Queue("bidcomp", connection=_r) if _r else None


class CreateJobRequest(BaseModel):
    carrier_key: str
    contractor_key: str
    carrier_filename: Optional[str] = None
    contractor_filename: Optional[str] = None


class CreateJobResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    id: str
    state: str
    progress_percent: int
    current_step: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    result_s3_key: Optional[str] = None
    output_mode: Optional[str] = None
    download_url: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class JobsListResponse(BaseModel):
    page: int
    per_page: int
    total_count: int
    jobs: List[JobStatusResponse]


def _serialize_job(job: ComparisonJob, download_url: Optional[str] = None) -> JobStatusResponse:
    return JobStatusResponse(
        id=str(job.id),
        state=job.state,
        progress_percent=job.progress_percent,
        current_step=job.current_step,
        error_code=job.error_code,
        error_message=job.error_message,
        result_s3_key=job.result_s3_key,
        output_mode=job.output_mode,
        download_url=download_url,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@jobs_router.post("", response_model=CreateJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    payload: CreateJobRequest,
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    if _q is None:
        raise HTTPException(status_code=503, detail="Redis not configured")

    try:
        job = await JobService.create_job(
            db=db,
            workspace_id=current_user.workspace_id,
            created_by=current_user.id,
            primary_filename=payload.carrier_filename,
            comparison_filename=payload.contractor_filename,
            primary_s3_key=payload.carrier_key,
            comparison_s3_key=payload.contractor_key,
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "insufficient_credits", "message": "Not enough credits to start job"},
        ) from exc

    rq_job = _q.enqueue(
        run_bid_comp_keys,
        str(job.id),
        payload.carrier_key,
        payload.contractor_key,
        None,
        payload.carrier_filename,
        payload.contractor_filename,
        None,
        str(job.id),
        job_timeout=600,
        result_ttl=86400,
        failure_ttl=86400,
    )
    job.rq_job_id = rq_job.id
    job.updated_at = datetime.utcnow()
    db.add(job)
    await db.commit()
    await db.refresh(job)

    return CreateJobResponse(job_id=str(job.id), status=job.state)


@jobs_router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    job = await JobService.get_job(db, job_id, workspace_id=current_user.workspace_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    download_url = None
    if job.state == JobService.COMPLETED and job.result_s3_key:
        try:
            s3 = get_s3()
            bucket = get_bucket()
            expire = int(os.getenv("PRESIGN_EXPIRE_SEC", "900"))
            download_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": job.result_s3_key},
                ExpiresIn=expire,
            )
        except Exception:
            download_url = None

    return _serialize_job(job, download_url=download_url)


@jobs_router.post("/{job_id}/retry", response_model=CreateJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    original_job = await JobService.get_job(db, job_id, workspace_id=current_user.workspace_id)
    if not original_job:
        raise HTTPException(status_code=404, detail="job not found")
    if original_job.state != JobService.FAILED:
        raise HTTPException(status_code=400, detail="only failed jobs can be retried")

    try:
        new_job = await JobService.create_job(
            db=db,
            workspace_id=current_user.workspace_id,
            created_by=current_user.id,
            primary_filename=original_job.primary_filename,
            comparison_filename=original_job.comparison_filename,
            primary_s3_key=original_job.primary_s3_key,
            comparison_s3_key=original_job.comparison_s3_key,
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "insufficient_credits", "message": "Not enough credits to start job"},
        ) from exc

    if _q is None:
        raise HTTPException(status_code=503, detail="Redis not configured")

    rq_job = _q.enqueue(
        run_bid_comp_keys,
        str(new_job.id),
        original_job.primary_s3_key,
        original_job.comparison_s3_key,
        None,
        original_job.primary_filename,
        original_job.comparison_filename,
        None,
        str(new_job.id),
        job_timeout=600,
        result_ttl=86400,
        failure_ttl=86400,
    )
    new_job.rq_job_id = rq_job.id
    new_job.updated_at = datetime.utcnow()
    original_job.retry_count += 1
    original_job.updated_at = datetime.utcnow()

    db.add(new_job)
    db.add(original_job)
    await db.commit()
    await db.refresh(new_job)

    return CreateJobResponse(job_id=str(new_job.id), status=new_job.state)


@jobs_router.get("", response_model=JobsListResponse)
async def list_jobs(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page

    total_stmt = select(func.count()).where(ComparisonJob.workspace_id == current_user.workspace_id)
    total_result = await db.exec(total_stmt)
    total_count = int(total_result.one())

    jobs_stmt = (
        select(ComparisonJob)
        .where(ComparisonJob.workspace_id == current_user.workspace_id)
        .order_by(desc(ComparisonJob.created_at))
        .offset(offset)
        .limit(per_page)
    )
    jobs_result = await db.exec(jobs_stmt)
    jobs = jobs_result.all()

    return JobsListResponse(
        page=page,
        per_page=per_page,
        total_count=total_count,
        jobs=[_serialize_job(job) for job in jobs],
    )
