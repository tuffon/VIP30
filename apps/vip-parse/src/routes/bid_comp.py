import os
import uuid
import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status
from redis import Redis
from rq import Queue
from rq.job import Job
from src.utils.s3_client import get_s3, get_bucket


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
        err = str(job.exc_info or "failed")
        logger.error("status failed: job_id=%s error=%s", job_id, err)
        return {"job_id": job_id, "status": "failed", "error": err}
    return {"job_id": job_id, "status": status_str}


