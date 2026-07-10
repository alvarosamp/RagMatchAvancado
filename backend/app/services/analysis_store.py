from __future__ import annotations

import hashlib
import json
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
    result_signature = json.dumps(result, sort_keys=True, ensure_ascii=False)
    source_hash = build_source_hash(source_kind, full_text or result_signature, source_name or "")
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

    edital_uf = ((result.get("edital") or {}).get("uf"))

    document.items.clear()
    db.flush()
    items = result.get("itens_elegiveis") or result.get("itens") or []
    for item in items:
        document.items.append(_build_analysis_item(item, uf=edital_uf))

    db.flush()
    return document


def _build_analysis_item(item: dict[str, Any], *, uf: str | None = None) -> AnalysisItem:
    direcionamento_marca = item.get("direcionamento_marca") or {}
    brand = _first(item, "marca", "brand") or direcionamento_marca.get("marca_modelo")
    return AnalysisItem(
        item_number=_first(item, "numero_item_edital", "numero_item", "item", "numero"),
        item_type=_first(item, "tipo", "categoria", "item_type"),
        description=_first(
            item,
            "descricao_original",
            "descricao",
            "descrição",
            "descricao_item",
            "raw_descricao",
        ),
        brand=brand,
        model=_first(item, "modelo", "model"),
        quantity=_to_float(_first(item, "quantidade", "qtd")),
        unit=_first(item, "unidade", "unit"),
        unit_value=_to_float(_first(item, "valor_unitario", "preco_unitario")),
        total_value=_to_float(_first(item, "valor_total", "total", "valor_total_item")),
        supplier=_first(item, "fornecedor", "empresa"),
        supplier_tax_id=_first(item, "cnpj_fornecedor", "cnpj"),
        raw_text=_first(item, "raw_descricao", "texto", "description"),
        raw_payload=item,
        categoria=item.get("categoria"),
        uf=uf,
        has_direcionamento_marca=bool(direcionamento_marca.get("existe")),
        has_risco=_has_risco(item.get("risco_associado")),
        caracteristicas_bi=item.get("caracteristicas_bi"),
    )


def _has_risco(value: Any) -> bool:
    if not value:
        return False
    text = str(value).strip().lower()
    return text not in ("", "nenhum", "n/c", "nao", "não")


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
