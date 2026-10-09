import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.market_intelligence.adapters import normalized_record
from fastapi import FastAPI
from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location(
    "market_api_test",
    Path(__file__).resolve().parents[2] / "backend/app/routers/market_intelligence.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
router = module.router


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(router)
    user = SimpleNamespace(id=100, tenant_id=1, role="admin")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, user


def test_api_hides_other_tenant_and_exports_same_filter(db, client):
    http, _ = client
    for tenant, category in [(1, "Switch"), (1, "Monitor"), (2, "Switch")]:
        normalized_record(
            db,
            tenant,
            "crm",
            "demand",
            {
                "id": category,
                "category": category,
                "description": "=external formula",
                "event_at": "2026-10-01T12:00:00Z",
                "reference_price": 10,
                "quantity": 2,
            },
        )
    db.commit()
    response = http.get("/crm/market-intelligence/facts?category=Switch")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["rows"][0]["tenant_id"] == 1
    csv = http.get("/crm/market-intelligence/export?category=Switch&section=assortment")
    assert csv.status_code == 200
    assert "Switch" in csv.text and "Monitor" not in csv.text


def test_viewer_cannot_write_or_enqueue(client):
    http, user = client
    user.role = "viewer"
    assert (
        http.post("/crm/market-intelligence/suppliers/normalize", json={}).status_code
        == 403
    )
    assert (
        http.post("/crm/market-intelligence/sync", json={"source": "crm"}).status_code
        == 403
    )
    assert (
        http.post(
            "/crm/market-intelligence/feedback", json={"item_id": "x", "action": "bid"}
        ).status_code
        == 403
    )


def test_operational_switch_preserves_history_and_blocks_reads_and_jobs(
    db, client, monkeypatch
):
    from app.market_intelligence.models import SyncRun
    from app.market_intelligence.worker import process_one

    http, _ = client
    db.add(SyncRun(tenant_id=1, source="crm"))
    db.commit()
    monkeypatch.setenv("MARKET_INTELLIGENCE_ENABLED", "false")
    assert http.get("/crm/market-intelligence/operations").status_code == 503
    assert (
        http.post("/crm/market-intelligence/sync", json={"source": "crm"}).status_code
        == 503
    )
    assert not process_one(
        lambda: (_ for _ in ()).throw(AssertionError("Must not claim jobs")), 1
    )
    assert db.query(SyncRun).one().status == "queued"


def test_bling_is_explicitly_planned_until_enabled(client, monkeypatch):
    http, _ = client
    monkeypatch.delenv("MARKET_BLING_ANALYTICS_ENABLED", raising=False)
    assert (
        http.get("/crm/market-intelligence/capabilities").json()["sources"]["bling"]
        == "planned"
    )
    assert (
        http.post("/crm/market-intelligence/sync", json={"source": "bling"}).status_code
        == 422
    )


def test_fact_drilldown_preserves_product_price_type_filters_and_tenant(db, client):
    from app.market_intelligence.models import Fact

    http, _ = client
    for tenant, identity, product, price_type in [
        (1, "1", "p", "winning_price"),
        (1, "2", "q", "winning_price"),
        (1, "3", "p", "supplier_cost"),
        (2, "4", "p", "winning_price"),
    ]:
        normalized_record(
            db,
            tenant,
            "manual",
            "price",
            {
                "id": identity,
                "event_at": "2026-10-01",
                "price_type": price_type,
                "unit_price": 10,
            },
        )
        db.flush()
        db.query(Fact).filter_by(
            tenant_id=tenant, source_id=identity
        ).one().product_id = product
    db.commit()
    result = http.get(
        "/crm/market-intelligence/facts?kind=price&product_id=p&price_type=winning_price"
    )
    assert result.status_code == 200
    assert result.json()["total"] == 1 and result.json()["rows"][0]["source_id"] == "1"
    normalized_record(
        db, 1, "manual", "demand", {"id": "unknown", "event_at": "2026-10-01"}
    )
    db.commit()
    unknown = http.get(
        "/crm/market-intelligence/facts?kind=demand&unresolved_product=true"
    )
    assert (
        unknown.json()["total"] == 1 and unknown.json()["rows"][0]["product_id"] is None
    )


def test_model_queue_deduplicates_each_task_even_with_other_task_first(client):
    http, _ = client
    ids = {}
    for task in (
        "win_probability",
        "technical_match",
        "win_probability",
        "technical_match",
    ):
        response = http.post(
            "/crm/market-intelligence/sync", json={"source": "models", "task": task}
        )
        assert response.status_code == 202
        run_id = response.json()["id"]
        if task in ids:
            assert run_id == ids[task]
        else:
            ids[task] = run_id
    assert len(set(ids.values())) == 2


def test_operations_reader_access_is_scoped_to_current_tenant(db, client):
    from app.market_intelligence.models import SyncRun

    http, user = client
    user.role = "viewer"
    db.add(SyncRun(tenant_id=2, source="bling", status="failed"))
    db.commit()
    response = http.get("/crm/market-intelligence/operations")
    assert response.status_code == 200
    assert [row["source"] for row in response.json()["sources"]] == ["crm"]
    assert http.get("/crm/market-intelligence/operations?days=91").status_code == 422


def test_feedback_cannot_address_another_tenant(db, client):
    http, _ = client
    normalized_record(
        db,
        2,
        "manual",
        "demand",
        {"id": "other", "item_id": "other", "event_at": "2026-10-01"},
    )
    db.commit()
    assert (
        http.post(
            "/crm/market-intelligence/feedback",
            json={"item_id": "other", "action": "bid"},
        ).status_code
        == 404
    )


def test_inverted_date_filter_and_missing_gap_evidence_rejected(client):
    http, _ = client
    assert (
        http.get(
            "/crm/market-intelligence/report?date_from=2026-10-02&date_to=2026-10-01"
        ).status_code
        == 422
    )
    assert (
        http.post(
            "/crm/market-intelligence/feedback",
            json={"item_id": "x", "action": "confirmed_gap"},
        ).status_code
        == 422
    )
