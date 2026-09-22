"""Apply a quality gate to a versioned CRM evaluation-dataset export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.match_eval_metrics import DATASET_VERSION
from app.services.match_quality_gate import evaluate_match_quality_gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida qualidade de snapshots revisados do matching CRM.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--min-records", type=int, required=True)
    parser.add_argument("--min-recall-at-1", type=float, required=True)
    parser.add_argument("--min-recall-at-3", type=float, required=True)
    parser.add_argument("--min-decision-records", type=int, default=0)
    parser.add_argument("--max-false-accept-rate", type=float, default=1.0)
    args = parser.parse_args()

    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("dataset_version") != DATASET_VERSION:
        parser.error(f"Dataset deve ter dataset_version={DATASET_VERSION}.")
    records = payload.get("records")
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        parser.error("Dataset deve conter uma lista de registros.")

    report = evaluate_match_quality_gate(
        records,
        min_records=args.min_records,
        min_recall_at_1=args.min_recall_at_1,
        min_recall_at_3=args.min_recall_at_3,
        min_decision_records=args.min_decision_records,
        max_false_accept_rate=args.max_false_accept_rate,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
