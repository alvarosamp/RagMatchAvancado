from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.crm.models import CrmCatalogProduct
from app.logs.config import logger
from app.pipeline.embedder import embed_texts_batch, get_embedding_identity
from app.services.crm_match_scoring import normalize_text


def catalog_product_search_text(product: Any) -> str:
    values = [
        getattr(product, "name", None),
        getattr(product, "brand", None),
        getattr(product, "model", None),
        getattr(product, "manufacturer_part_number", None),
        getattr(product, "sku", None),
        getattr(product, "category", None),
        getattr(product, "specification", None),
        getattr(product, "description", None),
        getattr(product, "keywords", None),
        getattr(product, "equivalent_skus", None),
        getattr(product, "notes", None),
    ]
    return " | ".join(str(value).strip() for value in values if value not in (None, ""))


def catalog_embedding_source_hash(product: Any) -> str:
    normalized = normalize_text(catalog_product_search_text(product))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def catalog_embedding_state(product: Any) -> dict[str, Any]:
    identity = get_embedding_identity()
    source_hash = catalog_embedding_source_hash(product)
    reasons: list[str] = []
    if getattr(product, "embedding", None) is None:
        reasons.append("missing_vector")
    if getattr(product, "embedding_source_hash", None) != source_hash:
        reasons.append("source_changed")
    if getattr(product, "embedding_provider", None) != identity.provider:
        reasons.append("provider_changed")
    if getattr(product, "embedding_model", None) != identity.model:
        reasons.append("model_changed")
    if getattr(product, "embedding_dimensions", None) != identity.dimensions:
        reasons.append("dimension_changed")
    return {
        "is_current": not reasons,
        "reasons": reasons,
        "source_hash": source_hash,
        "embedding_version": identity.version,
    }


def ensure_catalog_embeddings(
    _db: Session,
    products: Iterable[Any],
) -> dict[str, Any]:
    identity = get_embedding_identity()
    product_list = list(products)
    stale: list[tuple[Any, str, str]] = []
    for product in product_list:
        text = catalog_product_search_text(product)
        state = catalog_embedding_state(product)
        if not state["is_current"]:
            source_hash = str(state["source_hash"])
            stale.append((product, text, source_hash))

    if not stale:
        return {
            "total": len(product_list),
            "updated": 0,
            "reused": len(product_list),
            "embedding_version": identity.version,
        }

    vectors = embed_texts_batch([text for _, text, _ in stale])
    if len(vectors) != len(stale):
        raise RuntimeError(f"Provider retornou {len(vectors)} embeddings para {len(stale)} produtos.")
    if any(len(vector) != identity.dimensions for vector in vectors):
        raise ValueError(f"Embedding incompativel com a dimensao configurada ({identity.dimensions}).")

    updated_at = datetime.utcnow()
    for (product, _, source_hash), vector in zip(stale, vectors):
        product.embedding = vector
        product.embedding_source_hash = source_hash
        product.embedding_model = identity.model
        product.embedding_provider = identity.provider
        product.embedding_dimensions = identity.dimensions
        product.embedding_updated_at = updated_at
    logger.info(
        "[CatalogEmbeddings] %s/%s produtos atualizados com %s",
        len(stale),
        len(product_list),
        identity.version,
    )
    return {
        "total": len(product_list),
        "updated": len(stale),
        "reused": len(product_list) - len(stale),
        "embedding_version": identity.version,
    }


def catalog_embedding_status(
    db: Session,
    tenant_id: int,
    *,
    active_only: bool = True,
    limit_examples: int = 20,
) -> dict[str, Any]:
    identity = get_embedding_identity()
    products = _catalog_query(db, tenant_id, active_only=active_only).all()
    reason_counts: dict[str, int] = {}
    examples: list[dict[str, Any]] = []
    current = 0
    stale = 0
    for product in products:
        state = catalog_embedding_state(product)
        if state["is_current"]:
            current += 1
            continue
        stale += 1
        for reason in state["reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if len(examples) < limit_examples:
            examples.append(_catalog_embedding_example(product, state))

    total = len(products)
    return {
        "total": total,
        "current": current,
        "stale": stale,
        "coverage": round(current / total, 4) if total else 1.0,
        "active_only": active_only,
        "embedding_version": identity.version,
        "reason_counts": reason_counts,
        "examples": examples,
    }


def backfill_catalog_embeddings(
    db: Session,
    tenant_id: int,
    *,
    active_only: bool = True,
    stale_only: bool = True,
    limit: int = 100,
) -> dict[str, Any]:
    products = _catalog_query(db, tenant_id, active_only=active_only).all()
    selected: list[CrmCatalogProduct] = []
    for product in products:
        if stale_only and catalog_embedding_state(product)["is_current"]:
            continue
        selected.append(product)
        if len(selected) >= limit:
            break

    stats = ensure_catalog_embeddings(db, selected)
    db.commit()
    status = catalog_embedding_status(db, tenant_id, active_only=active_only, limit_examples=0)
    return {
        "ok": True,
        "processed": len(selected),
        "limit": limit,
        "active_only": active_only,
        "stale_only": stale_only,
        "embedding": stats,
        "status": status,
        "has_more": status["stale"] > 0 if stale_only else False,
    }


def _catalog_query(db: Session, tenant_id: int, *, active_only: bool):
    query = db.query(CrmCatalogProduct).filter(CrmCatalogProduct.tenant_id == tenant_id)
    if active_only:
        query = query.filter(CrmCatalogProduct.is_active.is_(True))
    return query.order_by(CrmCatalogProduct.updated_at.desc(), CrmCatalogProduct.id.asc())


def _catalog_embedding_example(product: CrmCatalogProduct, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "brand": product.brand,
        "model": product.model,
        "reasons": state["reasons"],
        "embedding_model": product.embedding_model,
        "embedding_provider": product.embedding_provider,
        "embedding_dimensions": product.embedding_dimensions,
        "embedding_updated_at": product.embedding_updated_at.isoformat() if product.embedding_updated_at else None,
    }
