from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AnalysisDocument, AnalysisItem
from app.services.analysis_normalizer import normalize_analysis_result
from app.services.document_identity import edital_business_key_from_result


def build_source_hash(*parts: str | None) -> str:
    """Stable signature used to reuse previous analysis results."""
    digest = hashlib.sha256()
    for part in parts:
        if part:
            digest.update(part.encode("utf-8", errors="ignore"))
        digest.update(b"\0")
    return digest.hexdigest()


def _meaningful(value: Any) -> bool:
    return value is not None and str(value).strip() not in ("", "-", "N/C")


def build_business_key(result: dict[str, Any], source_name: str | None) -> str | None:
    """
    Identificador do EDITAL em si (não do arquivo/conteúdo) — usado pra saber
    se "é o mesmo documento" mesmo que o JSON tenha sido reprocessado e o
    conteúdo tenha mudado ligeiramente. Prioriza `n_interno` (identificador
    explícito do schema); sem ele, cai numa combinação de pregão/órgão/data.
    Mesma lógica usada em app/crm/json_analysis_importer.py::_build_import_key,
    reimplementada aqui sem acoplar services -> crm.
    """
    return edital_business_key_from_result(result)


def persist_analysis_document(
    db: Session,
    *,
    tenant_id: int,
    source_kind: str,
    source_name: str | None,
    full_text: str | None,
    result: dict[str, Any],
    source_path: str | None = None,
    import_batch_id: int | None = None,
    analysis_only: bool = False,
    schema_name: str | None = None,
    schema_version: str | None = None,
    business_key: str | None = None,
    tokens_used: int = 0,
    processing_ms: int | None = None,
    status: str = "done",
) -> tuple[AnalysisDocument, bool]:
    """
    Upsert a structured analysis and its items by content hash.

    Retorna (document, is_duplicate). Quando um edital com o mesmo
    `business_key` (n_interno/número do pregão) já existe, o documento NÃO
    é reprocessado nem atualizado — é devolvido como está, com
    is_duplicate=True, pra quem chamou saber que não deve avançar esse item
    no processo (nem sincronizar CRM de novo). Pensado pro caso de importar
    uma pasta inteira: os itens novos avançam normalmente, os repetidos são
    pulados sem travar o lote.
    """
    if source_kind == "edital":
        result = normalize_analysis_result(result)

    business_key = business_key or (
        build_business_key(result, source_name) if source_kind == "edital" else None
    )
    result_signature = json.dumps(result, sort_keys=True, ensure_ascii=False)
    source_hash = build_source_hash(source_kind, full_text or result_signature)
    document = (
        db.query(AnalysisDocument)
        .filter(
            AnalysisDocument.tenant_id == tenant_id,
            AnalysisDocument.source_kind == source_kind,
            AnalysisDocument.source_hash == source_hash,
        )
        .first()
    )
    if document is not None:
        return document, True

    if business_key:
        document = (
            db.query(AnalysisDocument)
            .filter(
                AnalysisDocument.tenant_id == tenant_id,
                AnalysisDocument.source_kind == source_kind,
                AnalysisDocument.business_key == business_key,
            )
            .first()
        )

    if document is None:
        document = AnalysisDocument(
            tenant_id=tenant_id,
            import_batch_id=import_batch_id,
            source_kind=source_kind,
            schema_name=schema_name or source_kind,
            schema_version=schema_version,
            source_hash=source_hash,
            business_key=business_key,
        )
        db.add(document)
        db.flush()
    else:
        document.business_key = business_key or document.business_key
        document.schema_name = schema_name or document.schema_name or source_kind
        document.schema_version = schema_version or document.schema_version
        document.import_batch_id = import_batch_id or document.import_batch_id

    document.source_name = source_name
    document.source_path = source_path
    document.analysis_only = analysis_only
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
    return document, False


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
        lote_grupo=item.get("lote_grupo"),
        garantia=item.get("garantia"),
        prazo_entrega=item.get("prazo_entrega"),
        caracteristicas_tecnicas=item.get("caracteristicas_tecnicas"),
        exclusividade_me_epp_item=item.get("exclusividade_me_epp_item"),
        risco_associado=item.get("risco_associado"),
        direcionamento_marca_tipo=direcionamento_marca.get("tipo"),
        direcionamento_marca_justificativa=direcionamento_marca.get("justificativa"),
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
