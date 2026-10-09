from app.market_intelligence.adapters import normalized_record
from app.market_intelligence.models import Fact, SyncRun
from app.market_intelligence.repository import scoped
from app.market_intelligence.worker import process_one
from sqlalchemy.orm import sessionmaker


def test_failed_source_rolls_back_snapshot_and_records_failure(db, monkeypatch):
    from app.market_intelligence import worker

    run = SyncRun(tenant_id=1, source="crm")
    db.add(run)
    db.commit()

    def fail(session, tenant_id, run, factory):
        normalized_record(
            session,
            tenant_id,
            "crm",
            "demand",
            {"id": "partial", "event_at": "2026-10-01"},
        )
        raise ValueError("private upstream details")

    monkeypatch.setattr(worker, "run_source", fail)
    assert process_one(sessionmaker(bind=db.get_bind()), 1)
    db.expire_all()
    assert scoped(db, Fact, 1).count() == 0
    assert run.status == "failed"
    assert "private upstream details" not in run.error


def test_core_completion_enqueues_one_durable_dbt_follow_up(db, monkeypatch):
    from app.market_intelligence import worker

    monkeypatch.setenv("MARKET_DBT_ENABLED", "true")
    monkeypatch.setattr(worker, "run_source", lambda *args: {"records": 1})
    run = SyncRun(tenant_id=1, source="crm")
    db.add(run)
    db.commit()
    assert process_one(sessionmaker(bind=db.get_bind()), 1)
    db.expire_all()
    assert run.status == "completed"
    follow_up = scoped(db, SyncRun, 1).filter_by(source="marts").one()
    assert follow_up.status == "queued"
    assert follow_up.parameters["parent_run_id"] == run.id
