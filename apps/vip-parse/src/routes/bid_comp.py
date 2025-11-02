import os
import uuid
import logging
import io
from typing import Any, Dict, Tuple

import lz4.frame
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

    async def _stream_compress(upload: UploadFile) -> Tuple[bytes, int, bool]:
        head = await upload.read(5)
        if not _is_pdf_header(head):
            return b"", 0, False
        comp = lz4.frame.LZ4FrameCompressor()
        buf = io.BytesIO()
        total = len(head)
        buf.write(comp.begin())
        buf.write(comp.compress(head))
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BYTES:
                return b"", total, False
            buf.write(comp.compress(chunk))
        buf.write(comp.flush())
        return buf.getvalue(), total, True

    c_comp, c_size, ok_c = await _stream_compress(carrier)
    k_comp, k_size, ok_k = await _stream_compress(contractor)
    total_size = c_size + k_size
    if not ok_c or not ok_k:
        if total_size > MAX_BYTES:
            logger.warning("enqueue rejected: payload too large (%d bytes)", total_size)
            raise HTTPException(status_code=413, detail=f"payload too large: {total_size} bytes")
        logger.warning("enqueue rejected: invalid pdf content (carrier_ok=%s contractor_ok=%s)", ok_c, ok_k)
        raise HTTPException(status_code=415, detail="invalid PDF content")

    # Single job parses both PDFs sequentially (in-process semaphore caps concurrency)
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
    logger.info(
        "enqueue ok: job_id=%s sizes=(%d,%d) comp=(%d,%d)",
        job.id,
        c_size,
        k_size,
        len(c_comp),
        len(k_comp),
    )
    return {"job_id": job.id, "status": "queued"}


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


