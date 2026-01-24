import os
import uuid
import logging
from typing import Any, Dict, Optional, Tuple
from fastapi import APIRouter, HTTPException, status
from redis import Redis
from rq import Queue
from rq.job import Job, JobStatus
from src.utils.s3_client import get_s3, get_bucket


router = APIRouter(prefix="/render/bid-comp", tags=["bid-comp"])
logger = logging.getLogger("vip-parse.web")


def _diagnose_job_failure(job: Job) -> Tuple[str, str]:
    """
    Analyze a failed job and return (error_code, user_friendly_message).

    Common failure modes:
    - AbandonedJobError: Worker died mid-execution (OOM, crash, timeout)
    - TimeoutError: Job exceeded job_timeout
    - MemoryError: Worker ran out of memory
    - Connection errors: Redis/network issues
    """
    exc_info = str(job.exc_info or "")
    exc_lower = exc_info.lower()

    # Check for abandoned job (worker died)
    if "abandonedjob" in exc_lower or "abandoned" in exc_lower:
        # Try to determine why it was abandoned
        if job.timeout and job.started_at and job.ended_at:
            # Job ran for a long time before being abandoned
            runtime_sec = (job.ended_at - job.started_at).total_seconds() if job.ended_at and job.started_at else 0
            if runtime_sec > (job.timeout * 0.9):
                return (
                    "TIMEOUT",
                    f"Job timed out after {int(runtime_sec)}s. The PDF files may be too large or complex to process within the time limit. Try splitting large estimates into smaller files."
                )

        # Generic abandoned - likely OOM or worker crash
        return (
            "WORKER_CRASHED",
            "The processing worker stopped unexpectedly. This usually happens when PDF files are very large (over 50 pages) or contain complex graphics. Try uploading smaller or simpler PDF files, or contact support if the issue persists."
        )

    # Check for explicit timeout
    if "timeout" in exc_lower or "timedout" in exc_lower:
        return (
            "TIMEOUT",
            "Job exceeded the maximum processing time. Large or complex PDF files may take too long to process. Try splitting the estimate into smaller files."
        )

    # Check for memory errors
    if "memoryerror" in exc_lower or "oom" in exc_lower or "out of memory" in exc_lower:
        return (
            "OUT_OF_MEMORY",
            "The server ran out of memory processing your files. This happens with very large PDFs (50+ pages) or PDFs with high-resolution images. Try reducing image quality or splitting into smaller files."
        )

    # Check for Redis/connection errors
    if "connectionerror" in exc_lower or "redis" in exc_lower or "connection refused" in exc_lower:
        return (
            "CONNECTION_ERROR",
            "A temporary connection issue occurred. Please try again in a few minutes."
        )

    # Check for file not found / S3 errors
    if "filenotfound" in exc_lower or "nosuchkey" in exc_lower or "s3" in exc_lower:
        return (
            "FILE_NOT_FOUND",
            "One or more uploaded files could not be found. Please re-upload your files and try again."
        )

    # Check for parser errors
    if "parser" in exc_lower or "xactimate" in exc_lower or "pdf" in exc_lower:
        return (
            "PARSE_ERROR",
            "The PDF could not be parsed. Please ensure you're uploading valid Xactimate estimate PDFs. Scanned documents or image-only PDFs are not supported."
        )

    # Check for LLM/OpenAI errors
    if "openai" in exc_lower or "rate limit" in exc_lower or "api" in exc_lower:
        return (
            "LLM_ERROR",
            "The AI narrative generation encountered an issue. The comparison will still work, but narratives may be limited. Please try again."
        )

    # Generic fallback with sanitized error
    # Don't expose full stack traces to users
    short_error = exc_info.split("\n")[0][:200] if exc_info else "Unknown error"
    return (
        "UNKNOWN_ERROR",
        f"An unexpected error occurred: {short_error}. Please try again or contact support if the issue persists."
    )

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

"""Only presigned upload + key-based enqueue endpoints are supported."""


@router.post("/keys", status_code=status.HTTP_202_ACCEPTED)
def enqueue_bid_comp_keys(payload: Dict[str, Any]) -> Dict[str, Any]:
    if _q is None:
        raise HTTPException(status_code=503, detail="Redis not configured")
    carrier_key = payload.get("carrier_key")
    contractor_key = payload.get("contractor_key")
    if not carrier_key or not contractor_key:
        raise HTTPException(status_code=400, detail="carrier_key and contractor_key are required")
    job_id = str(uuid.uuid4())
    job = _q.enqueue(
        "src.tasks.run_bid_comp_keys",
        job_id,
        carrier_key,
        contractor_key,
        payload.get("template"),
        payload.get("carrier_filename"),
        payload.get("contractor_filename"),
        payload.get("notify_email"),
        job_timeout=600,
        result_ttl=86400,
        failure_ttl=86400,
    )
    logger.info("enqueue keys ok: job_id=%s keys=(%s,%s)", job.id, carrier_key, contractor_key)
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
        # If result_keys present, generate presigned download URLs
        if isinstance(result, dict) and result.get("result_keys"):
            try:
                s3 = get_s3()
                bucket = get_bucket()
                expire = int(os.getenv("PRESIGN_EXPIRE_SEC", "900"))
                presigned: Dict[str, str] = {}
                for name, key in (result.get("result_keys") or {}).items():
                    url = s3.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": bucket, "Key": key},
                        ExpiresIn=expire,
                    )
                    presigned[name] = url
                result["download_urls"] = presigned
            except Exception as e:  # noqa: BLE001
                logger.warning("presign failed: %s", e)
        return {"job_id": job_id, "status": "finished", **result}
    if status_str == "failed":
        error_code, user_message = _diagnose_job_failure(job)
        raw_error = str(job.exc_info or "")[:500]  # Keep for logging
        logger.error(
            "status failed: job_id=%s error_code=%s user_message=%s raw=%s",
            job_id,
            error_code,
            user_message,
            raw_error,
        )
        return {
            "job_id": job_id,
            "status": "failed",
            "error_code": error_code,
            "error": user_message,
            "error_details": raw_error if os.getenv("DEBUG") else None,
        }
    return {"job_id": job_id, "status": status_str}


