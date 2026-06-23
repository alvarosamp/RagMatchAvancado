from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AnalysisDocument, AnalysisItem


def build_source_hash(*parts: str | None) -> str:
    """Stable signature used to reuse previous analysis results."""
    digest = hashlib.sha256()
    for part in parts:
        if part:
            digest.update(part.encode("utf-8", errors="ignore"))
        digest.update(b"\0")
    return digest.hexdigest()


def persist_analysis_document(
    db: Session,
    *,
    tenant_id: int,
    source_kind: str,
    source_name: str | None,
    full_text: str | None,
    result: dict[str, Any],
    tokens_used: int = 0,
    processing_ms: int | None = None,
    status: str = "done",
) -> AnalysisDocument:
    """Upsert a structured analysis and its items by content hash."""
    source_hash = build_source_hash(source_kind, full_text or "", source_name or "")
    document = (
        db.query(AnalysisDocument)
        .filter(
            AnalysisDocument.tenant_id == tenant_id,
            AnalysisDocument.source_kind == source_kind,
            AnalysisDocument.source_hash == source_hash,
        )
        .first()
    )
    if document is None:
        document = AnalysisDocument(
            tenant_id=tenant_id,
            source_kind=source_kind,
            source_hash=source_hash,
        )
        db.add(document)
        db.flush()

    document.source_name = source_name
    document.full_text = full_text
    document.result = result
    document.tokens_used = tokens_used or int(result.get("tokens_usados") or 0)
    document.processing_ms = processing_ms
    document.status = status

    document.items.clear()
    db.flush()
    for item in result.get("itens") or []:
        document.items.append(_build_analysis_item(item))

    db.flush()
    return document


def _build_analysis_item(item: dict[str, Any]) -> AnalysisItem:
    return AnalysisItem(
        item_number=_first(item, "numero_item", "item", "numero"),
        item_type=_first(item, "tipo", "categoria", "item_type"),
        description=_first(
            item,
            "descricao",
            "descrição",
            "descricao_item",
            "raw_descricao",
        ),
        brand=_first(item, "marca", "brand"),
        model=_first(item, "modelo", "model"),
        quantity=_to_float(_first(item, "quantidade", "qtd")),
        unit=_first(item, "unidade", "unit"),
        unit_value=_to_float(_first(item, "valor_unitario", "preco_unitario")),
        total_value=_to_float(_first(item, "valor_total", "total")),
        supplier=_first(item, "fornecedor", "empresa"),
        supplier_tax_id=_first(item, "cnpj_fornecedor", "cnpj"),
        raw_text=_first(item, "raw_descricao", "texto", "description"),
        raw_payload=item,
    )


def _first(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None
