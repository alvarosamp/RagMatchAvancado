from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session, joinedload

from app.auth.models import User
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
    if score >= 0.82:
        return "ATENDE"
    if score >= 0.46:
        return "VERIFICAR"
    return "NAO_ATENDE"


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0
