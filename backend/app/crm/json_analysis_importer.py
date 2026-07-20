from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.crm.sales_process_importer import (
    ImportContext,
    build_tor_id,
    ensure_organ,
    ensure_portal,
    has_meaningful_value,
    normalize_status_label,
    normalize_text,
    optional_meaningful_text,
    optional_text,
    parse_bool,
    parse_datetime_pair,
    parse_float,
)
from app.services.analysis_normalizer import normalize_analysis_result


def sync_analysis_json_to_crm(
    db: Session,
    context: ImportContext,
    result: dict[str, Any],
    *,
    source_name: str | None = None,
) -> dict[str, Any]:
    """Upsert a schema v7.x analysis JSON into the operational CRM."""
    from app.crm.models import CrmNotice
    from app.services.crm_notice_sync import sync_notice_relationships

    result = normalize_analysis_result(result)
    edital = result.get("edital") or {}
    auditoria = result.get("auditoria") or {}
    import_key = _build_import_key(result, source_name)
    n_interno = optional_meaningful_text(result.get("n_interno"))
    tor_id = n_interno or build_tor_id("JSON", import_key)
    city = optional_meaningful_text(edital.get("cidade"))
    state = optional_meaningful_text(edital.get("uf"))

    organ = ensure_organ(
        db,
        context.tenant.id,
        edital.get("orgao"),
        city=city,
        state=state,
        created_by=context.user.id,
    )
    portal = ensure_portal(
        db,
        context.tenant.id,
        edital.get("local"),
        created_by=context.user.id,
    )

    notice_fields = {
        "number": tor_id,
        "tor_id": tor_id,
        "municipality_name": city,
        "title": _build_title(edital),
        "organ_id": organ.id if organ else None,
        "portal_id": portal.id if portal else None,
        "modality": optional_meaningful_text(edital.get("tipo_licitacao")),
        "auction_date": parse_datetime_pair(edital.get("data_disputa"), edital.get("hora_disputa")),
        "estimated_value": parse_float(edital.get("valor_total_switches"))
        or parse_float(edital.get("valor_total_itens"))
        or parse_float(edital.get("valor_total_edital")),
        "address": optional_meaningful_text(edital.get("endereco")),
        "zipcode": optional_meaningful_text(edital.get("cep")),
        "uasg": optional_meaningful_text(edital.get("uasg")),
        "state": state,
        "proposal_validity": optional_meaningful_text(edital.get("validade_proposta")),
        "document_delivery_moment": optional_meaningful_text(edital.get("momento_entrega_documentacao_habilitacao")),
        "analysis_status": optional_meaningful_text(edital.get("status")),
        "analysis_mode": optional_meaningful_text(auditoria.get("modo_analise")),
        "analysis_confidence": optional_meaningful_text(auditoria.get("confianca_geral")),
        "particularities": _build_notice_notes(result),
        "sales_status": normalize_status_label(edital.get("status")),
        "owner_id": context.user.id,
        "created_by": context.user.id,
        "import_key": import_key,
        "stage": "triage",
        "outcome": "pending",
        "company_position": optional_meaningful_text(edital.get("criterio")),
    }

    notice = (
        db.query(CrmNotice)
        .filter(CrmNotice.tenant_id == context.tenant.id, CrmNotice.import_key == import_key)
        .first()
    )
    created = False
    if notice is None:
        notice = CrmNotice(tenant_id=context.tenant.id, **notice_fields)
        db.add(notice)
        db.flush()
        created = True
    else:
        for field_name, value in notice_fields.items():
            if value is not None or getattr(notice, field_name) is None:
                setattr(notice, field_name, value)

    sync_notice_relationships(db, notice, created_by=context.user.id)
    products = _upsert_products(db, context, notice, result.get("itens_elegiveis") or [])
    documents = _upsert_documents(db, context, notice, result)

    return {
        "notice_id": notice.id,
        "created": created,
        "products": products,
        "documents": documents,
        "import_key": import_key,
    }


def _build_import_key(result: dict[str, Any], source_name: str | None) -> str:
    edital = result.get("edital") or {}
    n_interno = optional_meaningful_text(result.get("n_interno"))
    if n_interno:
        return f"analysis-json|{n_interno}"
    parts = [
        source_name,
        edital.get("numero_pregao"),
        edital.get("orgao"),
        edital.get("data_disputa"),
        edital.get("hora_disputa"),
    ]
    raw = "|".join(normalize_text(part).lower() for part in parts if has_meaningful_value(part))
    if not raw:
        raw = json.dumps(result, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"analysis-json|{digest}"


def _build_title(edital: dict[str, Any]) -> str | None:
    parts = [
        optional_meaningful_text(edital.get("numero_pregao")),
        optional_meaningful_text(edital.get("resumo_itens")) or optional_meaningful_text(edital.get("resumo_switches")),
    ]
    return " - ".join(part for part in parts if part) or None


def _build_notice_notes(result: dict[str, Any]) -> str | None:
    edital = result.get("edital") or {}
    riscos = result.get("riscos") or {}
    fields = [
        ("Resumo", edital.get("resumo_itens") or edital.get("resumo_switches")),
        ("Criterio", edital.get("criterio")),
        ("UASG", edital.get("uasg")),
        ("Intervalo", edital.get("intervalo")),
        ("Exclusividade", edital.get("exclusividade_me_epp")),
        ("Validade proposta", edital.get("validade_proposta")),
        ("Entrega documentacao", edital.get("momento_entrega_documentacao_habilitacao")),
        ("Risco identificado", riscos.get("risco_identificado")),
    ]
    parts = [f"{label}: {normalize_text(value)}" for label, value in fields if has_meaningful_value(value)]
    return "\n".join(parts) or None


def _upsert_products(db: Session, context: ImportContext, notice: Any, items: list[dict[str, Any]]) -> int:
    from app.crm.models import CrmNoticeProduct
    from app.services.crm_notice_sync import sync_notice_from_product

    imported = 0
    for index, item in enumerate(items, start=1):
        item_number = optional_meaningful_text(item.get("numero_item_edital")) or str(index)
        quantity = parse_float(item.get("quantidade")) or 1.0
        unit_value = parse_float(item.get("preco_unitario"))
        total_value = parse_float(item.get("valor_total_item"))
        if unit_value is None and total_value is not None and quantity:
            unit_value = round(total_value / quantity, 4)
        if total_value is None and unit_value is not None:
            total_value = round(unit_value * quantity, 4)

        product = (
            db.query(CrmNoticeProduct)
            .filter(CrmNoticeProduct.notice_id == notice.id, CrmNoticeProduct.item_number == item_number)
            .first()
        )
        if product is None:
            product = CrmNoticeProduct(
                tenant_id=context.tenant.id,
                notice_id=notice.id,
                item_number=item_number,
                sort_order=index - 1,
                description=_description_for_item(item, item_number),
                quantity=quantity,
            )
            db.add(product)
            db.flush()

        product.description = _description_for_item(item, item_number)
        product.lot = optional_meaningful_text(item.get("lote_grupo"))
        product.product_code = optional_meaningful_text((item.get("direcionamento_marca") or {}).get("marca_modelo"))
        product.is_exclusive_epp = parse_bool(item.get("exclusividade_me_epp_item"))
        product.exclusive_epp_label = optional_meaningful_text(item.get("exclusividade_me_epp_item"))
        product.quantity = quantity
        product.unit = optional_meaningful_text(item.get("unidade"))
        product.warranty = optional_meaningful_text(item.get("garantia"))
        product.delivery_deadline = optional_meaningful_text(item.get("prazo_entrega"))
        product.bi_features = item.get("caracteristicas_bi") or None
        product.unit_price = unit_value
        product.reference_price = unit_value
        product.reference_total_price = total_value
        product.notes = _item_notes(item)
        product.sort_order = index - 1

        sync_notice_from_product(db, product, created_by=context.user.id)
        imported += 1
    return imported


def _description_for_item(item: dict[str, Any], item_number: str) -> str:
    return (
        optional_text(item.get("descricao_original"))
        or optional_text(item.get("categoria"))
        or f"Item {item_number}"
    )


def _item_notes(item: dict[str, Any]) -> str | None:
    fields = [
        ("Categoria BI", item.get("categoria")),
        ("Garantia", item.get("garantia")),
        ("Prazo entrega", item.get("prazo_entrega")),
        ("Exclusividade ME/EPP", item.get("exclusividade_me_epp_item")),
        ("Risco associado", item.get("risco_associado")),
    ]
    direcionamento = item.get("direcionamento_marca") or {}
    if direcionamento:
        fields.extend(
            [
                ("Direcionamento marca", direcionamento.get("marca_modelo")),
                ("Tipo direcionamento", direcionamento.get("tipo")),
                ("Justificativa", direcionamento.get("justificativa")),
            ]
        )
    caracteristicas = item.get("caracteristicas_bi")
    parts = [f"{label}: {normalize_text(value)}" for label, value in fields if has_meaningful_value(value)]
    if caracteristicas:
        parts.append(f"Caracteristicas BI: {json.dumps(caracteristicas, ensure_ascii=False)}")
    return "\n".join(parts) or None


def _upsert_documents(db: Session, context: ImportContext, notice: Any, result: dict[str, Any]) -> int:
    from app.crm.models import CrmChecklistStatus, CrmNoticeDocument

    rows: list[tuple[str, str, str | None]] = []
    for item in result.get("documentacao") or []:
        name = optional_meaningful_text(item.get("documento"))
        if name:
            rows.append((name, optional_meaningful_text(item.get("categoria")) or "Documentacao", None))
    for item in result.get("declaracoes") or []:
        name = optional_meaningful_text(item.get("declaracao"))
        if name:
            rows.append((name, "Declaracoes", None))

    total = 0
    for index, (name, category, notes) in enumerate(rows, start=1):
        existing = (
            db.query(CrmNoticeDocument)
            .filter(CrmNoticeDocument.notice_id == notice.id, CrmNoticeDocument.name == name)
            .first()
        )
        if existing is None:
            existing = CrmNoticeDocument(
                tenant_id=context.tenant.id,
                notice_id=notice.id,
                name=name,
                status=CrmChecklistStatus.PENDING,
                is_required=True,
                is_specific=True,
                sort_order=index,
            )
            db.add(existing)
            db.flush()
        existing.category = category
        existing.notes = notes
        existing.sort_order = index
        total += 1
    return total
