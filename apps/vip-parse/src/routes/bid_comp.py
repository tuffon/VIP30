import os
import uuid
import logging
import tempfile
import shutil
from typing import Any, Dict
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from redis import Redis
from rq import Queue
from rq.job import Job


router = APIRouter(prefix="/render/bid-comp", tags=["bid-comp"])
logger = logging.getLogger("vip-parse.web")

_redis_url = os.getenv("REDIS_URL")
_r = None
_q = None
if _redis_url:
    try:
        _r = Redis.from_url(_redis_url, socket_connect_timeout=5, socket_timeout=5, health_check_interval=30)
        _q = Queue("bidcomp", connection=_r)
        logger.info("Redis connected for web routes")
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to connect Redis: %s", e)
else:
    logger.warning("REDIS_URL not set; bid-comp endpoints will return 503")

MAX_BYTES = 12 * 1024 * 1024  # 12 MB cap for combined uploads


def _is_pdf_header(data: bytes) -> bool:
    # quick sniff: PDF files start with '%PDF-'
    return data.startswith(b"%PDF-")


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_bid_comp(
    carrier: UploadFile = File(...),
    contractor: UploadFile = File(...),
) -> Dict[str, Any]:
    if _q is None:
        raise HTTPException(status_code=503, detail="Redis not configured")
    # MIME validation (cheap)
    if not (carrier.content_type or "").lower().endswith("pdf") or not (contractor.content_type or "").lower().endswith("pdf"):
        raise HTTPException(status_code=415, detail="only PDFs are accepted")

    def save_to_tmp(upload: UploadFile) -> str:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as out:
            shutil.copyfileobj(upload.file, out, length=1024 * 1024)
            return out.name

    p1, p2 = save_to_tmp(carrier), save_to_tmp(contractor)
    try:
        def _check_size_and_header(path: str) -> tuple[int, bool]:
            size = os.path.getsize(path)
            with open(path, "rb") as f:
                ok = _is_pdf_header(f.read(5))
            return size, ok

        s1, ok1 = _check_size_and_header(p1)
        s2, ok2 = _check_size_and_header(p2)
        if (s1 + s2) > MAX_BYTES:
            logger.warning("enqueue rejected: payload too large (%d bytes)", s1 + s2)
            raise HTTPException(status_code=413, detail=f"payload too large: {s1 + s2} bytes")
        if not ok1 or not ok2:
            logger.warning("enqueue rejected: invalid pdf content (carrier_ok=%s contractor_ok=%s)", ok1, ok2)
            raise HTTPException(status_code=415, detail="invalid PDF content")

        with open(p1, "rb") as f1, open(p2, "rb") as f2:
            payload = {"carrier_bytes": f1.read(), "contractor_bytes": f2.read()}

        job = _q.enqueue(
            "src.tasks.run_bid_comp_bytes",
            payload,
            job_timeout=600,
            result_ttl=86400,
            failure_ttl=86400,
        )
        logger.info("enqueue ok: job_id=%s sizes=(%d,%d)", job.id, s1, s2)
        return {"job_id": job.id, "status": "queued"}
    finally:
        for p in (p1, p2):
            try:
                os.remove(p)
            except OSError:
                pass


@router.get("/{job_id}")
def get_status(job_id: str) -> Dict[str, Any]:
    if _r is None:
        raise HTTPException(status_code=503, detail="Redis not configured")
    try:
        job = Job.fetch(job_id, connection=_r)
    except Exception:
        logger.warning("status: job not found: %s", job_id)
        raise HTTPException(status_code=404, detail="job not found")

    status_str = job.get_status(refresh=True)
    logger.info("status: job_id=%s status=%s", job_id, status_str)
    if status_str in ("queued", "started", "deferred"):
        return {"job_id": job_id, "status": status_str}
    if status_str == "finished":
        result = job.result or {}
        logger.info(
            "status finished: job_id=%s meta=%s keys=%s",
            job_id,
            getattr(result, "get", lambda *_: None)("meta") if isinstance(result, dict) else None,
            list(result.keys()) if isinstance(result, dict) else None,
        )
        return {"job_id": job_id, "status": "finished", **result}
    if status_str == "failed":
        err = str(job.exc_info or "failed")
        logger.error("status failed: job_id=%s error=%s", job_id, err)
        return {"job_id": job_id, "status": "failed", "error": err}
    return {"job_id": job_id, "status": status_str}


