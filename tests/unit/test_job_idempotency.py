import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test")

from app.jobs import queue
from app.jobs.queue import classify_job_failure, normalize_idempotency_key


def _job_model_stub():
    return SimpleNamespace(
        id=MagicMock(),
        status=MagicMock(),
        progress=MagicMock(),
        started_at=MagicMock(),
        finished_at=MagicMock(),
        error_message=MagicMock(),
        failure_code=MagicMock(),
        attempt_count=MagicMock(),
    )


def test_idempotency_key_is_normalized():
    assert normalize_idempotency_key("  request-123  ") == "request-123"
    assert normalize_idempotency_key("   ") is None
    assert normalize_idempotency_key(None) is None


def test_idempotency_key_rejects_oversized_values():
    with pytest.raises(ValueError, match="128"):
        normalize_idempotency_key("x" * 129)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("slow provider"), "timeout"),
        (ConnectionError("offline"), "dependency_unavailable"),
        (RuntimeError("invalid output"), "execution_error"),
    ],
)
def test_failure_classification(error, expected):
    assert classify_job_failure(error) == expected


def test_duplicate_delivery_cannot_claim_a_non_pending_job(monkeypatch):
    monkeypatch.setattr(queue, "Job", _job_model_stub())
    db = MagicMock()
    db.query.return_value.filter.return_value.update.return_value = 0

    assert queue._claim_job(db, "job-1") is False
    db.get.assert_not_called()


def test_first_delivery_claims_and_records_attempt_in_payload(monkeypatch):
    monkeypatch.setattr(queue, "Job", _job_model_stub())
    db = MagicMock()
    db.query.return_value.filter.return_value.update.return_value = 1
    job = SimpleNamespace(
        id="job-1",
        correlation_id="correlation-1",
        attempt_count=2,
        max_attempts=3,
        payload={"tenant_id": "acme"},
    )
    db.get.return_value = job

    assert queue._claim_job(db, "job-1") is True
    assert job.payload["attempts"] == 2
    assert db.commit.call_count == 2
