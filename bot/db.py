"""
db.py — AWS DynamoDB client for logging generation requests.

Table: autofigure_requests
  Partition key : user_id   (String)
  Sort key      : timestamp (String, ISO-8601 UTC)

Credentials are resolved automatically via boto3 credential chain:
  1. Environment variables (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
  2. ~/.aws/credentials
  3. EC2 IAM Role (production)
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

TABLE_NAME = os.getenv("DYNAMODB_TABLE", "autofigure_requests")
AWS_REGION = os.getenv("AWS_REGION", "ap-east-1")

_table = None  # lazy-init


def _get_table():
    global _table
    if _table is not None:
        return _table
    try:
        import boto3  # noqa: PLC0415

        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        _table = dynamodb.Table(TABLE_NAME)
        # Probe — raises if table doesn't exist or creds are missing
        _table.load()
        logger.info("DynamoDB table '%s' connected.", TABLE_NAME)
    except Exception as exc:
        logger.warning("DynamoDB unavailable (%s). Logging will be skipped.", exc)
        _table = None
    return _table


def log_request(
    user_id: int,
    method_text: str,
    status: str,
    *,
    has_reference: bool = False,
    job_id: Optional[str] = None,
    s3_url: Optional[str] = None,
) -> None:
    """Write one generation record to DynamoDB. Fails silently."""
    table = _get_table()
    if table is None:
        return
    item: dict = {
        "user_id": str(user_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method_text": method_text[:500],
        "has_reference": has_reference,
        "status": status,
        "job_id": job_id or str(uuid.uuid4()),
    }
    if s3_url:
        item["s3_url"] = s3_url
    try:
        table.put_item(Item=item)
    except Exception as exc:
        logger.warning("DynamoDB put_item failed: %s", exc)


def get_user_history(user_id: int, limit: int = 5) -> list:
    """Return the most recent `limit` records for this user (newest first)."""
    table = _get_table()
    if table is None:
        return []
    try:
        from boto3.dynamodb.conditions import Key  # noqa: PLC0415

        resp = table.query(
            KeyConditionExpression=Key("user_id").eq(str(user_id)),
            ScanIndexForward=False,
            Limit=limit,
        )
        return resp.get("Items", [])
    except Exception as exc:
        logger.warning("DynamoDB query failed: %s", exc)
        return []
