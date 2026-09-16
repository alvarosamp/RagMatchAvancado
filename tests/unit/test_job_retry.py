import os
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test")

from app.jobs.models import JobStatus, JobType
from app.jobs.queue import prepare_failed_job_retry


def failed_job(job_type=JobType.CRM_NOTICE_MATCH, error="provider indisponivel"):
    return SimpleNamespace(
        status=JobStatus.FAILED,
        job_type=job_type,
        error_message=error,
        attempt_count=3,
        max_attempts=3,
        payload={"attempts": 3},
        progress=0.7,
        result={"partial": True},
        started_at=datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 16, 10, 5, tzinfo=timezone.utc),
    )


def test_manual_retry_preserves_history_and_grants_one_attempt():
    job = failed_job()
    retry_at = datetime(2026, 9, 16, 11, 0, tzinfo=timezone.utc)

    prepare_failed_job_retry(job, now=retry_at)

    assert job.status == JobStatus.PENDING
    assert job.max_attempts == 4
    assert job.attempt_count == 3
    assert job.payload["manual_retry_count"] == 1
    assert job.payload["last_manual_retry_at"] == retry_at.isoformat()
    assert job.progress == 0.0
    assert job.error_message is None
    assert job.started_at is None
    assert job.finished_at is None


def test_upload_retry_requires_a_new_upload():
    with pytest.raises(ValueError, match="Reenvie o arquivo"):
        prepare_failed_job_retry(failed_job(job_type=JobType.UPLOAD_EDITAL))


def test_cancelled_job_cannot_be_retried():
    with pytest.raises(ValueError, match="cancelados"):
        prepare_failed_job_retry(failed_job(error="Cancelado pelo usuário"))


def test_active_job_cannot_be_retried():
    job = failed_job()
    job.status = JobStatus.RUNNING
    with pytest.raises(ValueError, match="Somente jobs com falha"):
        prepare_failed_job_retry(job)
