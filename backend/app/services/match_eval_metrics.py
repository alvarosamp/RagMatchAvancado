"""Pure JSON-only metrics for CRM retrieval and technical decisions."""

from __future__ import annotations

import math
from typing import Any, Iterable

DATASET_VERSION = "match_eval_dataset_v1"


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def evaluate_retrieval_records(
    records: Iterable[dict[str, Any]],
    *,
    k_values: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, Any]:
    rows = list(records)
    labelled = [row for row in rows if (row.get("label") or {}).get("catalog_product_id")]
    evaluated = [row for row in labelled if (row.get("prediction_snapshot") or {}).get("candidates")]

    ranks: list[int | None] = []
    reciprocal_ranks: list[float] = []
    discounted_gains: list[float] = []
    for row in evaluated:
        label_id = (row.get("label") or {}).get("catalog_product_id")
        candidates = (row.get("prediction_snapshot") or {}).get("candidates") or []
        rank = next(
            (int(candidate["rank"]) if candidate.get("rank") is not None else position
             for position, candidate in enumerate(candidates, start=1)
             if candidate.get("catalog_product_id") == label_id),
            None,
        )
        ranks.append(rank)
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)
        discounted_gains.append(1.0 / math.log2(rank + 1) if rank else 0.0)

    denominator = len(evaluated)
    recall = {
        f"recall_at_{k}": _rate(sum(1 for rank in ranks if rank is not None and rank <= k), denominator)
        for k in k_values
    }
    return {
        "labelled_records": len(labelled),
        "evaluated_records": denominator,
        "without_candidate_snapshot": len(labelled) - denominator,
        "hidden_label_count": sum(1 for rank in ranks if rank is None),
        **recall,
        "mrr": _mean(reciprocal_ranks),
        "ndcg_at_all": _mean(discounted_gains),
        **_evaluate_decisions(labelled),
    }


def _evaluate_decisions(records: list[dict[str, Any]]) -> dict[str, Any]:
    labels = ("ATENDE", "VERIFICAR", "NAO_ATENDE")
    pairs: list[tuple[str, str]] = []
    for row in records:
        truth = str((row.get("label") or {}).get("technical_verdict") or "").upper()
        predicted = str((row.get("prediction_snapshot") or {}).get("predicted_verdict") or "").upper()
        if truth in labels and predicted in labels:
            pairs.append((truth, predicted))

    if not pairs:
        return {
            "decision_metrics_available": False,
            "decision_evaluated_records": 0,
            "decision_metrics_blocker": (
                "Registre no CRM um veredito humano ATENDE/VERIFICAR/NAO_ATENDE "
                "para o produto vinculado ao item."
            ),
        }

    matrix = {truth: {predicted: 0 for predicted in labels} for truth in labels}
    for truth, predicted in pairs:
        matrix[truth][predicted] += 1

    per_label: dict[str, dict[str, float]] = {}
    f1_values: list[float] = []
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[truth][label] for truth in labels if truth != label)
        fn = sum(matrix[label][predicted] for predicted in labels if predicted != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        f1_values.append(f1)
        per_label[label] = {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}

    predicted_atende = sum(1 for _, predicted in pairs if predicted == "ATENDE")
    false_accepts = sum(1 for truth, predicted in pairs if predicted == "ATENDE" and truth != "ATENDE")
    return {
        "decision_metrics_available": True,
        "decision_evaluated_records": len(pairs),
        "confusion_matrix": matrix,
        "per_label": per_label,
        "macro_f1": round(sum(f1_values) / len(f1_values), 4),
        "false_accept_count": false_accepts,
        "false_accept_rate": _rate(false_accepts, predicted_atende),
    }
