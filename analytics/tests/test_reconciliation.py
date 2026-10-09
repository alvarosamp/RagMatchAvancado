from app.market_intelligence.adapters import bling_record
from app.market_intelligence.models import Fact
from app.market_intelligence.repository import scoped
from app.market_intelligence.worker import source_should_transform


def test_order_revision_removes_deleted_lines_and_their_prices(db):
    order = {
        "id": 1,
        "data": "2026-10-01",
        "itens": [
            {"id": 11, "quantidade": 2, "valor": 10},
            {"id": 12, "quantidade": 3, "valor": 20},
        ],
    }
    bling_record(db, 1, "purchase", order)
    assert scoped(db, Fact, 1).filter_by(active=True).count() == 4
    bling_record(db, 1, "purchase", {**order, "itens": order["itens"][:1]})
    db.expire_all()
    assert scoped(db, Fact, 1).filter_by(active=True).count() == 2
    assert scoped(db, Fact, 1).count() == 4


def test_transform_follow_up_requires_configured_dbt(monkeypatch):
    monkeypatch.delenv("MARKET_DBT_ENABLED", raising=False)
    assert not source_should_transform("crm")
    monkeypatch.setenv("MARKET_DBT_ENABLED", "true")
    assert source_should_transform("crm")
    assert not source_should_transform("marts")


def test_source_supplier_win_rate_does_not_credit_competitor():
    from app.market_intelligence.metrics import supplier_metrics

    suppliers = [
        {"id": "ours", "name": "Our source"},
        {"id": "winner", "name": "Competitor"},
    ]
    awards = [
        {"source": "crm", "item_id": "i", "supplier_id": "winner", "outcome": "lost"}
    ]
    offers = [{"source": "crm", "item_id": "i", "supplier_id": "ours"}]
    rows = {
        row["id"]: row for row in supplier_metrics([], awards, suppliers, [], offers)
    }
    assert rows["ours"]["win_rate"] == 0
    assert rows["ours"]["results_sample"] == 1
    assert rows["winner"]["win_rate"] is None
