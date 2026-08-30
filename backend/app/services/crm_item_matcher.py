from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.auth.models import User
from app.core.features import AI_FEATURES_ENABLED, CRM_MATCH_USE_LLM
from app.crm.models import (
    CrmCatalogProduct,
    CrmNotice,
    CrmNoticeHistory,
    CrmNoticeProduct,
    CrmNoticeProductMatch,
    CrmNoticeProductMatchLevel,
    CrmNoticeProductMatchStatus,
)
from app.pipeline.embedder import embed_texts_batch
from app.services.crm_match_scoring import (
    MatchScore,
    build_match_summary,
    combine_scores,
    cosine_similarity,
    _has_hard_category_conflict,
    lexical_similarity,
    normalize_text,
    technical_compatibility_score,
    try_llm_rerank,
)

PRESELECT_LIMIT = 12
SUGGESTIONS_PER_ITEM = 10
MIN_SUGGESTION_SCORE = 0.32


def _auto_pricing_allowed(product: CrmNoticeProduct) -> bool:
    notice = getattr(product, "notice", None)
    return not bool(getattr(notice, "post_auction_phase", None))


def _remember_lpu_version(product: CrmNoticeProduct, catalog: CrmCatalogProduct) -> None:
    product.catalog_lpu_version = getattr(catalog, "lpu_version", None)


def run_notice_item_match(
    db: Session,
    current_user: User,
    notice_id: str,
    *,
    use_llm: bool = True,
    notice_product_id: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    use_llm = bool(use_llm and AI_FEATURES_ENABLED and CRM_MATCH_USE_LLM)
    notice = _load_notice(db, current_user, notice_id)
    catalog_products = (
        db.query(CrmCatalogProduct)
        .filter(
            CrmCatalogProduct.tenant_id == current_user.tenant_id,
            CrmCatalogProduct.is_active.is_(True),
        )
        .all()
    )

    embedding_cache: dict[str, list[float]] = {}
    best_scores: list[dict[str, Any]] = []
    reusable_matches = _build_reusable_match_index(db, current_user)
    notice_products = notice.notice_products
    if notice_product_id:
        notice_products = [p for p in notice_products if p.id == notice_product_id]
        if not notice_products:
            raise LookupError("Item do edital nao encontrado para rodar match.")

    catalog_products_filtered = catalog_products
    if category:
        wanted = normalize_text(category)
        catalog_products_filtered = [
            p for p in catalog_products if normalize_text(getattr(p, "category", None)) == wanted
        ]
        if not catalog_products_filtered:
            raise ValueError("Nenhum produto ativo encontrado no catalogo para a categoria selecionada.")

    if notice_product_id:
        db.query(CrmNoticeProductMatch).filter(
            CrmNoticeProductMatch.tenant_id == current_user.tenant_id,
            CrmNoticeProductMatch.notice_id == notice_id,
            CrmNoticeProductMatch.notice_product_id == notice_product_id,
        ).delete(synchronize_session=False)
        db.flush()
    else:
        db.query(CrmNoticeProductMatch).filter(
            CrmNoticeProductMatch.tenant_id == current_user.tenant_id,
            CrmNoticeProductMatch.notice_id == notice_id,
        ).delete(synchronize_session=False)
        db.flush()

    for product in notice_products:
        reused_catalog = _find_reusable_catalog_product(product, reusable_matches)
        if reused_catalog is not None:
            reused_match = CrmNoticeProductMatch(
                tenant_id=current_user.tenant_id,
                notice_id=notice.id,
                notice_product_id=product.id,
                catalog_product_id=reused_catalog.id,
                match_rank=1,
                source_method="reuse_confirmed",
                status=CrmNoticeProductMatchStatus.CONFIRMED,
                match_level=CrmNoticeProductMatchLevel.STRONG,
                lexical_score=1.0,
                semantic_score=1.0,
                llm_score=None,
                overall_score=1.0,
                rationale="Reaproveitado de item identico com match previamente confirmado.",
                matched_features=["descricao normalizada identica", "historico confirmado"],
                conflicts=None,
                created_by=current_user.id,
            )
            product.catalog_product_id = reused_catalog.id
            _remember_lpu_version(product, reused_catalog)
            if _auto_pricing_allowed(product) and product.unit_price is None and reused_catalog.min_price is not None:
                product.unit_price = float(reused_catalog.min_price)
            if _auto_pricing_allowed(product) and product.cost is None and reused_catalog.cost is not None:
                product.cost = float(reused_catalog.cost)
            db.add(reused_match)
            best_scores.append({
                "notice_product_id": product.id,
                "best_score": 1.0,
                "reference_value": _reference_value(product),
            })
            continue

        ranked = _rank_candidates(product, catalog_products_filtered, embedding_cache=embedding_cache, use_llm=use_llm)
        matches: list[CrmNoticeProductMatch] = []
        for rank, candidate in enumerate(ranked[:SUGGESTIONS_PER_ITEM], start=1):
            score: MatchScore = candidate["score"]
            if score.overall_score < MIN_SUGGESTION_SCORE:
                continue
            match = CrmNoticeProductMatch(
                tenant_id=current_user.tenant_id,
                notice_id=notice.id,
                notice_product_id=product.id,
                catalog_product_id=candidate["catalog"].id,
                match_rank=rank,
                source_method=score.source_method,
                status=CrmNoticeProductMatchStatus.CONFIRMED if product.catalog_product_id == candidate["catalog"].id else CrmNoticeProductMatchStatus.SUGGESTED,
                match_level=_match_level_enum(score.level),
                lexical_score=score.lexical_score,
                semantic_score=score.semantic_score,
                llm_score=score.llm_score,
                overall_score=score.overall_score,
                rationale=score.rationale,
                matched_features=list(score.matched_features) if score.matched_features else None,
                conflicts=list(score.conflicts) if score.conflicts else None,
                created_by=current_user.id,
            )
            db.add(match)
            matches.append(match)

        best_match_score = matches[0].overall_score if matches else 0.0
        best_scores.append({
            "notice_product_id": product.id,
            "best_score": best_match_score,
            "reference_value": _reference_value(product),
        })

    db.flush()
    summary = build_match_summary(best_scores, total_reference_value=sum(item["reference_value"] for item in best_scores))
    db.add(
        CrmNoticeHistory(
            tenant_id=current_user.tenant_id,
            notice_id=notice.id,
            user_id=current_user.id,
            action="Match catalogo x edital executado",
            details=summary,
        )
    )
    db.commit()
    return get_notice_item_match_payload(db, current_user, notice_id)


def get_notice_item_match_payload(db: Session, current_user: User, notice_id: str) -> dict[str, Any]:
    notice = _load_notice(db, current_user, notice_id)
    matches = (
        db.query(CrmNoticeProductMatch)
        .options(joinedload(CrmNoticeProductMatch.catalog_product), joinedload(CrmNoticeProductMatch.notice_product))
        .filter(
            CrmNoticeProductMatch.tenant_id == current_user.tenant_id,
            CrmNoticeProductMatch.notice_id == notice_id,
        )
        .order_by(CrmNoticeProductMatch.notice_product_id.asc(), CrmNoticeProductMatch.match_rank.asc())
        .all()
    )

    grouped: dict[str, list[CrmNoticeProductMatch]] = defaultdict(list)
    for match in matches:
        grouped[match.notice_product_id].append(match)

    item_payloads: list[dict[str, Any]] = []
    best_scores: list[dict[str, Any]] = []
    for product in notice.notice_products:
        product_matches = grouped.get(product.id, [])
        best_score = product_matches[0].overall_score if product_matches else 0.0
        reference_value = _reference_value(product)
        best_scores.append({
            "notice_product_id": product.id,
            "best_score": best_score,
            "reference_value": reference_value,
        })
        item_payloads.append({
            "notice_product": _serialize_notice_product(product),
            "current_catalog_product_id": product.catalog_product_id,
            "best_match": _serialize_match(product_matches[0]) if product_matches else None,
            "matches": [_serialize_match(match) for match in product_matches],
        })

    summary = build_match_summary(best_scores, total_reference_value=sum(item["reference_value"] for item in best_scores))
    if not matches:
        summary["label"] = "Sem match rodado"
    return {
        "summary": summary,
        "items": item_payloads,
    }


def confirm_notice_item_match(db: Session, current_user: User, match_id: str) -> dict[str, Any]:
    match = _load_match(db, current_user, match_id)
    product = match.notice_product
    catalog = match.catalog_product

    product.catalog_product_id = catalog.id
    product.catalog_match_source = "match_confirmed"
    product.catalog_match_confirmed_by = current_user.id
    product.catalog_match_confirmed_at = datetime.utcnow()
    product.catalog_match_model_version = match.source_method
    product.catalog_match_notes = f"Confirmado a partir da sugestao rank #{match.match_rank}."
    _remember_lpu_version(product, catalog)
    if _auto_pricing_allowed(product) and product.unit_price is None and catalog.min_price is not None:
        product.unit_price = float(catalog.min_price)
    if _auto_pricing_allowed(product) and product.cost is None and catalog.cost is not None:
        product.cost = float(catalog.cost)

    db.query(CrmNoticeProductMatch).filter(
        CrmNoticeProductMatch.notice_product_id == product.id,
        CrmNoticeProductMatch.id != match.id,
    ).update({CrmNoticeProductMatch.status: CrmNoticeProductMatchStatus.REJECTED}, synchronize_session=False)
    match.status = CrmNoticeProductMatchStatus.CONFIRMED

    db.add(
        CrmNoticeHistory(
            tenant_id=current_user.tenant_id,
            notice_id=match.notice_id,
            user_id=current_user.id,
            action="Match confirmado",
            details={
                "notice_product_id": product.id,
                "catalog_product_id": catalog.id,
                "catalog_product": _catalog_title(catalog),
            },
        )
    )
    db.commit()
    return get_notice_item_match_payload(db, current_user, match.notice_id)


def mark_notice_product_ground_truth(
    db: Session,
    current_user: User,
    notice_product_id: str,
    catalog_product_id: str,
    *,
    source: str = "manual_confirmed",
    notes: str | None = None,
) -> dict[str, Any]:
    product = (
        db.query(CrmNoticeProduct)
        .filter(
            CrmNoticeProduct.id == notice_product_id,
            CrmNoticeProduct.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not product:
        raise LookupError("Item do edital nao encontrado.")
    catalog = (
        db.query(CrmCatalogProduct)
        .filter(
            CrmCatalogProduct.id == catalog_product_id,
            CrmCatalogProduct.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not catalog:
        raise LookupError("Produto do catalogo nao encontrado.")

    product.catalog_product_id = catalog.id
    product.catalog_match_source = source
    product.catalog_match_confirmed_by = current_user.id
    product.catalog_match_confirmed_at = datetime.utcnow()
    product.catalog_match_notes = notes
    _remember_lpu_version(product, catalog)
    if _auto_pricing_allowed(product) and product.unit_price is None and catalog.min_price is not None:
        product.unit_price = float(catalog.min_price)
    if _auto_pricing_allowed(product) and product.cost is None and catalog.cost is not None:
        product.cost = float(catalog.cost)

    existing_match = (
        db.query(CrmNoticeProductMatch)
        .filter(
            CrmNoticeProductMatch.notice_product_id == product.id,
            CrmNoticeProductMatch.catalog_product_id == catalog.id,
        )
        .first()
    )
    if existing_match is not None:
        existing_match.status = CrmNoticeProductMatchStatus.CONFIRMED
        product.catalog_match_model_version = existing_match.source_method
        db.query(CrmNoticeProductMatch).filter(
            CrmNoticeProductMatch.notice_product_id == product.id,
            CrmNoticeProductMatch.id != existing_match.id,
        ).update({CrmNoticeProductMatch.status: CrmNoticeProductMatchStatus.REJECTED}, synchronize_session=False)

    db.add(
        CrmNoticeHistory(
            tenant_id=current_user.tenant_id,
            notice_id=product.notice_id,
            user_id=current_user.id,
            action="Ground truth de match registrado",
            details={
                "notice_product_id": product.id,
                "catalog_product_id": catalog.id,
                "source": source,
            },
        )
    )
    db.commit()
    return get_notice_item_match_payload(db, current_user, product.notice_id)


def mark_notice_product_match_review(
    db: Session,
    current_user: User,
    notice_product_id: str,
    *,
    verdict: str,
    confidence: float | None = None,
    reason_codes: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    normalized_verdict = str(verdict or "").strip().upper().replace(" ", "_")
    if normalized_verdict not in {"ATENDE", "VERIFICAR", "NAO_ATENDE"}:
        raise ValueError("verdict deve ser ATENDE, VERIFICAR ou NAO_ATENDE.")
    if confidence is not None and not 0.0 <= float(confidence) <= 1.0:
        raise ValueError("confidence deve estar entre 0 e 1.")

    product = (
        db.query(CrmNoticeProduct)
        .filter(
            CrmNoticeProduct.id == notice_product_id,
            CrmNoticeProduct.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not product:
        raise LookupError("Item do edital nao encontrado.")
    if not product.catalog_product_id:
        raise ValueError("Vincule um produto do catalogo antes de registrar o veredito tecnico.")

    cleaned_reasons = []
    for value in reason_codes or []:
        code = str(value or "").strip().lower().replace(" ", "_")[:80]
        if code and code not in cleaned_reasons:
            cleaned_reasons.append(code)

    product.match_review_verdict = normalized_verdict
    product.match_review_confidence = round(float(confidence), 4) if confidence is not None else None
    product.match_review_reason_codes = cleaned_reasons[:20]
    product.match_review_evidence = list(evidence or [])[:30]
    product.match_review_notes = str(notes or "").strip()[:4000] or None
    product.match_reviewed_by = current_user.id
    product.match_reviewed_at = datetime.utcnow()
    db.add(
        CrmNoticeHistory(
            tenant_id=current_user.tenant_id,
            notice_id=product.notice_id,
            user_id=current_user.id,
            action="Veredito tecnico do match registrado",
            details={
                "notice_product_id": product.id,
                "catalog_product_id": product.catalog_product_id,
                "verdict": normalized_verdict,
                "confidence": product.match_review_confidence,
                "reason_codes": product.match_review_reason_codes,
            },
        )
    )
    db.commit()
    return get_notice_item_match_payload(db, current_user, product.notice_id)


def build_match_ground_truth_report(
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
    rows = [_ground_truth_row(product) for product in products]
    evaluated = [row for row in rows if row["suggestions_count"] > 0]
    hidden = [row for row in rows if row["rank"] is None and row["suggestions_count"] > 0]

    total = len(rows)
    evaluated_total = len(evaluated)
    top1 = sum(1 for row in evaluated if row["rank"] == 1)
    top3 = sum(1 for row in evaluated if row["rank"] is not None and row["rank"] <= 3)
    top5 = sum(1 for row in evaluated if row["rank"] is not None and row["rank"] <= 5)
    avg_score = _avg(row["ground_truth_score"] for row in evaluated if row["ground_truth_score"] is not None)

    return {
        "summary": {
            "ground_truth_items": total,
            "linked_items_included": total,
            "include_unmarked": include_unmarked,
            "evaluated_items": evaluated_total,
            "without_suggestions": total - evaluated_total,
            "top1_hits": top1,
            "top3_hits": top3,
            "top5_hits": top5,
            "top1_rate": _rate(top1, evaluated_total),
            "top3_rate": _rate(top3, evaluated_total),
            "top5_rate": _rate(top5, evaluated_total),
            "hidden_errors": len(hidden),
            "avg_ground_truth_score": avg_score,
        },
        "hidden_errors": hidden[:50],
        "low_confidence_truth": [
            row for row in evaluated
            if row["ground_truth_score"] is not None and row["ground_truth_score"] < 0.64
        ][:50],
        "items": rows,
    }


def build_attached_products_llm_report(
    db: Session,
    current_user: User,
    *,
    notice_id: str | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    query = (
        db.query(CrmNoticeProduct)
        .options(
            joinedload(CrmNoticeProduct.notice).joinedload(CrmNotice.organ),
            joinedload(CrmNoticeProduct.notice).joinedload(CrmNotice.portal),
            joinedload(CrmNoticeProduct.catalog_product),
            joinedload(CrmNoticeProduct.product_matches).joinedload(CrmNoticeProductMatch.catalog_product),
        )
        .filter(
            CrmNoticeProduct.tenant_id == current_user.tenant_id,
            CrmNoticeProduct.catalog_product_id.isnot(None),
        )
    )
    if notice_id:
        query = query.filter(CrmNoticeProduct.notice_id == notice_id)

    products = query.order_by(CrmNoticeProduct.created_at.desc()).limit(limit).all()
    items = [_attached_products_llm_row(product) for product in products]
    notices = {item["notice"]["id"] for item in items if item.get("notice", {}).get("id")}
    confirmed = sum(1 for item in items if item["attachment"]["source"])
    with_match_suggestion = sum(1 for item in items if item["match_evidence"]["attached_match"] is not None)
    discarded = sum(1 for item in items if item["notice"].get("is_discarded"))
    training_labels = defaultdict(int)
    for item in items:
        training_labels[item["training"]["label"]] += 1

    return {
        "report_type": "crm_attached_products_llm_context",
        "summary": {
            "attached_items": len(items),
            "notices_count": len(notices),
            "discarded_notices_included": len({item["notice"]["id"] for item in items if item["notice"].get("is_discarded")}),
            "discarded_items_included": discarded,
            "confirmed_or_sourced_items": confirmed,
            "items_with_match_evidence": with_match_suggestion,
            "training_labels": dict(training_labels),
            "limit": limit,
        },
        "llm_task": {
            "objective": (
                "Avaliar se cada produto do catalogo anexado ao item do edital atende a descricao, "
                "caracteristicas tecnicas, quantidades, prazos e restricoes comerciais do edital."
            ),
            "coverage": (
                "Inclui editais ativos, encerrados, ganhos, perdidos e descartados que possuam "
                "um produto do catalogo vinculado. O resultado comercial do edital nao define o rotulo de match."
            ),
            "expected_output": [
                "veredito por item: atende, atende com ressalvas ou nao atende",
                "principais evidencias do edital usadas na decisao",
                "principais evidencias do produto do catalogo usadas na decisao",
                "gaps, riscos e perguntas que precisam de validacao humana",
                "resumo executivo por edital",
            ],
            "important_fields": [
                "notice",
                "notice_product",
                "attached_catalog_product",
                "attachment",
                "match_evidence",
            ],
        },
        "items": items,
    }


def flatten_attached_products_report_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in report.get("items") or []:
        notice = item.get("notice") or {}
        notice_product = item.get("notice_product") or {}
        catalog = item.get("attached_catalog_product") or {}
        attachment = item.get("attachment") or {}
        evidence = item.get("match_evidence") or {}
        training = item.get("training") or {}
        rows.append({
            "notice_id": notice.get("id"),
            "notice_number": notice.get("number"),
            "notice_tor_id": notice.get("tor_id"),
            "notice_bid_number": notice.get("bid_number"),
            "notice_title": notice.get("title"),
            "organ": notice.get("organ"),
            "portal": notice.get("portal"),
            "municipality_name": notice.get("municipality_name"),
            "state": notice.get("state"),
            "stage": notice.get("stage"),
            "notice_outcome": notice.get("outcome"),
            "notice_outcome_reason": notice.get("outcome_reason"),
            "notice_is_discarded": notice.get("is_discarded"),
            "notice_product_id": notice_product.get("id"),
            "item_number": notice_product.get("item_number"),
            "lot": notice_product.get("lot"),
            "item_description": notice_product.get("description"),
            "quantity": notice_product.get("quantity"),
            "unit": notice_product.get("unit"),
            "item_category": notice_product.get("category"),
            "technical_characteristics": notice_product.get("technical_characteristics"),
            "reference_price": notice_product.get("reference_price"),
            "reference_total_price": notice_product.get("reference_total_price"),
            "catalog_product_id": catalog.get("id") or attachment.get("catalog_product_id"),
            "catalog_name": catalog.get("name"),
            "catalog_brand": catalog.get("brand"),
            "catalog_model": catalog.get("model"),
            "catalog_sku": catalog.get("sku"),
            "catalog_mpn": catalog.get("manufacturer_part_number"),
            "catalog_category": catalog.get("category"),
            "catalog_specification": catalog.get("specification"),
            "catalog_keywords": catalog.get("keywords"),
            "attachment_source": attachment.get("source"),
            "attachment_confirmed_at": attachment.get("confirmed_at"),
            "attachment_model_version": attachment.get("model_version"),
            "training_label": training.get("label"),
            "training_use": training.get("recommended_use"),
            "training_review_required": training.get("review_required"),
            "attached_product_rank": evidence.get("attached_product_rank"),
            "attached_product_score": evidence.get("attached_product_score"),
            "suggestions_count": evidence.get("suggestions_count"),
        })
    return rows


def reject_notice_item_match(db: Session, current_user: User, match_id: str) -> dict[str, Any]:
    match = _load_match(db, current_user, match_id)
    match.status = CrmNoticeProductMatchStatus.REJECTED
    db.add(
        CrmNoticeHistory(
            tenant_id=current_user.tenant_id,
            notice_id=match.notice_id,
            user_id=current_user.id,
            action="Sugestao de match rejeitada",
            details={
                "notice_product_id": match.notice_product_id,
                "catalog_product_id": match.catalog_product_id,
            },
        )
    )
    db.commit()
    return get_notice_item_match_payload(db, current_user, match.notice_id)


def _rank_candidates(
    product: CrmNoticeProduct,
    catalog_products: list[CrmCatalogProduct],
    *,
    embedding_cache: dict[str, list[float]],
    use_llm: bool,
) -> list[dict[str, Any]]:
    notice_text = _notice_product_text(product)
    lexical_ranked = sorted(
        (
            {
                "catalog": catalog,
                "lexical_score": lexical_similarity(notice_text, _catalog_product_text(catalog)),
            }
            for catalog in catalog_products
        ),
        key=lambda item: item["lexical_score"],
        reverse=True,
    )[:PRESELECT_LIMIT]

    if AI_FEATURES_ENABLED:
        _attach_semantic_scores(product, lexical_ranked, embedding_cache=embedding_cache)
    ranked: list[dict[str, Any]] = []
    for candidate in lexical_ranked:
        llm_payload = None
        if use_llm and (candidate.get("semantic_score") or candidate["lexical_score"]) >= 0.5 and len(ranked) < 2:
            llm_payload = try_llm_rerank(
                notice_text=notice_text,
                candidate_title=_catalog_title(candidate["catalog"]),
                candidate_text=_catalog_product_text(candidate["catalog"]),
            )

        technical = technical_compatibility_score(notice_text, _catalog_product_text(candidate["catalog"]))
        semantic_score = candidate.get("semantic_score")
        if technical is not None:
            semantic_score = max(semantic_score or 0.0, technical.score)

        score = combine_scores(
            candidate["lexical_score"],
            semantic_score,
            llm_payload.get("score") if llm_payload else None,
        )
        if llm_payload:
            score = MatchScore(
                lexical_score=score.lexical_score,
                semantic_score=score.semantic_score,
                llm_score=score.llm_score,
                overall_score=score.overall_score,
                level=llm_payload.get("level") or score.level,
                source_method=score.source_method,
                rationale=llm_payload.get("rationale"),
                matched_features=tuple(llm_payload.get("matched_features") or ()),
                conflicts=tuple(llm_payload.get("conflicts") or ()),
            )
        if _has_hard_category_conflict(notice_text, _catalog_product_text(candidate["catalog"])):
            score = MatchScore(
                lexical_score=score.lexical_score,
                semantic_score=score.semantic_score,
                llm_score=score.llm_score,
                overall_score=min(score.overall_score, 0.25),
                level="none",
                source_method=score.source_method,
                rationale=score.rationale or "Familia tecnica incompativel entre item do edital e produto do catalogo.",
                matched_features=score.matched_features,
                conflicts=(*score.conflicts, "Familia tecnica incompativel entre item do edital e produto do catalogo."),
            )
        elif technical is not None and (technical.matched_features or technical.conflicts):
            score = MatchScore(
                lexical_score=score.lexical_score,
                semantic_score=score.semantic_score,
                llm_score=score.llm_score,
                overall_score=score.overall_score,
                level=score.level,
                source_method=score.source_method,
                rationale=score.rationale,
                matched_features=(*score.matched_features, *technical.matched_features),
                conflicts=(*score.conflicts, *technical.conflicts),
            )
        ranked.append({
            "catalog": candidate["catalog"],
            "score": score,
        })

    return sorted(ranked, key=lambda item: item["score"].overall_score, reverse=True)


def _attach_semantic_scores(
    product: CrmNoticeProduct,
    ranked_candidates: list[dict[str, Any]],
    *,
    embedding_cache: dict[str, list[float]],
) -> None:
    notice_key = f"notice:{product.id}"
    notice_text = _notice_product_text(product)
    entries = [(notice_key, notice_text)]
    for candidate in ranked_candidates:
        entries.append((f"catalog:{candidate['catalog'].id}", _catalog_product_text(candidate["catalog"])))

    missing = [(key, text) for key, text in entries if key not in embedding_cache and normalize_text(text)]
    if missing:
        try:
            vectors = embed_texts_batch([text for _, text in missing])
            for (key, _), vector in zip(missing, vectors):
                embedding_cache[key] = vector
        except Exception:
            return

    notice_embedding = embedding_cache.get(notice_key)
    if not notice_embedding:
        return

    for candidate in ranked_candidates:
        catalog_embedding = embedding_cache.get(f"catalog:{candidate['catalog'].id}")
        candidate["semantic_score"] = cosine_similarity(notice_embedding, catalog_embedding) if catalog_embedding else None


def _load_notice(db: Session, current_user: User, notice_id: str) -> CrmNotice:
    notice = (
        db.query(CrmNotice)
        .options(
            joinedload(CrmNotice.notice_products).joinedload(CrmNoticeProduct.catalog_product),
        )
        .filter(CrmNotice.id == notice_id, CrmNotice.tenant_id == current_user.tenant_id)
        .first()
    )
    if not notice:
        raise LookupError("Edital CRM nao encontrado.")
    return notice


def _load_match(db: Session, current_user: User, match_id: str) -> CrmNoticeProductMatch:
    match = (
        db.query(CrmNoticeProductMatch)
        .options(
            joinedload(CrmNoticeProductMatch.notice_product),
            joinedload(CrmNoticeProductMatch.catalog_product),
        )
        .filter(
            CrmNoticeProductMatch.id == match_id,
            CrmNoticeProductMatch.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not match:
        raise LookupError("Sugestao de match nao encontrada.")
    return match


def _catalog_title(product: CrmCatalogProduct) -> str:
    return " ".join(part for part in [product.brand, product.model] if part) or product.name or "Produto do catalogo"


def _catalog_product_text(product: CrmCatalogProduct) -> str:
    parts = [
        product.name,
        product.brand,
        product.model,
        product.sku,
        product.specification,
        product.description,
        product.keywords,
        product.notes,
    ]
    return " | ".join(part for part in parts if part)


def _notice_product_text(product: CrmNoticeProduct) -> str:
    parts = [
        product.description,
        product.product_code,
        product.item_number,
        product.lot,
        product.notes,
    ]
    return " | ".join(part for part in parts if part)


def _reference_value(product: CrmNoticeProduct) -> float:
    if product.reference_total_price is not None:
        return float(product.reference_total_price)
    if product.reference_price is not None and product.quantity is not None:
        return float(product.reference_price) * float(product.quantity)
    return float(product.quantity or 0.0)


def _serialize_notice_product(product: CrmNoticeProduct) -> dict[str, Any]:
    return {
        "id": product.id,
        "item_number": product.item_number,
        "lot": product.lot,
        "product_code": product.product_code,
        "description": product.description,
        "quantity": product.quantity,
        "reference_price": product.reference_price,
        "reference_total_price": product.reference_total_price,
        "catalog_product_id": product.catalog_product_id,
        "catalog_match_source": product.catalog_match_source,
        "catalog_match_confirmed_by": product.catalog_match_confirmed_by,
        "catalog_match_confirmed_at": product.catalog_match_confirmed_at.isoformat() if product.catalog_match_confirmed_at else None,
        "catalog_match_model_version": product.catalog_match_model_version,
        "catalog_match_notes": product.catalog_match_notes,
        "catalog_lpu_version": product.catalog_lpu_version,
        "match_review_verdict": product.match_review_verdict,
        "match_review_confidence": product.match_review_confidence,
        "match_review_reason_codes": product.match_review_reason_codes,
        "match_review_evidence": product.match_review_evidence,
        "match_review_notes": product.match_review_notes,
        "match_reviewed_by": product.match_reviewed_by,
        "match_reviewed_at": product.match_reviewed_at.isoformat() if product.match_reviewed_at else None,
        "catalog_product": {
            "id": product.catalog_product.id,
            "name": product.catalog_product.name,
            "brand": product.catalog_product.brand,
            "model": product.catalog_product.model,
            "sku": product.catalog_product.sku,
            "category": getattr(product.catalog_product, "category", None),
        } if product.catalog_product else None,
    }


def _ground_truth_row(product: CrmNoticeProduct) -> dict[str, Any]:
    matches = sorted(product.product_matches or [], key=lambda item: item.match_rank or 9999)
    truth_match = next((match for match in matches if match.catalog_product_id == product.catalog_product_id), None)
    best_match = matches[0] if matches else None
    return {
        "notice_id": product.notice_id,
        "notice_number": product.notice.number if product.notice else None,
        "notice_title": product.notice.title if product.notice else None,
        "notice_product_id": product.id,
        "item_number": product.item_number,
        "description": product.description,
        "ground_truth_catalog_product_id": product.catalog_product_id,
        "ground_truth_catalog_product": _catalog_title(product.catalog_product) if product.catalog_product else None,
        "source": product.catalog_match_source,
        "confirmed_at": product.catalog_match_confirmed_at.isoformat() if product.catalog_match_confirmed_at else None,
        "confirmed_by": product.catalog_match_confirmed_by,
        "model_version": product.catalog_match_model_version,
        "rank": truth_match.match_rank if truth_match else None,
        "ground_truth_score": truth_match.overall_score if truth_match else None,
        "best_catalog_product_id": best_match.catalog_product_id if best_match else None,
        "best_catalog_product": _catalog_title(best_match.catalog_product) if best_match and best_match.catalog_product else None,
        "best_score": best_match.overall_score if best_match else None,
        "suggestions_count": len(matches),
    }


def _attached_products_llm_row(product: CrmNoticeProduct) -> dict[str, Any]:
    matches = sorted(product.product_matches or [], key=lambda item: item.match_rank or 9999)
    attached_match = next((match for match in matches if match.catalog_product_id == product.catalog_product_id), None)
    best_match = matches[0] if matches else None
    notice = product.notice
    catalog = product.catalog_product
    training = _training_metadata(product.catalog_match_source)
    outcome = _enum_value(notice.outcome) if notice else None
    return {
        "notice": {
            "id": notice.id if notice else None,
            "number": notice.number if notice else None,
            "tor_id": notice.tor_id if notice else None,
            "bid_number": notice.bid_number if notice else None,
            "title": notice.title if notice else None,
            "organ": notice.organ.name if notice and notice.organ else None,
            "portal": notice.portal.name if notice and notice.portal else None,
            "municipality_name": notice.municipality_name if notice else None,
            "state": notice.state if notice else None,
            "modality": notice.modality if notice else None,
            "auction_date": notice.auction_date.isoformat() if notice and notice.auction_date else None,
            "estimated_value": notice.estimated_value if notice else None,
            "stage": notice.stage.value if notice and notice.stage else None,
            "outcome": outcome,
            "outcome_reason": notice.outcome_reason if notice else None,
            "is_discarded": outcome == "not_pursued",
            "decision_recommendation": notice.decision_recommendation if notice else None,
            "decision_score": notice.decision_score if notice else None,
            "bi_item_summary": notice.bi_item_summary if notice else None,
            "bi_criterion": notice.bi_criterion if notice else None,
            "bi_exclusivity": notice.bi_exclusivity if notice else None,
            "bi_risk_identified": notice.bi_risk_identified if notice else None,
            "particularities": notice.particularities if notice else None,
        },
        "notice_product": {
            "id": product.id,
            "item_number": product.item_number,
            "lot": product.lot,
            "product_code": product.product_code,
            "description": product.description,
            "quantity": product.quantity,
            "unit": product.unit,
            "warranty": product.warranty,
            "delivery_deadline": product.delivery_deadline,
            "category": product.category,
            "technical_characteristics": product.technical_characteristics,
            "risk_associated": product.risk_associated,
            "reference_price": product.reference_price,
            "reference_total_price": product.reference_total_price,
            "brand_direction_exists": product.brand_direction_exists,
            "brand_direction_model": product.brand_direction_model,
            "brand_direction_type": product.brand_direction_type,
            "brand_direction_justification": product.brand_direction_justification,
            "exclusive_epp_label": product.exclusive_epp_label,
            "bi_features": product.bi_features,
            "raw_payload": product.raw_payload,
            "notes": product.notes,
        },
        "attached_catalog_product": _serialize_catalog_product_for_llm(catalog),
        "attachment": {
            "catalog_product_id": product.catalog_product_id,
            "source": product.catalog_match_source,
            "confirmed_by": product.catalog_match_confirmed_by,
            "confirmed_at": product.catalog_match_confirmed_at.isoformat() if product.catalog_match_confirmed_at else None,
            "model_version": product.catalog_match_model_version,
            "lpu_version": product.catalog_lpu_version,
            "notes": product.catalog_match_notes,
        },
        "training": training,
        "match_evidence": {
            "attached_match": _serialize_match(attached_match) if attached_match else None,
            "best_match": _serialize_match(best_match) if best_match else None,
            "attached_product_rank": attached_match.match_rank if attached_match else None,
            "attached_product_score": attached_match.overall_score if attached_match else None,
            "suggestions_count": len(matches),
        },
    }


def _training_metadata(source: str | None) -> dict[str, Any]:
    """Classifica a confianca do vinculo sem excluir editais por resultado."""
    if source in {"manual_confirmed", "match_confirmed"}:
        return {
            "label": "positive_confirmed",
            "recommended_use": "train_positive",
            "review_required": False,
        }
    if source == "manual_kit":
        return {
            "label": "positive_kit_review",
            "recommended_use": "review_before_training",
            "review_required": True,
        }
    return {
        "label": "unverified_link",
        "recommended_use": "review_before_training",
        "review_required": True,
    }


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _serialize_catalog_product_for_llm(product: CrmCatalogProduct | None) -> dict[str, Any] | None:
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
        "unit": product.unit,
        "cost": product.cost,
        "min_price": product.min_price,
        "computed_min_price": product.computed_min_price,
        "tax_percent": product.tax_percent,
        "margin_percent": product.margin_percent,
        "notes": product.notes,
        "is_active": product.is_active,
    }


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _avg(values: Any) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 4)


def _serialize_match(match: CrmNoticeProductMatch) -> dict[str, Any]:
    catalog = match.catalog_product
    return {
        "id": match.id,
        "notice_product_id": match.notice_product_id,
        "catalog_product_id": match.catalog_product_id,
        "match_rank": match.match_rank,
        "status": match.status.value,
        "match_level": match.match_level.value,
        "source_method": match.source_method,
        "lexical_score": match.lexical_score,
        "semantic_score": match.semantic_score,
        "llm_score": match.llm_score,
        "overall_score": match.overall_score,
        "rationale": match.rationale,
        "matched_features": match.matched_features or [],
        "conflicts": match.conflicts or [],
        "catalog_product": {
            "id": catalog.id,
            "name": catalog.name,
            "brand": catalog.brand,
            "model": catalog.model,
            "sku": catalog.sku,
            "category": getattr(catalog, "category", None),
            "description": catalog.description,
            "specification": catalog.specification,
            "keywords": catalog.keywords,
            "min_price": catalog.min_price,
        } if catalog else None,
    }


def _match_level_enum(raw_level: str | None) -> CrmNoticeProductMatchLevel:
    try:
        return CrmNoticeProductMatchLevel(raw_level or "weak")
    except ValueError:
        return CrmNoticeProductMatchLevel.WEAK


def build_product_reuse_signature(description: str | None, product_code: str | None = None) -> str:
    parts = [normalize_text(description), normalize_text(product_code)]
    return "||".join(part for part in parts if part)


def _build_reusable_match_index(db: Session, current_user: User) -> dict[str, CrmCatalogProduct]:
    confirmed_matches = (
        db.query(CrmNoticeProductMatch)
        .options(
            joinedload(CrmNoticeProductMatch.notice_product),
            joinedload(CrmNoticeProductMatch.catalog_product),
        )
        .filter(
            CrmNoticeProductMatch.tenant_id == current_user.tenant_id,
            CrmNoticeProductMatch.status == CrmNoticeProductMatchStatus.CONFIRMED,
        )
        .all()
    )

    reusable: dict[str, CrmCatalogProduct] = {}
    for match in confirmed_matches:
        if not match.notice_product or not match.catalog_product:
            continue
        if not match.catalog_product.is_active:
            continue
        signature = build_product_reuse_signature(
            match.notice_product.description,
            match.notice_product.product_code,
        )
        if signature and signature not in reusable:
            reusable[signature] = match.catalog_product
    return reusable


def _find_reusable_catalog_product(
    product: CrmNoticeProduct,
    reusable_matches: dict[str, CrmCatalogProduct],
) -> CrmCatalogProduct | None:
    signature = build_product_reuse_signature(product.description, product.product_code)
    if not signature:
        return None
    return reusable_matches.get(signature)
