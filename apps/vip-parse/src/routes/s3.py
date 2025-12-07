import os
from typing import Dict

from fastapi import APIRouter, HTTPException

from src.utils.filename import sanitize_storage_name
from src.utils.s3_client import get_s3, get_bucket


router = APIRouter(prefix="/render", tags=["r2"], )


@router.post("/upload-url")
def create_upload_url(filename: str) -> Dict[str, str]:
    try:
        safe_filename = sanitize_storage_name(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="filename must contain letters or numbers")
    try:
        s3 = get_s3()
        key = f"uploads/{safe_filename}"
        url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": get_bucket(), "Key": key},
            ExpiresIn=int(os.getenv("PRESIGN_EXPIRE_SEC", "900")),
        )
        return {"upload_url": url, "key": key, "filename": safe_filename}
    except Exception as e:  # noqa: BLE001
        # Return a terse message helpful for ops without leaking secrets
        raise HTTPException(status_code=500, detail=f"presign error: {type(e).__name__}")


@router.get("/download-url")
def create_download_url(key: str) -> Dict[str, str]:
    try:
        s3 = get_s3()
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": get_bucket(), "Key": key},
            ExpiresIn=int(os.getenv("PRESIGN_EXPIRE_SEC", "900")),
        )
        return {"download_url": url}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"presign error: {type(e).__name__}")


