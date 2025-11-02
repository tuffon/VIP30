import os
import uuid
from typing import Any, Dict

import lz4.frame
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from redis import Redis
from rq import Queue
from rq.job import Job


router = APIRouter(prefix="/render/bid-comp", tags=["bid-comp"])

try:
    _redis_url = os.environ["REDIS_URL"]
except KeyError as exc:
    raise RuntimeError("REDIS_URL env var must be set") from exc

_r = Redis.from_url(_redis_url)
_q = Queue("bidcomp", connection=_r)

MAX_BYTES = 12 * 1024 * 1024  # 12 MB cap for combined uploads


def _is_pdf_header(data: bytes) -> bool:
    # quick sniff: PDF files start with '%PDF-'
    return data.startswith(b"%PDF-")


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_bid_comp(
    carrier: UploadFile = File(...),
    contractor: UploadFile = File(...),
) -> Dict[str, Any]:
    # Read entire files (they are small ~3-5MB each)
    carrier_bytes = await carrier.read()
    contractor_bytes = await contractor.read()

    total_size = len(carrier_bytes) + len(contractor_bytes)
    if total_size > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"payload too large: {total_size} bytes")

    # MIME and header validation
    if not (carrier.content_type or "").lower().endswith("pdf") or not (contractor.content_type or "").lower().endswith("pdf"):
        raise HTTPException(status_code=415, detail="only PDFs are accepted")
    if not _is_pdf_header(carrier_bytes) or not _is_pdf_header(contractor_bytes):
        raise HTTPException(status_code=415, detail="invalid PDF content")

    # Compress before enqueue to keep Redis lean
    c_comp = lz4.frame.compress(carrier_bytes)
    k_comp = lz4.frame.compress(contractor_bytes)

    # Create job
    job_id = str(uuid.uuid4())
    job = _q.enqueue(
        "src.tasks.run_bid_comp",
        job_id,
        c_comp,
        k_comp,
        job_timeout=600,
        result_ttl=86400,
        failure_ttl=86400,
    )

    # Use job.id for consistent lookup
    return {"job_id": job.id, "status": "queued"}


@router.get("/{job_id}")
def get_status(job_id: str) -> Dict[str, Any]:
    try:
        job = Job.fetch(job_id, connection=_r)
    except Exception:
        raise HTTPException(status_code=404, detail="job not found")

    status_str = job.get_status(refresh=True)
    if status_str in ("queued", "started", "deferred"):
        return {"job_id": job_id, "status": status_str}
    if status_str == "finished":
        result = job.result or {}
        return {"job_id": job_id, "status": "finished", **result}
    if status_str == "failed":
        return {"job_id": job_id, "status": "failed", "error": str(job.exc_info or "failed")}
    return {"job_id": job_id, "status": status_str}


