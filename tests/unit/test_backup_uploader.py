"""Tests for the independent off-site backup uploader."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "upload_backup.py"
SPEC = importlib.util.spec_from_file_location("backup_uploader_under_test", SCRIPT)
uploader = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(uploader)


FIXTURE_DIRECTORY = ROOT / "tests" / "fixtures" / "backup-set"
FIXTURE_STAMP = "20260918T120000Z"


def test_local_minio_endpoint_is_rejected():
    with pytest.raises(RuntimeError, match="storage externo"):
        uploader._validate_endpoint("http://minio:9000")


def test_uploads_and_verifies_complete_backup_set(monkeypatch):
    stamp = FIXTURE_STAMP
    files = uploader._backup_files(FIXTURE_DIRECTORY, stamp)
    monkeypatch.setenv("BACKUP_S3_BUCKET", "external-backups")
    monkeypatch.setenv("BACKUP_S3_PREFIX", "prod")
    client = MagicMock()
    sizes = {f"prod/{stamp}/{path.name}": path.stat().st_size for path in files}
    checksums = {f"prod/{stamp}/{path.name}": uploader._sha256(path) for path in files}
    client.head_object.side_effect = lambda Bucket, Key: {
        "ContentLength": sizes[Key],
        "Metadata": {"sha256": checksums[Key]},
    }

    keys = uploader.upload_backup(FIXTURE_DIRECTORY, stamp, client=client)

    assert keys == list(sizes)
    assert client.upload_file.call_count == 3
    assert client.head_object.call_count == 3


def test_incomplete_backup_set_is_not_uploaded(monkeypatch):
    monkeypatch.setenv("BACKUP_S3_BUCKET", "external-backups")

    with pytest.raises(RuntimeError, match="Conjunto de backup incompleto"):
        uploader.upload_backup(FIXTURE_DIRECTORY, "missing", client=MagicMock())
