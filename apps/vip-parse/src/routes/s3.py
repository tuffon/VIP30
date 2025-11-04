import os
from typing import Dict

from fastapi import APIRouter

from src.utils.s3_client import get_s3


router = APIRouter(prefix="/render", tags=["r2"], )


@router.post("/upload-url")
def create_upload_url(filename: str) -> Dict[str, str]:
    s3 = get_s3()
    key = f"uploads/{filename}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": os.environ["S3_BUCKET"], "Key": key},
        ExpiresIn=int(os.getenv("PRESIGN_EXPIRE_SEC", "900")),
    )
    return {"upload_url": url, "key": key}


@router.get("/download-url")
def create_download_url(key: str) -> Dict[str, str]:
    s3 = get_s3()
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": os.environ["S3_BUCKET"], "Key": key},
        ExpiresIn=int(os.getenv("PRESIGN_EXPIRE_SEC", "900")),
    )
    return {"download_url": url}


