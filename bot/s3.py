"""
s3.py — Upload generated figures to AWS S3.

Bucket layout:  figures/{user_id}/{timestamp}_{job_id}.png
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BUCKET = os.getenv("S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")

_s3_client = None


def _get_s3():
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    if not BUCKET:
        logger.warning("S3_BUCKET not configured — image upload skipped.")
        return None
    try:
        import boto3  # noqa: PLC0415

        _s3_client = boto3.client("s3", region_name=AWS_REGION)
        logger.info("S3 client ready (bucket=%s, region=%s).", BUCKET, AWS_REGION)
    except Exception as exc:
        logger.warning("S3 unavailable (%s). Image upload skipped.", exc)
        _s3_client = None
    return _s3_client


def upload_figure(png_bytes: bytes, user_id: int, job_id: str | None = None) -> str | None:
    """Upload a PNG to S3. Returns the object URL, or None on failure."""
    s3 = _get_s3()
    if s3 is None:
        return None
    if not job_id:
        job_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    key = f"figures/{user_id}/{ts}_{job_id}.png"
    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=png_bytes,
            ContentType="image/png",
        )
        url = f"https://{BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
        logger.info("Uploaded figure → %s", url)
        return url
    except Exception as exc:
        logger.warning("S3 put_object failed: %s", exc)
        return None
