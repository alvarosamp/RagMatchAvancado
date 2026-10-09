from datetime import datetime, timezone
from decimal import Decimal

from app.market_intelligence.metrics import benchmarks, build_report, supplier_metrics


def demand(id, **values):
    return {
        "id": id,
        "kind": "demand",
        "source": "crm",
        "notice_id": "n1",
        "event_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "total_value": Decimal(100),
        "coverage": "unassessed",
        "category": "Switch",
        **values,
    }


def test_coverage_keeps_unknown_and_rejected_selections_separate():
    rows = [
        demand("1", coverage="covered"),
        demand("2", coverage="rejected_selection"),
        demand("3", total_value=None),
    ]
    report = build_report(rows, [], [])
    assert report["summary"]["demand_weighted_coverage"] == 0.5
    assert report["summary"]["unassessed_items"] == 1
    assert report["summary"]["rejected_selections"] == 1
    assert report["summary"]["confirmed_gap_items"] == 0
    assert report["summary"]["win_rate"] is None


def test_unit_and_price_semantics_split_benchmarks():
    rows = [
        {
            "product_id": "p",
            "unit": "UN",
            "currency": "BRL",
            "price_type": "winning_price",
            "unit_price": Decimal(10),
        },
        {
            "product_id": "p",
            "unit": "KIT",
            "currency": "BRL",
            "price_type": "winning_price",
            "unit_price": Decimal(100),
        },
        {
            "product_id": "p",
            "unit": "UN",
            "currency": "BRL",
            "price_type": "supplier_cost",
            "unit_price": Decimal(4),
        },
        {"category": "Switch", "unit": "UN", "unit_price": Decimal(5)},
    ]
    groups, excluded = benchmarks(rows)
    assert len(groups) == 3
    assert excluded == 1
    assert all(g["sample"] == 1 and not g["sufficient"] for g in groups)


def test_missing_receipt_does_not_count_as_failed_delivery():
    supplier = {"id": "s", "name": "ACME"}
    purchases = [
        {
            "supplier_id": "s",
            "quantity": Decimal(1),
            "total_value": Decimal(10),
            "attributes": {},
        }
    ]
    report = supplier_metrics(purchases, [], [supplier], [])[0]
    assert report["otif"] is None
    assert report["delivery_sample"] == 0


def test_real_receipt_has_correct_otif_and_fill_rate():
    supplier = {"id": "s", "name": "ACME"}
    row = {
        "supplier_id": "s",
        "quantity": Decimal(10),
        "total_value": Decimal(100),
        "event_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "attributes": {
            "promised_at": "2026-10-09T12:00:00Z",
            "received_at": "2026-10-08T12:00:00Z",
            "quantity_received": 10,
        },
    }
    report = supplier_metrics([row], [], [supplier], [])[0]
    assert report["otif"] == 1
    assert report["fill_rate"] == 1
    assert report["lead_time_p50"] == 7.5


def test_monthly_sources_remain_separate_and_use_sao_paulo_month():
    moment = datetime(2026, 10, 1, 1, tzinfo=timezone.utc)
    result = build_report(
        [demand("1", event_at=moment), demand("2", source="pncp", event_at=moment)],
        [],
        [],
    )
    assert result["timeline"] == [
        {"source": "crm", "month": "2026-09", "items": 1, "observed_value": 100.0},
        {"source": "pncp", "month": "2026-09", "items": 1, "observed_value": 100.0},
    ]


def test_offered_brand_does_not_invent_demand_brand_or_mix_public_shares():
    offered = demand("o", kind="offer", product_id="p", offered_price=Decimal(50))
    result = build_report(
        [demand("d"), offered, demand("public", source="pncp", brand="Other")],
        [{"id": "p", "kind": "product", "brand": "ACME"}],
        [],
    )
    acme = next(row for row in result["brands"] if row["brand"] == "ACME")
    assert acme["offered_items"] == 1 and acme["offer_share"] == 1
    assert acme["demanded_items"] == 0 and acme["demand_share"] is None
    assert (
        next(row for row in result["brands"] if row["brand"] == "Other")["demand_share"]
        == 1
    )
    assert all(row["month"] == "2026-09" for row in result["brand_trends"])
