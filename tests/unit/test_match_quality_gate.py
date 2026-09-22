import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.services.match_quality_gate import evaluate_match_quality_gate


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "match_quality_smoke.json"


def _records():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["records"]


def _gate(records, **overrides):
    policy = dict(min_records=4, min_recall_at_1=0.75, min_recall_at_3=1.0,
                  min_decision_records=4, max_false_accept_rate=0.0)
    policy.update(overrides)
    return evaluate_match_quality_gate(records, **policy)


def test_smoke_snapshot_meets_contract():
    report = _gate(_records())
    assert report["passed"] is True
    assert report["metrics"]["recall_at_1"] == 0.75
    assert report["metrics"]["recall_at_3"] == 1.0


def test_gate_fails_closed_on_tiny_or_unreviewed_sample():
    rows = _records()
    rows[0]["label"]["review_ready"] = False
    report = _gate(rows)
    assert report["passed"] is False
    assert "Amostra insuficiente" in " ".join(report["failures"])


def test_gate_detects_retrieval_and_false_accept_regressions():
    rows = deepcopy(_records())
    rows[0]["prediction_snapshot"]["candidates"] = [{"catalog_product_id": "wrong", "rank": 1}]
    rows[2]["prediction_snapshot"]["predicted_verdict"] = "ATENDE"
    report = _gate(rows)
    assert report["passed"] is False
    assert any("Recall@1" in failure for failure in report["failures"])
    assert any("False accept rate" in failure for failure in report["failures"])


def test_gate_requires_unique_records_split_groups_and_snapshots():
    rows = deepcopy(_records())
    rows[1]["record_id"] = rows[0]["record_id"]
    rows[2]["split_group"] = None
    rows[3]["prediction_snapshot"]["candidates"] = []
    report = _gate(rows)
    assert report["passed"] is False
    assert len(report["failures"]) >= 3


def test_gate_rejects_invalid_thresholds():
    with pytest.raises(ValueError, match="entre 0 e 1"):
        _gate(_records(), min_recall_at_1=1.1)


def test_gate_requires_positive_and_negative_human_decisions():
    rows = _records()
    for row in rows:
        row["label"]["technical_verdict"] = "ATENDE"
    report = _gate(rows)
    assert report["passed"] is False
    assert any("NAO_ATENDE" in failure for failure in report["failures"])


def test_gate_does_not_trust_snapshot_rank_claims():
    rows = _records()
    rows[3]["prediction_snapshot"]["candidates"][1]["rank"] = 1
    report = _gate(rows)
    assert report["passed"] is False
    assert report["metrics"]["recall_at_1"] == 0.75
    assert any("Ranks fora de ordem" in failure for failure in report["failures"])
