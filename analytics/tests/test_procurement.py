import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.market_intelligence.adapters import normalized_record
from app.market_intelligence.models import Fact, RawRecord
from app.market_intelligence.procurement import compare_quote, stock_report
from fastapi import FastAPI
from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location(
    "procurement_api_test",
    Path(__file__).resolve().parents[2] / "backend/app/routers/market_intelligence.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
router = module.router


@pytest.fixture
def http(db):
    app = FastAPI()
    app.include_router(router)
    user = SimpleNamespace(id=100, tenant_id=1, role="admin")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, user


def seed(db, tenant=1):
    product = normalized_record(
        db, tenant, "manual", "product", {"id": "p", "name": "Switch"}
    )
    supplier = normalized_record(
        db, tenant, "manual", "supplier", {"id": "s", "name": "ACME LTDA"}
    )
    normalized_record(
        db,
        tenant,
        "manual",
        "product_supplier",
        {"id": "link", "product_id": "p", "supplier_id": "s"},
    )
    normalized_record(
        db,
        tenant,
        "manual",
        "demand",
        {
            "id": "d",
            "product_id": "p",
            "quantity": 10,
            "unit": "UN",
            "reference_price": 650,
            "event_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.commit()
    return product.id, supplier.id


def request_body(product):
    return {
        "product_id": product,
        "quantity": "8",
        "unit": "UN",
        "notes": "Confirmado para consulta aos fornecedores",
        "filters": {"source": "manual"},
        "needed_by": (datetime.now(timezone.utc) + timedelta(days=20))
        .date()
        .isoformat(),
    }


def quote_body(supplier, **overrides):
    return {
        "supplier_id": supplier,
        "unit_price": "500",
        "shipping": "40",
        "taxes": "10",
        "available_quantity": "20",
        "minimum_quantity": "1",
        "lead_time_days": 2,
        "valid_until": (datetime.now(timezone.utc) + timedelta(days=30))
        .date()
        .isoformat(),
        "notes": "Proposta documentada teste",
        **overrides,
    }


def test_stock_and_inquiry_quote_workflow_are_audited_without_becoming_orders(db, http):
    client, _ = http
    product, supplier = seed(db)
    stock = {
        "product_id": product,
        "unit": "UN",
        "quantity": "3",
        "reserved": "1",
        "observed_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        "notes": "Conferência física documentada",
    }
    assert (
        client.post(
            "/crm/market-intelligence/procurement/stock", json=stock
        ).status_code
        == 200
    )
    stock["quantity"] = "4"
    assert (
        client.post(
            "/crm/market-intelligence/procurement/stock", json=stock
        ).status_code
        == 200
    )
    assert db.query(RawRecord).filter_by(entity="inventory").count() == 2
    data = client.get("/crm/market-intelligence/procurement?source=manual").json()
    assert data["planning"][0]["quantity_to_quote"] == 7
    response = client.post(
        "/crm/market-intelligence/procurement/requests", json=request_body(product)
    )
    assert response.status_code == 201, response.text
    identity = response.json()["id"]
    assert response.json()["snapshot"]["observed"]["stock_available"] == 3
    first = client.post(
        f"/crm/market-intelligence/procurement/requests/{identity}/quotes",
        json=quote_body(supplier),
    ).json()
    assert (
        client.post(
            f"/crm/market-intelligence/procurement/requests/{identity}/quotes",
            json=quote_body(supplier, unit_price="480", shipping="300"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/crm/market-intelligence/procurement/requests/{identity}/quotes",
            json=quote_body(supplier, unit_price="1", shipping=None, taxes=None),
        ).status_code
        == 201
    )
    inquiry = client.get("/crm/market-intelligence/procurement?source=manual").json()[
        "requests"
    ][0]
    assert inquiry["status"] == "open"
    cheapest = [row for row in inquiry["quotes"] if row["lowest_complete_total"]]
    assert [row["id"] for row in cheapest] == [first["id"]]
    assert Decimal(cheapest[0]["total"]) == Decimal(4050)
    selected = client.post(
        f"/crm/market-intelligence/procurement/requests/{identity}/selection",
        json={"quote_id": first["id"], "reason": "Total e condições conferidos"},
    )
    assert selected.status_code == 200
    assert (
        selected.json()["selection_history"][0]["total_at_selection"]
        == "4050.000000000000"
    )
    assert db.query(Fact).filter(Fact.kind.in_(["purchase", "offer"])).count() == 0


def test_procurement_rejects_foreign_identities_and_quote_request_mismatch(db, http):
    client, user = http
    product, supplier = seed(db, 1)
    foreign, _ = seed(db, 2)
    body = request_body(foreign)
    assert (
        client.post(
            "/crm/market-intelligence/procurement/requests", json=body
        ).status_code
        == 404
    )
    request = client.post(
        "/crm/market-intelligence/procurement/requests", json=request_body(product)
    ).json()
    quote = client.post(
        f"/crm/market-intelligence/procurement/requests/{request['id']}/quotes",
        json=quote_body(supplier),
    ).json()
    second = client.post(
        "/crm/market-intelligence/procurement/requests", json=request_body(product)
    ).json()
    assert (
        client.post(
            f"/crm/market-intelligence/procurement/requests/{second['id']}/selection",
            json={"quote_id": quote["id"], "reason": "Proposta de outro processo"},
        ).status_code
        == 404
    )
    user.tenant_id = 2
    assert (
        client.get("/crm/market-intelligence/procurement?source=manual").json()[
            "requests"
        ]
        == []
    )
    assert (
        client.post(
            f"/crm/market-intelligence/procurement/requests/{request['id']}/quotes",
            json=quote_body(supplier),
        ).status_code
        == 404
    )


def test_viewer_cannot_record_stock_inquiries_quotes_or_selection(http):
    client, user = http
    user.role = "viewer"
    stock = {
        "product_id": "p",
        "quantity": 0,
        "reserved": 0,
        "unit": "UN",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "notes": "Documentado",
    }
    for path, body in [
        ("stock", stock),
        ("requests", request_body("p")),
        ("requests/x/quotes", quote_body("s")),
        ("requests/x/selection", {"quote_id": "q", "reason": "Documentado"}),
    ]:
        assert (
            client.post(
                "/crm/market-intelligence/procurement/" + path, json=body
            ).status_code
            == 403
        )


def test_invalid_stock_and_units_and_expired_quotes_fail_with_422(db, http):
    client, _ = http
    product, supplier = seed(db)
    stock = {
        "product_id": product,
        "quantity": "2",
        "reserved": "3",
        "unit": "UN",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "notes": "Documentado",
    }
    assert (
        client.post(
            "/crm/market-intelligence/procurement/stock", json=stock
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/crm/market-intelligence/procurement/stock",
            json={
                **stock,
                "reserved": "1",
                "observed_at": (
                    datetime.now(timezone.utc) + timedelta(days=1)
                ).isoformat(),
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/crm/market-intelligence/procurement/requests",
            json={**request_body(product), "unit": "KG"},
        ).status_code
        == 422
    )
    request = client.post(
        "/crm/market-intelligence/procurement/requests", json=request_body(product)
    ).json()
    assert (
        client.post(
            f"/crm/market-intelligence/procurement/requests/{request['id']}/quotes",
            json=quote_body(supplier, valid_until="2000-01-01"),
        ).status_code
        == 422
    )


@pytest.mark.parametrize("reason", ["missing", "stale", "partial", "mixed", "invalid"])
def test_unknown_stock_or_partial_demand_never_becomes_an_automatic_purchase_quantity(
    reason,
):
    as_of = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    demand = {
        "product_id": "p",
        "unit": "UN",
        "quantity": 10,
        "quantity_sample": 2,
        "items": 2,
        "product": "Switch",
        "value": 100,
    }
    stock = {
        "product_id": "p",
        "unit": "UN",
        "quantity": 4,
        "event_at": as_of,
        "attributes": {"procurement_stock": True, "reserved": "1"},
    }
    stocks = [stock]
    if reason == "missing":
        stocks = []
    elif reason == "stale":
        stock["event_at"] -= timedelta(days=8)
    elif reason == "partial":
        demand["quantity_sample"] = 1
    elif reason == "mixed":
        demand["unit"] = None
    else:
        stock["attributes"]["reserved"] = "invalid"
    result = stock_report([demand], stocks, as_of)[0]
    assert result["quantity_to_quote"] is None


def test_quote_total_keeps_decimal_precision_and_checks_arrival_availability_and_minimum():
    as_of = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    request = {
        "quantity": Decimal("99999999999999.999999"),
        "needed_by": as_of.date() + timedelta(days=1),
    }
    quote = {
        "unit_price": Decimal("99999999999999.999999"),
        "shipping": Decimal("0.01"),
        "taxes": Decimal("0.02"),
        "available_quantity": Decimal(1),
        "minimum_quantity": Decimal(100000000000000),
        "valid_until": as_of.date() + timedelta(days=1),
        "lead_time_days": 3,
    }
    result = compare_quote(request, quote, as_of)
    assert result["total"] == "9999999999999999999800000000.030000000001"
    assert set(result["flags"]) == {
        "insufficient_availability",
        "below_minimum",
        "after_deadline",
    }


def test_supplier_consolidation_remaps_quotes_and_preserves_original_evidence(db, http):
    from app.market_intelligence.models import Entity, SupplierQuote
    from app.market_intelligence.suppliers import merge_supplier

    client, _ = http
    product, supplier = seed(db)
    inquiry = client.post(
        "/crm/market-intelligence/procurement/requests", json=request_body(product)
    ).json()
    quote = client.post(
        f"/crm/market-intelligence/procurement/requests/{inquiry['id']}/quotes",
        json=quote_body(supplier),
    ).json()
    target = normalized_record(
        db, 1, "manual", "supplier", {"id": "new", "name": "ACME"}
    )
    current = db.query(Entity).filter_by(id=supplier).one()
    original = db.query(SupplierQuote).filter_by(id=quote["id"]).one().evidence.copy()
    merge_supplier(db, 1, current, target)
    db.commit()
    row = db.query(SupplierQuote).filter_by(id=quote["id"]).one()
    assert row.supplier_id == target.id
    assert row.evidence == original
    data = client.get("/crm/market-intelligence/procurement?source=manual").json()
    assert data["requests"][0]["quotes"][0]["supplier"] == target.name


def test_older_stock_observation_cannot_overwrite_current_balance(db, http):
    client, _ = http
    product, _ = seed(db)
    observed = datetime.now(timezone.utc) - timedelta(minutes=5)
    stock = {
        "product_id": product,
        "unit": "UN",
        "quantity": "4",
        "reserved": "1",
        "observed_at": observed.isoformat(),
        "notes": "Conferência documentada",
    }
    assert (
        client.post(
            "/crm/market-intelligence/procurement/stock", json=stock
        ).status_code
        == 200
    )
    stock.update(quantity="99", observed_at=(observed - timedelta(hours=1)).isoformat())
    assert (
        client.post(
            "/crm/market-intelligence/procurement/stock", json=stock
        ).status_code
        == 422
    )
    data = client.get("/crm/market-intelligence/procurement?source=manual").json()
    assert data["planning"][0]["stock_available"] == 3


def test_negotiation_summary_filters_and_tenant_scope(db, http):
    from app.market_intelligence.models import SupplierQuote

    client, user = http
    product, supplier = seed(db)
    foreign_product, _ = seed(db, 2)
    first = client.post(
        "/crm/market-intelligence/procurement/requests", json=request_body(product)
    ).json()
    client.post(
        "/crm/market-intelligence/procurement/requests", json=request_body(product)
    )
    quotes = []
    for fields in [
        {},
        {"shipping": None},
        {
            "valid_until": (
                datetime.now(timezone.utc).date() + timedelta(days=20)
            ).isoformat()
        },
    ]:
        response = client.post(
            f"/crm/market-intelligence/procurement/requests/{first['id']}/quotes",
            json=quote_body(supplier, **fields),
        )
        assert response.status_code == 201, response.text
        quotes.append(response.json())
    expired = db.query(SupplierQuote).filter_by(id=quotes[0]["id"]).one()
    expired.valid_until = datetime.now(timezone.utc).date() - timedelta(days=1)
    db.commit()
    url = "/crm/market-intelligence/procurement?source=manual"
    data = client.get(url).json()
    summary = data["negotiations"]
    assert summary["requests"] == 2 and summary["quotes"] == 3
    assert summary["awaiting_quotes"] == 1
    assert summary["expired"] == 1 and summary["incomplete"] == 1
    assert summary["suppliers"][0]["quotes"] == 3
    assert summary["suppliers"][0]["requests"] == 1
    assert len(summary["suppliers"]) == 1
    for state in ["expired", "incomplete"]:
        filtered = client.get(url + "&negotiation_state=" + state).json()
        assert [row["id"] for row in filtered["requests"]] == [first["id"]]
        assert filtered["negotiations"] == summary
    waiting = client.get(url + "&negotiation_state=awaiting_quotes").json()
    assert waiting["request_total"] == 1 and not waiting["requests"][0]["quotes"]
    assert client.get(url + "&negotiation_search=%25").json()["request_total"] == 0
    assert client.get(url + "&negotiation_search=sWiTcH").json()["request_total"] == 2
    assert (
        client.get(url + "&negotiation_supplier=" + supplier).json()["request_total"]
        == 1
    )
    assert client.get(url + "&offset=25").json()["negotiations"] == summary
    assert client.get(url + "&negotiation_state=invalid").status_code == 422
    user.tenant_id = 2
    client.post(
        "/crm/market-intelligence/procurement/requests",
        json=request_body(foreign_product),
    )
    second = client.get(url + "&negotiation_supplier=" + supplier).json()
    assert second["request_total"] == 0
    assert second["negotiations"]["requests"] == 1
    assert second["negotiations"]["quotes"] == 0
    assert second["negotiations"]["suppliers"] == []


def test_negotiation_validity_boundaries_use_brasilia_calendar(db, http):
    from unittest.mock import patch

    from app.market_intelligence.models import SupplierQuote
    from app.market_intelligence.negotiations import overview

    client, _ = http
    product, supplier = seed(db)
    request = client.post(
        "/crm/market-intelligence/procurement/requests", json=request_body(product)
    ).json()
    for days in [-1, 0, 7, 8]:
        response = client.post(
            f"/crm/market-intelligence/procurement/requests/{request['id']}/quotes",
            json=quote_body(supplier),
        ).json()
        quote = db.query(SupplierQuote).filter_by(id=response["id"]).one()
        quote.valid_until = datetime(
            2026, 10, 9, tzinfo=timezone.utc
        ).date() + timedelta(days=days)
    db.commit()
    with patch(
        "app.market_intelligence.negotiations.now",
        return_value=datetime(2026, 10, 10, 1, tzinfo=timezone.utc),
    ):
        summary = overview(db, 1)
    assert summary["as_of"] == "2026-10-09"
    assert summary["expired"] == 1 and summary["expiring"] == 2


def test_comparison_breakdown_differences_ties_and_incomplete_conditions():
    from app.market_intelligence.procurement import compare_proposals

    proposals = [
        {"id": "a", "comparable": True, "total": "4050.000000000000"},
        {"id": "b", "comparable": True, "total": "4150.000000000000"},
        {"id": "tie", "comparable": True, "total": "4050"},
        {"id": "incomplete", "comparable": False, "total": None},
        {"id": "expired-cheap", "comparable": False, "total": "1"},
    ]
    rows = compare_proposals(proposals)
    assert [row["id"] for row in rows if row["lowest_complete_total"]] == ["a", "tie"]
    assert Decimal(rows[1]["difference_to_lowest_complete"]) == 100
    assert all(row["difference_to_lowest_complete"] is None for row in rows[3:])
    assert compare_proposals(proposals[3:])[0]["difference_to_lowest_complete"] is None
    assert compare_proposals([]) == []


def test_comparison_preserves_large_exact_difference():
    from app.market_intelligence.procurement import compare_proposals

    rows = compare_proposals(
        [
            {"comparable": True, "total": "9999999999999999999800000000.030000000001"},
            {"comparable": True, "total": "9999999999999999999800000000.040000000002"},
        ]
    )
    assert Decimal(rows[1]["difference_to_lowest_complete"]) == Decimal(
        "0.010000000001"
    )
