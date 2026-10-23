from datetime import datetime, timedelta, timezone

from app.market_intelligence.training import predict_snapshot, readiness, temporal_split


def test_temporal_split_never_splits_one_notice():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"group": f"n{i // 2}", "decision_at": now + timedelta(days=i), "target": i % 2}
        for i in range(50)
    ]
    train, test = temporal_split(rows)
    assert {r["group"] for r in train}.isdisjoint({r["group"] for r in test})
    assert max(r["decision_at"] for r in train) < min(r["decision_at"] for r in test)


def test_insufficient_labels_cannot_enable_probability_model():
    report, _, _ = readiness([])
    assert not report["ready"]
    assert report["reasons"]


def test_serving_parameters_reproduce_logistic_probability():
    result = predict_snapshot(
        {"quantity": 10},
        {
            "features": ["quantity"],
            "medians": [5],
            "means": [5],
            "scales": [5],
            "weights": [1],
            "intercept": 0,
        },
    )
    assert abs(result["probability"] - 0.7310585786) < 1e-9
    assert result["mode"] == "shadow"
