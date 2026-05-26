from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.auth.models import User
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
    lexical_similarity,
    normalize_text,
    try_llm_rerank,
)

PRESELECT_LIMIT = 12
SUGGESTIONS_PER_ITEM = 3
MIN_SUGGESTION_SCORE = 0.32


def run_notice_item_match(
    db: Session,
    current_user: User,
    notice_id: str,
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    notice = _load_notice(db, current_user, notice_id)
    catalog_products = (
        db.query(CrmCatalogProduct)
        .filter(
            CrmCatalogProduct.tenant_id == current_user.tenant_id,
            CrmCatalogProduct.is_active.is_(True),
        )
        .all()
    )

    db.query(CrmNoticeProductMatch).filter(
        CrmNoticeProductMatch.tenant_id == current_user.tenant_id,
        CrmNoticeProductMatch.notice_id == notice_id,
    ).delete(synchronize_session=False)
    db.flush()

    embedding_cache: dict[str, list[float]] = {}
    best_scores: list[dict[str, Any]] = []

    for product in notice.notice_products:
        ranked = _rank_candidates(product, catalog_products, embedding_cache=embedding_cache, use_llm=use_llm)
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
    if product.unit_price is None and catalog.min_price is not None:
        product.unit_price = float(catalog.min_price)
    if product.cost is None and catalog.cost is not None:
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

        score = combine_scores(
            candidate["lexical_score"],
            candidate.get("semantic_score"),
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
        "catalog_product": {
            "id": product.catalog_product.id,
            "name": product.catalog_product.name,
            "brand": product.catalog_product.brand,
            "model": product.catalog_product.model,
            "sku": product.catalog_product.sku,
        } if product.catalog_product else None,
    }


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
