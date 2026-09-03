from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session, joinedload

from app.auth.models import User
from app.core.ml_config import get_ml_config
from app.crm.models import CrmNoticeProduct, CrmNoticeProductMatch


DATASET_VERSION = "match_eval_dataset_v1"
SCHEMA_VERSION = "1.0.0"


# This manifest makes the CRM-to-dataset contract explicit. Fields marked as
# labels must never be copied into model inputs; commercial fields are useful
# for bid/no-bid and pricing models, but are excluded from technical matching.
FIELD_MANIFEST: dict[str, dict[str, Any]] = {
    "notice.number": {"role": "metadata", "technical_match": False},
    "notice.title": {"role": "feature", "technical_match": True},
    "notice.modality": {"role": "context", "technical_match": False},
    "notice.organ": {"role": "context", "technical_match": False},
    "notice.portal": {"role": "context", "technical_match": False},
    "notice.outcome": {"role": "commercial_label", "technical_match": False},
    "notice.decision_recommendation": {"role": "commercial_prediction", "technical_match": False},
    "notice_product.description": {"role": "feature", "technical_match": True},
    "notice_product.product_code": {"role": "feature", "technical_match": True},
    "notice_product.category": {"role": "feature", "technical_match": True},
    "notice_product.technical_characteristics": {"role": "feature", "technical_match": True},
    "notice_product.bi_features": {"role": "feature", "technical_match": True},
    "notice_product.raw_payload": {"role": "source_evidence", "technical_match": True},
    "notice_product.brand_direction_exists": {"role": "feature", "technical_match": True},
    "notice_product.brand_direction_model": {"role": "feature", "technical_match": True},
    "notice_product.brand_direction_type": {"role": "feature", "technical_match": True},
    "notice_product.brand_direction_justification": {"role": "source_evidence", "technical_match": True},
    "notice_product.quantity": {"role": "context", "technical_match": False},
    "notice_product.unit": {"role": "context", "technical_match": False},
    "notice_product.reference_price": {"role": "commercial_feature", "technical_match": False},
    "notice_product.reference_total_price": {"role": "commercial_feature", "technical_match": False},
    "notice_product.cost": {"role": "commercial_feature", "technical_match": False},
    "notice_product.unit_price": {"role": "commercial_feature", "technical_match": False},
    "notice_product.selected_for_dispute": {"role": "commercial_label", "technical_match": False},
    "notice_product.catalog_product_id": {"role": "retrieval_label", "technical_match": False},
    "notice_product.catalog_match_source": {"role": "label_provenance", "technical_match": False},
    "notice_product.catalog_match_notes": {"role": "review_evidence", "technical_match": False},
    "notice_product.match_review_verdict": {"role": "decision_label", "technical_match": False},
    "notice_product.match_review_confidence": {"role": "label_quality", "technical_match": False},
    "notice_product.match_review_reason_codes": {"role": "review_evidence", "technical_match": False},
    "notice_product.match_review_evidence": {"role": "review_evidence", "technical_match": False},
    "catalog_product.category": {"role": "candidate_feature", "technical_match": True},
    "catalog_product.brand": {"role": "candidate_feature", "technical_match": True},
    "catalog_product.model": {"role": "candidate_feature", "technical_match": True},
    "catalog_product.manufacturer_part_number": {"role": "candidate_feature", "technical_match": True},
    "catalog_product.sku": {"role": "candidate_feature", "technical_match": True},
    "catalog_product.specification": {"role": "candidate_feature", "technical_match": True},
    "catalog_product.keywords": {"role": "candidate_feature", "technical_match": True},
    "catalog_product.equivalent_skus": {"role": "candidate_feature", "technical_match": True},
}


def build_match_evaluation_dataset(
    db: Session,
    current_user: User,
    *,
    notice_id: str | None = None,
    source: str | None = None,
    limit: int = 500,
    include_unmarked: bool = False,
) -> dict[str, Any]:
    query = (
        db.query(CrmNoticeProduct)
        .options(
            joinedload(CrmNoticeProduct.notice),
            joinedload(CrmNoticeProduct.catalog_product),
            joinedload(CrmNoticeProduct.product_matches).joinedload(CrmNoticeProductMatch.catalog_product),
        )
        .filter(
            CrmNoticeProduct.tenant_id == current_user.tenant_id,
            CrmNoticeProduct.catalog_product_id.isnot(None),
        )
    )
    if not include_unmarked:
        query = query.filter(CrmNoticeProduct.catalog_match_source.isnot(None))
    if notice_id:
        query = query.filter(CrmNoticeProduct.notice_id == notice_id)
    if source:
        query = query.filter(CrmNoticeProduct.catalog_match_source == source)

    products = query.order_by(CrmNoticeProduct.created_at.desc()).limit(limit).all()
    records = [build_match_evaluation_record(product) for product in products]
    return build_dataset_envelope(records, include_unmarked=include_unmarked, limit=limit)


def build_attached_products_ai_opportunity_report(
    db: Session,
    current_user: User,
    *,
    notice_id: str | None = None,
    source: str | None = None,
    include_unmarked: bool = False,
    limit: int = 1000,
) -> dict[str, Any]:
    query = (
        db.query(CrmNoticeProduct)
        .options(
            joinedload(CrmNoticeProduct.notice),
            joinedload(CrmNoticeProduct.catalog_product),
            joinedload(CrmNoticeProduct.item_result),
        )
        .filter(
            CrmNoticeProduct.tenant_id == current_user.tenant_id,
            CrmNoticeProduct.catalog_product_id.isnot(None),
        )
    )
    if not include_unmarked:
        query = query.filter(CrmNoticeProduct.catalog_match_source.isnot(None))
    if notice_id:
        query = query.filter(CrmNoticeProduct.notice_id == notice_id)
    if source:
        query = query.filter(CrmNoticeProduct.catalog_match_source == source)

    products = query.order_by(CrmNoticeProduct.catalog_match_confirmed_at.desc().nullslast()).limit(limit).all()
    records = [_attached_product_ai_record(product) for product in products]
    return analyze_attached_product_records(records, include_unmarked=include_unmarked, limit=limit)


def analyze_attached_product_records(
    records: list[dict[str, Any]],
    *,
    include_unmarked: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    source_counts = Counter(str((row.get("attachment") or {}).get("source") or "unmarked") for row in records)
    ready_pairs = sum(1 for row in records if (row.get("attachment") or {}).get("source") in {"manual_confirmed", "match_confirmed"})
    manual_kit = sum(1 for row in records if (row.get("attachment") or {}).get("source") == "manual_kit")
    reviewed = sum(1 for row in records if (row.get("technical_label") or {}).get("verdict"))
    field_coverage = _field_coverage(records, _AI_OPPORTUNITY_FIELDS)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "attached_items": len(records),
            "ready_retrieval_pairs": ready_pairs,
            "manual_kit_items": manual_kit,
            "technical_reviewed_items": reviewed,
            "include_unmarked": include_unmarked,
            "limit": limit,
            "source_counts": dict(source_counts),
        },
        "field_coverage": field_coverage,
        "recommended_ai_uses": _attached_ai_recommendations(records, field_coverage),
        "leakage_boundaries": [
            {
                "fields": ["attachment.catalog_product_id", "attachment.source", "technical_label.*"],
                "use": "labels/avaliacao",
                "technical_match_input": False,
            },
            {
                "fields": ["commercial_context.*"],
                "use": "bid_no_bid, pricing, chance de ganho e priorizacao comercial",
                "technical_match_input": False,
            },
            {
                "fields": ["technical_input.*", "attached_catalog.*"],
                "use": "matching tecnico, retrieval, reranking e explicabilidade",
                "technical_match_input": True,
            },
        ],
        "next_actions": _attached_ai_next_actions(records, field_coverage),
        "sample_records": records[:25],
    }


def build_dataset_envelope(
    records: list[dict[str, Any]],
    *,
    include_unmarked: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    sources = Counter(str((record.get("label") or {}).get("source") or "unmarked") for record in records)
    review_ready = sum(1 for record in records if (record.get("label") or {}).get("review_ready"))
    return {
        "dataset_version": DATASET_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task": "catalog_product_retrieval",
        "summary": {
            "records": len(records),
            "review_ready_records": review_ready,
            "review_required_records": len(records) - review_ready,
            "label_sources": dict(sources),
            "include_unmarked": include_unmarked,
            "limit": limit,
        },
        "field_manifest": FIELD_MANIFEST,
        "evaluation": evaluate_retrieval_records(records),
        "limitations": [
            "A selecao do produto correto avalia retrieval/ranking, mas nao rotula sozinha ATENDE/VERIFICAR/NAO_ATENDE.",
            "Sugestoes rejeitadas automaticamente apos uma confirmacao nao devem ser tratadas como negativos fortes.",
            "Resultado comercial, preco e decisao de disputar ficam fora das features do matching tecnico.",
            "Para reduzir selection bias, o gold dataset deve incluir revisao ocasional de produtos fora do top-K atual.",
        ],
        "records": records,
    }


_AI_OPPORTUNITY_FIELDS: dict[str, str] = {
    "technical_input.notice.title": "feature",
    "technical_input.item.description": "feature",
    "technical_input.item.category": "feature",
    "technical_input.item.technical_characteristics": "feature",
    "technical_input.item.brand_direction.exists": "feature",
    "technical_input.item.brand_direction.model": "feature",
    "technical_input.item.brand_direction.type": "feature",
    "technical_input.item.brand_direction.justification": "source_evidence",
    "technical_input.item.bi_features": "structured_feature",
    "technical_input.item.raw_payload": "source_evidence",
    "attached_catalog.name": "candidate_feature",
    "attached_catalog.category": "candidate_feature",
    "attached_catalog.brand": "candidate_feature",
    "attached_catalog.model": "candidate_feature",
    "attached_catalog.manufacturer_part_number": "candidate_feature",
    "attached_catalog.sku": "candidate_feature",
    "attached_catalog.specification": "candidate_feature",
    "attached_catalog.keywords": "candidate_feature",
    "attached_catalog.equivalent_skus": "candidate_feature",
    "attached_catalog.datasheet_url": "candidate_evidence",
    "commercial_context.item.quantity": "commercial_context",
    "commercial_context.item.reference_price": "commercial_context",
    "commercial_context.item.unit_price": "commercial_context",
    "commercial_context.notice.outcome": "commercial_label",
    "commercial_context.item_result.winner_type": "commercial_label",
    "technical_label.verdict": "decision_label",
}


def build_match_calibration_report(
    records: Iterable[dict[str, Any]],
    *,
    embedding_weights: Iterable[float] = (0.0, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0),
    atende_thresholds: Iterable[float] = (0.76, 0.8, 0.82, 0.85, 0.88),
    verificar_thresholds: Iterable[float] = (0.4, 0.46, 0.5, 0.55, 0.6),
) -> dict[str, Any]:
    rows = list(records)
    retrieval = _calibrate_retrieval_weights(rows, embedding_weights)
    decisions = _calibrate_decision_thresholds(rows, atende_thresholds, verificar_thresholds)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records": len(rows),
        "retrieval": retrieval,
        "decision_thresholds": decisions,
        "recommended": {
            "embedding_weight": (retrieval.get("best") or {}).get("embedding_weight"),
            "threshold_atende": (decisions.get("best") or {}).get("threshold_atende"),
            "threshold_verificar": (decisions.get("best") or {}).get("threshold_verificar"),
        },
        "notes": [
            "A calibracao de peso reordena candidatos usando scores lexical e semantico salvos no snapshot.",
            "A calibracao de decisao usa apenas registros com veredito humano tecnico.",
            "Antes de fixar thresholds, confira manualmente os falsos ATENDE em amostras reais.",
        ],
    }


def build_match_evaluation_record(product: CrmNoticeProduct) -> dict[str, Any]:
    notice = product.notice
    matches = sorted(product.product_matches or [], key=lambda item: item.match_rank or 999999)
    label_product_id = product.catalog_product_id
    label_match = next((match for match in matches if match.catalog_product_id == label_product_id), None)
    source = product.catalog_match_source

    return {
        "record_id": product.id,
        # All items from the same notice must stay in the same train/test split.
        "split_group": product.notice_id,
        "technical_input": {
            "notice": {
                "title": getattr(notice, "title", None),
            },
            "item": {
                "item_number": product.item_number,
                "lot": product.lot,
                "product_code": product.product_code,
                "description": product.description,
                "category": product.category,
                "technical_characteristics": product.technical_characteristics,
                "warranty": product.warranty,
                "delivery_deadline": product.delivery_deadline,
                "brand_direction": {
                    "exists": product.brand_direction_exists,
                    "model": product.brand_direction_model,
                    "type": product.brand_direction_type,
                    "justification": product.brand_direction_justification,
                },
                "bi_features": product.bi_features,
                "raw_payload": product.raw_payload,
            },
        },
        "commercial_context": {
            "notice": {
                "number": getattr(notice, "number", None),
                "modality": getattr(notice, "modality", None),
                "organ": getattr(getattr(notice, "organ", None), "name", None),
                "portal": getattr(getattr(notice, "portal", None), "name", None),
                "outcome": _enum_value(getattr(notice, "outcome", None)),
                "decision_recommendation": getattr(notice, "decision_recommendation", None),
            },
            "item": {
                "quantity": product.quantity,
                "unit": product.unit,
                "reference_price": product.reference_price,
                "reference_total_price": product.reference_total_price,
                "cost": product.cost,
                "unit_price": product.unit_price,
                "selected_for_dispute": product.selected_for_dispute,
            },
        },
        "label": {
            "task": "correct_catalog_product",
            "catalog_product_id": label_product_id,
            "catalog_product": _serialize_catalog_product(product.catalog_product),
            "source": source,
            "confirmed_at": product.catalog_match_confirmed_at.isoformat() if product.catalog_match_confirmed_at else None,
            "confirmed_by": product.catalog_match_confirmed_by,
            "notes": product.catalog_match_notes,
            "review_ready": source in {"manual_confirmed", "match_confirmed"},
            "technical_verdict": getattr(product, "match_review_verdict", None),
            "technical_confidence": getattr(product, "match_review_confidence", None),
            "technical_reason_codes": getattr(product, "match_review_reason_codes", None),
            "technical_evidence": getattr(product, "match_review_evidence", None),
            "technical_notes": getattr(product, "match_review_notes", None),
            "technical_reviewed_by": getattr(product, "match_reviewed_by", None),
            "technical_reviewed_at": (
                product.match_reviewed_at.isoformat()
                if getattr(product, "match_reviewed_at", None)
                else None
            ),
        },
        "prediction_snapshot": {
            "model_version": product.catalog_match_model_version,
            "label_rank": label_match.match_rank if label_match else None,
            "label_score": label_match.overall_score if label_match else None,
            "predicted_verdict": _score_to_verdict(label_match.overall_score if label_match else None),
            "candidates": [_serialize_candidate(match) for match in matches],
        },
    }


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
        rank = _find_rank(candidates, label_id)
        ranks.append(rank)
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)
        discounted_gains.append(1.0 / math.log2(rank + 1) if rank else 0.0)

    denominator = len(evaluated)
    recall = {
        f"recall_at_{k}": _rate(sum(1 for rank in ranks if rank is not None and rank <= k), denominator)
        for k in k_values
    }
    decision = _evaluate_decisions(labelled)
    return {
        "labelled_records": len(labelled),
        "evaluated_records": denominator,
        "without_candidate_snapshot": len(labelled) - denominator,
        "hidden_label_count": sum(1 for rank in ranks if rank is None),
        **recall,
        "mrr": _mean(reciprocal_ranks),
        "ndcg_at_all": _mean(discounted_gains),
        **decision,
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

    matrix = {
        truth: {predicted: 0 for predicted in labels}
        for truth in labels
    }
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
        per_label[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

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


def _calibrate_retrieval_weights(
    records: list[dict[str, Any]],
    weights: Iterable[float],
) -> dict[str, Any]:
    labelled = [row for row in records if (row.get("label") or {}).get("catalog_product_id")]
    evaluated = [row for row in labelled if (row.get("prediction_snapshot") or {}).get("candidates")]
    runs: list[dict[str, Any]] = []
    for weight in weights:
        bounded_weight = max(0.0, min(1.0, float(weight)))
        reranked_records = []
        for row in evaluated:
            snapshot = row.get("prediction_snapshot") or {}
            candidates = [
                {**candidate, "scores": _reweighted_scores(candidate.get("scores") or {}, bounded_weight)}
                for candidate in snapshot.get("candidates") or []
            ]
            candidates = sorted(candidates, key=lambda item: (item.get("scores") or {}).get("overall") or 0.0, reverse=True)
            candidates = [{**candidate, "rank": index} for index, candidate in enumerate(candidates, start=1)]
            reranked_records.append({**row, "prediction_snapshot": {**snapshot, "candidates": candidates}})
        metrics = evaluate_retrieval_records(reranked_records)
        runs.append({
            "embedding_weight": round(bounded_weight, 4),
            "lexical_weight": round(1.0 - bounded_weight, 4),
            "evaluated_records": metrics["evaluated_records"],
            "recall_at_1": metrics["recall_at_1"],
            "recall_at_3": metrics["recall_at_3"],
            "recall_at_5": metrics["recall_at_5"],
            "mrr": metrics["mrr"],
            "hidden_label_count": metrics["hidden_label_count"],
        })

    best = max(
        runs,
        key=lambda item: (
            item["recall_at_1"],
            item["mrr"],
            item["recall_at_3"],
            -item["hidden_label_count"],
        ),
        default=None,
    )
    return {
        "evaluated_records": len(evaluated),
        "best": best,
        "candidates": runs,
    }


def _reweighted_scores(scores: dict[str, Any], embedding_weight: float) -> dict[str, Any]:
    lexical = _score_value(scores.get("lexical"))
    semantic = _score_value(scores.get("semantic"))
    if semantic is None:
        overall = lexical
    else:
        overall = (lexical * (1.0 - embedding_weight)) + (semantic * embedding_weight)
    return {
        **scores,
        "overall": round(max(0.0, min(1.0, overall)), 4),
        "calibrated_embedding_weight": round(embedding_weight, 4),
    }


def _calibrate_decision_thresholds(
    records: list[dict[str, Any]],
    atende_thresholds: Iterable[float],
    verificar_thresholds: Iterable[float],
) -> dict[str, Any]:
    labelled_scores = []
    for row in records:
        truth = str((row.get("label") or {}).get("technical_verdict") or "").upper()
        score = _score_value((row.get("prediction_snapshot") or {}).get("label_score"))
        if truth in {"ATENDE", "VERIFICAR", "NAO_ATENDE"} and score is not None:
            labelled_scores.append((truth, score))

    runs: list[dict[str, Any]] = []
    for atende in atende_thresholds:
        threshold_atende = float(atende)
        for verificar in verificar_thresholds:
            threshold_verificar = float(verificar)
            if threshold_verificar >= threshold_atende:
                continue
            pairs = [
                (truth, _score_to_verdict_with_thresholds(score, threshold_atende, threshold_verificar))
                for truth, score in labelled_scores
            ]
            metrics = _decision_metrics_from_pairs(pairs)
            runs.append({
                "threshold_atende": round(threshold_atende, 4),
                "threshold_verificar": round(threshold_verificar, 4),
                **metrics,
            })

    best = max(
        runs,
        key=lambda item: (
            item["macro_f1"],
            -item["false_accept_rate"],
            item["accuracy"],
        ),
        default=None,
    )
    return {
        "evaluated_records": len(labelled_scores),
        "best": best,
        "candidates": runs,
    }


def _decision_metrics_from_pairs(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    labels = ("ATENDE", "VERIFICAR", "NAO_ATENDE")
    if not pairs:
        return {
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "false_accept_count": 0,
            "false_accept_rate": 0.0,
        }
    matrix = {truth: {predicted: 0 for predicted in labels} for truth in labels}
    for truth, predicted in pairs:
        matrix[truth][predicted] += 1

    f1_values = []
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[truth][label] for truth in labels if truth != label)
        fn = sum(matrix[label][predicted] for predicted in labels if predicted != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1_values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)

    correct = sum(1 for truth, predicted in pairs if truth == predicted)
    predicted_atende = sum(1 for _, predicted in pairs if predicted == "ATENDE")
    false_accepts = sum(1 for truth, predicted in pairs if predicted == "ATENDE" and truth != "ATENDE")
    return {
        "accuracy": _rate(correct, len(pairs)),
        "macro_f1": round(sum(f1_values) / len(f1_values), 4),
        "false_accept_count": false_accepts,
        "false_accept_rate": _rate(false_accepts, predicted_atende),
    }


def _attached_product_ai_record(product: CrmNoticeProduct) -> dict[str, Any]:
    notice = product.notice
    item_result = getattr(product, "item_result", None)
    return {
        "record_id": product.id,
        "split_group": product.notice_id,
        "technical_input": {
            "notice": {"title": getattr(notice, "title", None)},
            "item": {
                "item_number": product.item_number,
                "lot": product.lot,
                "product_code": product.product_code,
                "description": product.description,
                "category": product.category,
                "technical_characteristics": product.technical_characteristics,
                "warranty": product.warranty,
                "delivery_deadline": product.delivery_deadline,
                "brand_direction": {
                    "exists": product.brand_direction_exists,
                    "model": product.brand_direction_model,
                    "type": product.brand_direction_type,
                    "justification": product.brand_direction_justification,
                },
                "bi_features": product.bi_features,
                "raw_payload": product.raw_payload,
            },
        },
        "attached_catalog": _serialize_catalog_product_with_evidence(product.catalog_product),
        "attachment": {
            "catalog_product_id": product.catalog_product_id,
            "source": product.catalog_match_source,
            "confirmed_at": product.catalog_match_confirmed_at.isoformat() if product.catalog_match_confirmed_at else None,
            "confirmed_by": product.catalog_match_confirmed_by,
            "model_version": product.catalog_match_model_version,
            "notes": product.catalog_match_notes,
            "lpu_version": product.catalog_lpu_version,
        },
        "technical_label": {
            "verdict": getattr(product, "match_review_verdict", None),
            "confidence": getattr(product, "match_review_confidence", None),
            "reason_codes": getattr(product, "match_review_reason_codes", None),
            "reviewed_at": product.match_reviewed_at.isoformat() if getattr(product, "match_reviewed_at", None) else None,
        },
        "commercial_context": {
            "notice": {
                "number": getattr(notice, "number", None),
                "modality": getattr(notice, "modality", None),
                "organ": getattr(getattr(notice, "organ", None), "name", None),
                "portal": getattr(getattr(notice, "portal", None), "name", None),
                "outcome": _enum_value(getattr(notice, "outcome", None)),
                "decision_recommendation": getattr(notice, "decision_recommendation", None),
                "decision_score": getattr(notice, "decision_score", None),
            },
            "item": {
                "quantity": product.quantity,
                "unit": product.unit,
                "reference_price": product.reference_price,
                "reference_total_price": product.reference_total_price,
                "cost": product.cost,
                "unit_price": product.unit_price,
                "selected_for_dispute": product.selected_for_dispute,
            },
            "item_result": {
                "winner_type": _enum_value(getattr(item_result, "winner_type", None)),
                "competitor_name": getattr(item_result, "competitor_name", None),
                "competitor_product": getattr(item_result, "competitor_product", None),
                "winning_price": getattr(item_result, "winning_price", None),
                "winning_quantity": getattr(item_result, "winning_quantity", None),
            } if item_result else None,
        },
    }


def _field_coverage(records: list[dict[str, Any]], fields: dict[str, str]) -> list[dict[str, Any]]:
    total = len(records)
    coverage = []
    for path, role in fields.items():
        present = sum(1 for row in records if _has_value(_path_get(row, path)))
        coverage.append({
            "field": path,
            "role": role,
            "present": present,
            "coverage": _rate(present, total),
            "technical_match_input": role in {"feature", "structured_feature", "source_evidence", "candidate_feature", "candidate_evidence"},
        })
    return sorted(coverage, key=lambda item: (item["coverage"], item["field"]), reverse=True)


def _attached_ai_recommendations(records: list[dict[str, Any]], field_coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(records)
    if not total:
        return [{
            "area": "dados",
            "priority": "high",
            "recommendation": "Registrar itens vinculados ao catalogo para criar pares positivos de treino e avaliacao.",
        }]

    coverage = {item["field"]: item["coverage"] for item in field_coverage}
    source_counts = Counter(str((row.get("attachment") or {}).get("source") or "unmarked") for row in records)
    reviewed = sum(1 for row in records if (row.get("technical_label") or {}).get("verdict"))
    recommendations = [
        {
            "area": "retrieval",
            "priority": "high",
            "recommendation": "Usar anexos manuais confirmados como pares positivos edital-produto para calibrar ranking hibrido.",
            "evidence": {
                "confirmed_pairs": source_counts.get("manual_confirmed", 0) + source_counts.get("match_confirmed", 0),
                "total": total,
            },
        }
    ]
    if coverage.get("technical_input.item.bi_features", 0.0) >= 0.25:
        recommendations.append({
            "area": "extracao",
            "priority": "high",
            "recommendation": "Usar bi_features como features estruturadas para matching por familia tecnica e para explicar conflitos.",
            "evidence": {"coverage": coverage["technical_input.item.bi_features"]},
        })
    if coverage.get("technical_input.item.raw_payload", 0.0) >= 0.25:
        recommendations.append({
            "area": "data_quality",
            "priority": "medium",
            "recommendation": "Comparar raw_payload com campos normalizados para medir perda de informacao na importacao do CRM.",
            "evidence": {"coverage": coverage["technical_input.item.raw_payload"]},
        })
    if coverage.get("attached_catalog.datasheet_url", 0.0) >= 0.2:
        recommendations.append({
            "area": "rag",
            "priority": "medium",
            "recommendation": "Usar datasheets do catalogo como evidencia RAG para um juiz tecnico apenas nos top candidatos.",
            "evidence": {"coverage": coverage["attached_catalog.datasheet_url"]},
        })
    if reviewed:
        recommendations.append({
            "area": "decision_model",
            "priority": "high",
            "recommendation": "Usar vereditos humanos para calibrar ATENDE/VERIFICAR/NAO_ATENDE e reduzir falsos ATENDE.",
            "evidence": {"reviewed_items": reviewed, "coverage": _rate(reviewed, total)},
        })
    if source_counts.get("manual_kit", 0):
        recommendations.append({
            "area": "kit_decomposition",
            "priority": "medium",
            "recommendation": "Separar anexos manual_kit como dataset de composicao de kits, nao como positivo simples de um produto unico.",
            "evidence": {"manual_kit_items": source_counts["manual_kit"]},
        })
    if coverage.get("commercial_context.notice.outcome", 0.0) >= 0.25:
        recommendations.append({
            "area": "commercial_ai",
            "priority": "medium",
            "recommendation": "Treinar modelos separados para bid/no-bid e chance de ganho usando contexto comercial, fora do matching tecnico.",
            "evidence": {"outcome_coverage": coverage["commercial_context.notice.outcome"]},
        })
    return recommendations


def _attached_ai_next_actions(records: list[dict[str, Any]], field_coverage: list[dict[str, Any]]) -> list[str]:
    if not records:
        return [
            "Importar ou confirmar manualmente vinculos item-produto no CRM.",
            "Rodar novamente este relatorio apos haver anexos manuais.",
        ]
    coverage = {item["field"]: item["coverage"] for item in field_coverage}
    actions = [
        "Exportar os anexos confirmados como pares positivos de retrieval.",
        "Revisar uma amostra de top candidatos rejeitados para criar negativos confiaveis.",
        "Rodar /api/crm/matches/calibration-report depois de atualizar os matches dos itens rotulados.",
    ]
    if coverage.get("technical_label.verdict", 0.0) < 0.2:
        actions.append("Priorizar revisao humana ATENDE/VERIFICAR/NAO_ATENDE em pelo menos 50-100 itens.")
    if coverage.get("attached_catalog.specification", 0.0) < 0.5:
        actions.append("Completar especificacoes tecnicas do catalogo nos produtos mais usados em anexos manuais.")
    if coverage.get("technical_input.item.bi_features", 0.0) < 0.3:
        actions.append("Aumentar extracao de campos estruturados dos itens para melhorar matching por atributos.")
    return actions


def _serialize_catalog_product_with_evidence(product: Any | None) -> dict[str, Any] | None:
    if product is None:
        return None
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "brand": product.brand,
        "model": product.model,
        "manufacturer_part_number": product.manufacturer_part_number,
        "sku": product.sku,
        "specification": product.specification,
        "keywords": product.keywords,
        "equivalent_skus": product.equivalent_skus,
        "unit": product.unit,
        "datasheet_url": getattr(product, "datasheet_url", None),
        "certificate_url": getattr(product, "certificate_url", None),
    }


def _path_get(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _score_to_verdict_with_thresholds(score: float, threshold_atende: float, threshold_verificar: float) -> str:
    if score >= threshold_atende:
        return "ATENDE"
    if score >= threshold_verificar:
        return "VERIFICAR"
    return "NAO_ATENDE"


def _serialize_candidate(match: CrmNoticeProductMatch) -> dict[str, Any]:
    return {
        "catalog_product_id": match.catalog_product_id,
        "catalog_product": _serialize_catalog_product(match.catalog_product),
        "rank": match.match_rank,
        "source_method": match.source_method,
        "status": _enum_value(match.status),
        "level": _enum_value(match.match_level),
        "scores": {
            "lexical": match.lexical_score,
            "semantic": match.semantic_score,
            "llm": match.llm_score,
            "overall": match.overall_score,
        },
        "rationale": match.rationale,
        "matched_features": match.matched_features,
        "conflicts": match.conflicts,
    }


def _serialize_catalog_product(product: Any | None) -> dict[str, Any] | None:
    if product is None:
        return None
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "brand": product.brand,
        "model": product.model,
        "manufacturer_part_number": product.manufacturer_part_number,
        "sku": product.sku,
        "specification": product.specification,
        "keywords": product.keywords,
        "equivalent_skus": product.equivalent_skus,
        "unit": product.unit,
    }


def _find_rank(candidates: list[dict[str, Any]], label_id: str) -> int | None:
    for position, candidate in enumerate(candidates, start=1):
        if candidate.get("catalog_product_id") == label_id:
            raw_rank = candidate.get("rank")
            return int(raw_rank) if raw_rank is not None else position
    return None


def _score_to_verdict(score: float | None) -> str | None:
    if score is None:
        return None
    cfg = get_ml_config()
    if score >= cfg.threshold_atende:
        return "ATENDE"
    if score >= cfg.threshold_verificar:
        return "VERIFICAR"
    return "NAO_ATENDE"


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _score_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None
