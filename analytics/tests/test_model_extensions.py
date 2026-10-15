from datetime import datetime, timezone
from decimal import Decimal

from app.market_intelligence.deflation import deflated_benchmarks
from app.market_intelligence.review_models import evaluate_reviews


def test_review_models_require_human_labels(db):
    for task in ["technical_match", "entity_resolution"]:
        rows, result = evaluate_reviews(db, 1, task)
        assert not rows
        assert result["status"] == "insufficient_data"
        assert not result["automatic_matching"]


def test_deflation_uses_levels_and_exact_event_month():
    prices = [
        {
            "product_id": "p",
            "unit": "UN",
            "currency": "BRL",
            "price_type": "supplier_cost",
            "unit_price": Decimal(10),
            "event_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
    ]
    indices = [
        {
            "unit_price": Decimal(level),
            "attributes": {
                "table": 1737,
                "variable": 2266,
                "month": month,
                "unit": "Número-índice",
            },
        }
        for month, level in [("202601", 100), ("202602", 110)]
    ]
    result = deflated_benchmarks(prices, indices, "1737:2266")
    assert result["rows"][0]["median"] == 11
    assert result["base_month"] == "202602"
    for row in indices:
        row["attributes"]["unit"] = "%"
    assert deflated_benchmarks(prices, indices, "1737:2266")["status"] == "unavailable"
