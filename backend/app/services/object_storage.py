"""S3-compatible object storage for source PDFs and generated exports.

Use MinIO in Compose or any managed S3-compatible provider in production.
Storage is opt-in so existing local installations keep using the shared /data volume.
"""

from __future__ import annotations

import io
import os
import re
from datetime import datetime, timezone

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.logs.config import logger


def object_storage_enabled() -> bool:
    return os.getenv("OBJECT_STORAGE_ENABLED", "0").lower() in {"1", "true", "yes", "sim"}


def put_upload(tenant_id: str, job_id: str, filename: str, content: bytes) -> str:
    key = f"uploads/{_safe_part(tenant_id)}/{job_id}/{_safe_filename(filename)}"
    put_bytes(key, content, content_type="application/pdf")
    return key


def put_export(tenant_id: str, edital_id: int, filename: str, content: bytes, content_type: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"exports/{_safe_part(tenant_id)}/edital-{edital_id}/{timestamp}_{_safe_filename(filename)}"
    put_bytes(key, content, content_type=content_type)
    return key


def put_bytes(key: str, content: bytes, *, content_type: str) -> None:
    if not object_storage_enabled():
        return
    client = _client()
    bucket = _bucket()
    _ensure_bucket(client, bucket)
    client.upload_fileobj(io.BytesIO(content), bucket, key, ExtraArgs={"ContentType": content_type})


def get_bytes(key: str) -> bytes:
    client = _client()
    response = client.get_object(Bucket=_bucket(), Key=key)
    return response["Body"].read()


def delete(key: str | None) -> None:
    if not key or not object_storage_enabled():
        return
    try:
        _client().delete_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        logger.warning("[ObjectStorage] Nao foi possivel apagar %s: %s", key, exc)


def list_objects() -> list[dict[str, str]]:
    """List all objects for a controlled server-migration backup."""
    if not object_storage_enabled():
        return []
    client = _client()
    try:
        response = client.list_objects_v2(Bucket=_bucket())
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"NoSuchBucket", "404"}:
            return []
        raise
    objects = list(response.get("Contents", []))
    while response.get("IsTruncated"):
        response = client.list_objects_v2(Bucket=_bucket(), ContinuationToken=response["NextContinuationToken"])
        objects.extend(response.get("Contents", []))
    return [{"key": item["Key"]} for item in objects]


def _client():
    endpoint = os.getenv("S3_ENDPOINT_URL") or None
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
        region_name=os.getenv("S3_REGION", "us-east-1"),
        config=Config(s3={"addressing_style": "path"}),
    )


def _bucket() -> str:
    return os.getenv("S3_BUCKET", "edital-matcher")


def _ensure_bucket(client, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)


def _safe_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)[:100] or "default"


def _safe_filename(value: str) -> str:
    name = value.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:180] or "arquivo"
