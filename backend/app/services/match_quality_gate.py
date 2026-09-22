"""Fail-closed quality checks for reviewed CRM matching snapshots."""

from __future__ import annotations

from typing import Any

from app.services.match_eval_metrics import evaluate_retrieval_records


REVIEWED_SOURCES = {"manual_confirmed", "match_confirmed"}


def evaluate_match_quality_gate(
    records: list[dict[str, Any]],
    *,
    min_records: int,
    min_recall_at_1: float,
    min_recall_at_3: float,
    min_decision_records: int = 0,
    max_false_accept_rate: float = 1.0,
) -> dict[str, Any]:
    """Evaluate only human-confirmed pairs; missing evidence fails the gate."""
    failures: list[str] = []
    if min_records < 1 or min_decision_records < 0:
        raise ValueError("Tamanho minimo de amostra invalido.")
    for name, value in (
        ("min_recall_at_1", min_recall_at_1),
        ("min_recall_at_3", min_recall_at_3),
        ("max_false_accept_rate", max_false_accept_rate),
    ):
        if not 0 <= value <= 1:
            raise ValueError(f"{name} deve estar entre 0 e 1.")

    reviewed = [
        row for row in records
        if (row.get("label") or {}).get("review_ready") is True
        and (row.get("label") or {}).get("source") in REVIEWED_SOURCES
    ]
    ids = [row.get("record_id") for row in reviewed]
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(str(value) for value in ids)):
        failures.append("Registros revisados precisam de record_id unico e nao vazio.")
    if any(not row.get("split_group") for row in reviewed):
        failures.append("Registros revisados precisam de split_group para evitar vazamento entre treino e teste.")

    normalized: list[dict[str, Any]] = []
    for row in reviewed:
        snapshot = row.get("prediction_snapshot") or {}
        candidates = snapshot.get("candidates") or []
        safe_candidates: list[dict[str, Any]] = []
        seen_candidate_ids: set[str] = set()
        if not isinstance(candidates, list):
            failures.append(f"Candidatos invalidos no registro {row.get('record_id')}.")
            candidates = []
        for position, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, dict):
                failures.append(f"Candidato invalido no registro {row.get('record_id')}.")
                continue
            candidate_id = candidate.get("catalog_product_id")
            if not isinstance(candidate_id, str) or not candidate_id or candidate_id in seen_candidate_ids:
                failures.append(f"Candidatos sem ID ou repetidos no registro {row.get('record_id')}.")
            if isinstance(candidate_id, str):
                seen_candidate_ids.add(candidate_id)
            if candidate.get("rank") != position:
                failures.append(f"Ranks fora de ordem no registro {row.get('record_id')}.")
            safe_candidates.append({**candidate, "rank": position})
        normalized.append({**row, "prediction_snapshot": {**snapshot, "candidates": safe_candidates}})

    metrics = evaluate_retrieval_records(normalized)
    evaluated = metrics["evaluated_records"]
    if evaluated < min_records:
        failures.append(f"Amostra insuficiente: {evaluated} < {min_records} registros avaliaveis.")
    if metrics["without_candidate_snapshot"]:
        failures.append(f"{metrics['without_candidate_snapshot']} registro(s) sem snapshot de candidatos.")
    if metrics["recall_at_1"] < min_recall_at_1:
        failures.append(f"Recall@1 abaixo do minimo: {metrics['recall_at_1']} < {min_recall_at_1}.")
    if metrics["recall_at_3"] < min_recall_at_3:
        failures.append(f"Recall@3 abaixo do minimo: {metrics['recall_at_3']} < {min_recall_at_3}.")
    if min_decision_records:
        decision_count = metrics["decision_evaluated_records"]
        if decision_count < min_decision_records:
            failures.append(f"Amostra de decisao insuficiente: {decision_count} < {min_decision_records}.")
        else:
            verdicts = {
                str((row.get("label") or {}).get("technical_verdict") or "").upper()
                for row in reviewed
            }
            if not {"ATENDE", "NAO_ATENDE"}.issubset(verdicts):
                failures.append("Amostra de decisao precisa incluir ATENDE e NAO_ATENDE humanos.")
            if metrics["false_accept_rate"] > max_false_accept_rate:
                failures.append(
                    f"False accept rate acima do maximo: {metrics['false_accept_rate']} > {max_false_accept_rate}."
                )

    return {
        "passed": not failures,
        "reviewed_records": len(reviewed),
        "metrics": metrics,
        "failures": failures,
    }
