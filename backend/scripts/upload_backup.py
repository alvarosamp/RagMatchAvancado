"""Upload a complete backup set to an independent S3-compatible bucket.

The uploader is intentionally separate from the application object storage:
backup credentials only exist in the short-lived backup container.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Variavel obrigatoria ausente: {name}")
    return value


def _validate_endpoint(endpoint_url: str | None) -> None:
    if not endpoint_url:
        return  # AWS S3 uses the SDK default endpoint.
    hostname = (urlparse(endpoint_url).hostname or "").lower()
    if hostname in {"localhost", "minio", "127.0.0.1", "::1"}:
        raise RuntimeError(
            "BACKUP_S3_ENDPOINT_URL deve apontar para storage externo, nao para o MinIO local."
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup_files(directory: Path, stamp: str) -> list[Path]:
    files = [
        directory / f"postgres-{stamp}.dump",
        directory / f"minio-{stamp}.tgz",
        directory / f"checksums-{stamp}.sha256",
    ]
    missing = [path.name for path in files if not path.is_file()]
    if missing:
        raise RuntimeError(f"Conjunto de backup incompleto: {', '.join(missing)}")
    return files


def _client():
    import boto3

    endpoint_url = os.getenv("BACKUP_S3_ENDPOINT_URL", "").strip() or None
    _validate_endpoint(endpoint_url)
    kwargs = {
        "service_name": "s3",
        "region_name": os.getenv("BACKUP_S3_REGION", "us-east-1"),
    }
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    access_key = os.getenv("BACKUP_S3_ACCESS_KEY", "").strip()
    secret_key = os.getenv("BACKUP_S3_SECRET_KEY", "").strip()
    if access_key or secret_key:
        if not (access_key and secret_key):
            raise RuntimeError("Informe BACKUP_S3_ACCESS_KEY e BACKUP_S3_SECRET_KEY juntos.")
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
    return boto3.client(**kwargs)


def upload_backup(directory: Path, stamp: str, client=None) -> list[str]:
    bucket = _required_env("BACKUP_S3_BUCKET")
    prefix = os.getenv("BACKUP_S3_PREFIX", "ragmatch-backups").strip().strip("/")
    sse = os.getenv("BACKUP_S3_SSE", "AES256").strip()
    files = _backup_files(directory, stamp)
    client = client or _client()
    uploaded = []

    for path in files:
        key = "/".join(part for part in (prefix, stamp, path.name) if part)
        checksum = _sha256(path)
        extra_args = {"Metadata": {"sha256": checksum}}
        if sse:
            extra_args["ServerSideEncryption"] = sse
        client.upload_file(str(path), bucket, key, ExtraArgs=extra_args)
        remote = client.head_object(Bucket=bucket, Key=key)
        if int(remote.get("ContentLength", -1)) != path.stat().st_size:
            raise RuntimeError(f"Tamanho remoto invalido apos upload: {key}")
        remote_checksum = (remote.get("Metadata") or {}).get("sha256")
        if remote_checksum != checksum:
            raise RuntimeError(f"Checksum remoto invalido apos upload: {key}")
        uploaded.append(key)

    return uploaded


def main() -> int:
    parser = argparse.ArgumentParser(description="Envia backup para storage S3 externo.")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--stamp", default=os.getenv("BACKUP_STAMP", ""))
    args = parser.parse_args()
    if not args.stamp:
        parser.error("informe --stamp ou BACKUP_STAMP")

    uploaded = upload_backup(args.directory, args.stamp)
    print(f"Backup externo verificado: {len(uploaded)} objetos enviados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
