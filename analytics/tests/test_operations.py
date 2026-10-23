from datetime import datetime, timedelta, timezone

from app.market_intelligence.models import SyncRun
from app.market_intelligence.operations import operations_report

CLOCK = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


def run(db, tenant=1, source="crm", status="completed", duration=10, days=1):
    started = CLOCK - timedelta(days=days)
    db.add(
        SyncRun(
            tenant_id=tenant,
            source=source,
            status=status,
            created_at=started - timedelta(seconds=5),
            started_at=started,
            finished_at=started + timedelta(seconds=duration)
            if status in {"completed", "failed"}
            else None,
        )
    )
    db.flush()


def test_operations_measures_duration_and_does_not_leak_other_tenant(db):
    run(db, duration=10)
    run(db, duration=30)
    run(db, tenant=2, source="bling", status="failed")
    result = operations_report(db, 1, clock=CLOCK)
    assert result["status"] == "healthy"
    source = result["sources"][0]
    assert len(result["sources"]) == 1
    assert source["completed"] == 2 and source["failed"] == 0
    assert source["duration_p50_seconds"] == 20
    assert source["duration_p95_seconds"] == 30
    assert source["queue_wait_p50_seconds"] == 5


def test_old_pending_jobs_remain_visible_outside_measurement_window(db):
    run(db, status="queued", days=40)
    run(db, source="pncp", status="running", days=1)
    result = operations_report(db, 1, clock=CLOCK)
    codes = {(row["source"], row["code"]) for row in result["alerts"]}
    assert ("crm", "queue_wait_exceeded") in codes
    assert ("pncp", "running_job_exceeded") in codes
    assert result["sources"][0]["queued"] == 1


def test_failures_use_terminal_denominator_and_missing_duration_stays_unknown(db):
    run(db, status="failed")
    run(db, status="completed")
    run(db, status="queued")
    result = operations_report(db, 1, clock=CLOCK, sample_limit=1)
    source = result["sources"][0]
    assert source["failure_rate"] == 0.5
    assert source["sample_truncated"]
    assert "source_failures_in_window" in source["alerts"]
    empty = operations_report(db, 2, clock=CLOCK)["sources"][0]
    assert empty["failure_rate"] is None and empty["duration_p50_seconds"] is None
