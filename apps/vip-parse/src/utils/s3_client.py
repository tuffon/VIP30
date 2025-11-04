import os

import boto3
from botocore.config import Config


def _get(env: str, *aliases: str, default: str | None = None) -> str | None:
    for key in (env,) + aliases:
        val = os.getenv(key)
        if val:
            return val
    return default


def get_bucket() -> str:
    bucket = _get("S3_BUCKET", "CLOUDFLARE_BUCKET")
    if not bucket:
        raise KeyError("S3_BUCKET (or CLOUDFLARE_BUCKET) not set")
    return bucket


def get_s3():
    endpoint = _get("S3_ENDPOINT", "CLOUDFLARE_ENDPOINT", "CLOUDFLARE_R2_ENDPOINT")
    access_key = _get("S3_ACCESS_KEY_ID", "CLOUDFLARE_ACCESS_KEY_ID", "CLOUDFLARE_R2_ACCESS_KEY_ID")
    secret_key = _get("S3_SECRET_ACCESS_KEY", "CLOUDFLARE_SECRET_ACCESS_KEY", "CLOUDFLARE_R2_SECRET_ACCESS_KEY")
    if not endpoint:
        # Allow deriving R2 endpoint from account id if provided
        account_id = _get("CLOUDFLARE_ACCOUNT_ID")
        if account_id:
            endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    if not endpoint:
        raise KeyError("S3 endpoint not configured (set S3_ENDPOINT or CLOUDFLARE_* endpoint/account vars)")
    if not access_key or not secret_key:
        raise KeyError("S3 credentials not configured (set S3_ACCESS_KEY_ID/SECRET or CLOUDFLARE_* equivalents)")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.getenv("S3_REGION", "auto"),
        config=Config(s3={"addressing_style": "virtual"}, signature_version="s3v4"),
    )


