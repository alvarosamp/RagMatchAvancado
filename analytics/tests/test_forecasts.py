from datetime import datetime, timezone
from types import SimpleNamespace

from app.market_intelligence.training import forecast_report


def prices(values):
    return [
        SimpleNamespace(
            kind="price",
            product_id="p",
            unit="UN",
            currency="BRL",
            state="SP",
            price_type="winning_price",
            unit_price=value,
            event_at=datetime(2023 + i // 12, i % 12 + 1, 15, 12, tzinfo=timezone.utc),
        )
        for i, value in enumerate(values)
    ]


def test_forecast_interval_requires_history_beyond_model_selection_months():
    row = forecast_report(prices([100] * 24), "price_forecast")["series"][0]
    assert row["interval"] is None
    assert row["interval_status"] == "insufficient_calibration_history"
    assert row["forecast_month"] == "2025-01"


def test_holdout_shock_does_not_inflate_calibration_interval():
    row = forecast_report(
        prices([100] * 30 + [200, 300, 400, 500, 600, 700]), "price_forecast"
    )["series"][0]
    assert row["method"] == "naive"
    assert row["interval"]["calibration_months"] == 18
    assert row["interval"]["lower"] == row["interval"]["upper"] == 700
    assert row["interval"]["holdout_coverage"] == 0
    assert not row["interval"]["coverage_guaranteed"]


def test_moving_median_wins_robust_backtest_and_monthly_price_uses_true_median():
    row = forecast_report(
        prices([100] * 30 + [1000, 100, 100, 1000, 100, 100]), "price_forecast"
    )["series"][0]
    assert row["method"] == "moving_median_3"
    assert row["next_month"] == 100
    assert row["selected_mae"] < row["naive_mae"]
    doubled = prices([10] * 24) + prices([30] * 24)
    assert forecast_report(doubled, "price_forecast")["series"][0]["next_month"] == 20


def test_forecasts_refuse_missing_months():
    rows = prices([100] * 36)
    del rows[10]
    row = forecast_report(rows, "price_forecast")["series"][0]
    assert row["status"] == "incomplete_month_coverage"


def test_demand_forecasts_keep_crm_and_public_demand_separate():
    rows = [
        SimpleNamespace(
            kind="demand", source=source, category="Switch", event_at=row.event_at
        )
        for source in ("crm", "pncp")
        for row in prices([100] * 24)
    ]
    result = forecast_report(rows, "demand_forecast")
    assert {row["source"] for row in result["series"]} == {"crm", "pncp"}
    assert all(row["next_month"] == 1 for row in result["series"])


def test_forecast_versions_capture_real_dataset_and_sample_count(db):
    from app.market_intelligence.adapters import normalized_record
    from app.market_intelligence.models import Fact, ModelRun
    from app.market_intelligence.training import train_task

    for i, row in enumerate(prices([100] * 36)):
        normalized_record(
            db,
            1,
            "manual",
            "demand",
            {"id": f"d{i}", "category": "Switch", "event_at": row.event_at.isoformat()},
        )
    db.flush()
    assert train_task(db, 1, "demand_forecast")["samples"] == 36
    db.flush()
    first = db.query(ModelRun).one()
    assert first.feature_version == "forecast-v2" and first.dataset_version
    db.query(Fact).filter_by(source_id="d0").one().active = False
    db.flush()
    train_task(db, 1, "demand_forecast")
    db.flush()
    assert (
        db.query(ModelRun).filter(ModelRun.id != first.id).one().dataset_version
        != first.dataset_version
    )
