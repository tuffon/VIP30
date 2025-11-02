import os
import uuid
import logging
from typing import Any, Dict

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
    # Read entire files (they are small ~3-5MB each)
    carrier_bytes = await carrier.read()
    contractor_bytes = await contractor.read()

    total_size = len(carrier_bytes) + len(contractor_bytes)
    if total_size > MAX_BYTES:
        logger.warning("enqueue rejected: payload too large (%d bytes)", total_size)
        raise HTTPException(status_code=413, detail=f"payload too large: {total_size} bytes")

    # MIME and header validation
    if not (carrier.content_type or "").lower().endswith("pdf") or not (contractor.content_type or "").lower().endswith("pdf"):
        raise HTTPException(status_code=415, detail="only PDFs are accepted")
    if not _is_pdf_header(carrier_bytes) or not _is_pdf_header(contractor_bytes):
        logger.warning("enqueue rejected: invalid pdf headers (carrier_ok=%s contractor_ok=%s)", _is_pdf_header(carrier_bytes), _is_pdf_header(contractor_bytes))
        raise HTTPException(status_code=415, detail="invalid PDF content")

    # Compress before enqueue to keep Redis lean
    c_comp = lz4.frame.compress(carrier_bytes)
    k_comp = lz4.frame.compress(contractor_bytes)

    # Enqueue one job per PDF
    job_c = _q.enqueue(
        "src.tasks.parse_pdf",
        "carrier",
        c_comp,
        job_timeout=600,
        result_ttl=86400,
        failure_ttl=86400,
    )
    job_k = _q.enqueue(
        "src.tasks.parse_pdf",
        "contractor",
        k_comp,
        job_timeout=600,
        result_ttl=86400,
        failure_ttl=86400,
    )

    # Join job waits for both
    corr_id = str(uuid.uuid4())
    join_job = _q.enqueue(
        "src.tasks.join_bid_comp",
        corr_id,
        job_c.id,
        job_k.id,
        depends_on=[job_c, job_k],
        job_timeout=120,
        result_ttl=86400,
        failure_ttl=86400,
    )
    try:
        join_job.meta = {"deps": [job_c.id, job_k.id]}
        join_job.save()
    except Exception:
        pass

    logger.info(
        "enqueue ok: join=%s deps=(%s,%s) sizes=(%d,%d) comp=(%d,%d)",
        join_job.id,
        job_c.id,
        job_k.id,
        len(carrier_bytes),
        len(contractor_bytes),
        len(c_comp),
        len(k_comp),
    )
    return {"job_id": join_job.id, "status": "queued"}


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
        # If deferred, check dependency failures to surface a terminal error
        if status_str == "deferred":
            deps = None
            try:
                deps = (job.meta or {}).get("deps")
            except Exception:
                deps = None
            if deps and _r is not None:
                try:
                    from rq.job import Job as _J
                    dep_jobs = [_J.fetch(jid, connection=_r) for jid in deps if jid]
                    for dj in dep_jobs:
                        if dj.get_status(refresh=True) == "failed":
                            return {"job_id": job_id, "status": "failed", "error": str(dj.exc_info or "dependency failed")}
                except Exception:
                    pass
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


