from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
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
    import_batch_id: int | None = None,
    analysis_document_id: int | None = None,
    notify: bool = True,
) -> dict[str, Any]:
    """Upsert a schema v7.x analysis JSON into the operational CRM."""
    from app.crm.models import CrmNotice
    from app.services.crm_notice_sync import sync_notice_relationships

    original_result = result or {}
    original_items = original_result.get("itens_elegiveis") or original_result.get("itens") or []
    result = normalize_analysis_result(result)
    edital = result.get("edital") or {}
    auditoria = result.get("auditoria") or {}
    riscos = result.get("riscos") or {}
    auction_date = parse_datetime_pair(edital.get("data_disputa"), edital.get("hora_disputa"))
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
        "bid_number": optional_meaningful_text(edital.get("numero_pregao") or edital.get("numero_licitacao")),
        "municipality_name": city,
        "title": _build_title(edital),
        "organ_id": organ.id if organ else None,
        "portal_id": portal.id if portal else None,
        "modality": optional_meaningful_text(edital.get("tipo_licitacao")),
        "auction_date": auction_date,
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
        "bi_item_summary": optional_meaningful_text(edital.get("resumo_itens") or edital.get("resumo_switches")),
        "bi_criterion": optional_meaningful_text(edital.get("criterio")),
        "bi_interval": optional_meaningful_text(edital.get("intervalo")),
        "bi_exclusivity": optional_meaningful_text(edital.get("exclusividade_me_epp")),
        "bi_risk_identified": optional_meaningful_text(riscos.get("risco_identificado")),
        "bi_risk_operational": _risk_notes(riscos.get("risco_operacional")),
        "bi_risk_documental": _risk_notes(riscos.get("risco_documental")),
        "particularities": None,
        "sales_status": normalize_status_label(edital.get("status")),
        "owner_id": context.user.id,
        "created_by": context.user.id,
        "import_batch_id": import_batch_id,
        "analysis_document_id": analysis_document_id,
        "import_key": import_key,
        "stage": "triage",
        "outcome": "pending",
        "company_position": optional_meaningful_text(edital.get("criterio")),
    }
    _apply_particularity_line_fields(notice_fields, original_result.get("particularities"))

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
        _apply_particularity_line_fields(notice_fields, getattr(notice, "particularities", None), only_missing=True)
        for field_name, value in notice_fields.items():
            if field_name == "particularities":
                setattr(notice, field_name, None)
                continue
            if value is not None or getattr(notice, field_name) is None:
                setattr(notice, field_name, value)

    sync_notice_relationships(db, notice, created_by=context.user.id)
    _ensure_auction_session(db, context, notice, auction_date, result)
    products = _upsert_products(
        db,
        context,
        notice,
        result.get("itens_elegiveis") or [],
        original_items=original_items,
    )
    documents = _upsert_documents(db, context, notice, result)
    if notify:
        _notify_telegram_notice(notice, products)

    return {
        "notice_id": notice.id,
        "created": created,
        "products": products,
        "documents": documents,
        "import_key": import_key,
    }


def _build_import_key(result: dict[str, Any], source_name: str | None) -> str:
    edital = result.get("edital") or {}
    parts = [
        result.get("n_interno"),
        edital.get("numero_pregao"),
        edital.get("numero_licitacao"),
        edital.get("orgao"),
        edital.get("cidade"),
        edital.get("uf"),
        edital.get("local"),
        edital.get("data_disputa"),
        edital.get("hora_disputa"),
    ]
    meaningful = [normalize_text(part).lower() for part in parts if has_meaningful_value(part)]
    item_signature = _items_import_signature(result)
    if item_signature:
        meaningful.append(item_signature)
    raw = "|".join(meaningful)
    if not raw:
        raw = json.dumps(result, sort_keys=True, ensure_ascii=False) or (source_name or "")
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"analysis-json|{digest}"


def _items_import_signature(result: dict[str, Any]) -> str | None:
    items = result.get("itens_elegiveis") or result.get("itens") or []
    if not isinstance(items, list) or not items:
        return None
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_parts = [
            item.get("lote_grupo") or item.get("lote") or item.get("grupo"),
            item.get("numero_item_edital") or item.get("numero_item") or item.get("item") or item.get("numero"),
            item.get("categoria") or item.get("tipo"),
            item.get("descricao_original") or item.get("descricao") or item.get("descricao_item"),
            item.get("quantidade") or item.get("qtd"),
            item.get("preco_unitario") or item.get("valor_unitario") or item.get("preco_minimo"),
        ]
        text = "|".join(normalize_text(part).lower() for part in item_parts if has_meaningful_value(part))
        if text:
            parts.append(text)
    if not parts:
        return None
    raw = "||".join(sorted(parts))
    return "items:" + hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


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
        ("Numero da licitacao", edital.get("numero_pregao") or edital.get("numero_licitacao")),
        ("Intervalo", edital.get("intervalo")),
        ("Exclusividade", edital.get("exclusividade_me_epp")),
        ("Validade proposta", edital.get("validade_proposta")),
        ("Entrega documentacao", edital.get("momento_entrega_documentacao_habilitacao")),
        ("Risco identificado", riscos.get("risco_identificado")),
    ]
    parts = [f"{label}: {normalize_text(value)}" for label, value in fields if has_meaningful_value(value)]
    return "\n".join(parts) or None


def _apply_particularity_line_fields(fields: dict[str, Any], raw_value: Any, *, only_missing: bool = False) -> None:
    """Map legacy 'Label: value' particularity lines into dedicated CRM fields."""
    if not has_meaningful_value(raw_value):
        return
    line_map = _parse_labeled_lines(raw_value)
    assignments = {
        "resumo": "bi_item_summary",
        "criterio": "bi_criterion",
        "critério": "bi_criterion",
        "intervalo": "bi_interval",
        "exclusividade": "bi_exclusivity",
        "validade proposta": "proposal_validity",
        "entrega documentacao": "document_delivery_moment",
        "entrega documentação": "document_delivery_moment",
        "risco identificado": "bi_risk_identified",
        "risco operacional": "bi_risk_operational",
        "risco documental": "bi_risk_documental",
    }
    for label, field_name in assignments.items():
        value = line_map.get(label)
        if has_meaningful_value(value):
            if only_missing and has_meaningful_value(fields.get(field_name)):
                continue
            fields[field_name] = value


def _parse_labeled_lines(value: Any) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in normalize_text(value).splitlines():
        if ":" not in raw_line:
            continue
        label, content = raw_line.split(":", 1)
        normalized_label = _normalize_label(label)
        normalized_content = content.strip()
        if normalized_label and normalized_content:
            parsed[normalized_label] = normalized_content
    return parsed


def _normalize_label(value: Any) -> str:
    return " ".join(normalize_text(value).strip().lower().split())


def _risk_notes(value: Any) -> str | None:
    if not isinstance(value, dict):
        return optional_meaningful_text(value)
    parts = []
    if has_meaningful_value(value.get("existe")):
        parts.append(f"Existe: {value.get('existe')}")
    motivos = value.get("motivos")
    if isinstance(motivos, list) and motivos:
        parts.append("Motivos: " + "; ".join(normalize_text(item) for item in motivos if has_meaningful_value(item)))
    return "\n".join(parts) or None


def _ensure_auction_session(db: Session, context: ImportContext, notice: Any, auction_date: Any, result: dict[str, Any]) -> None:
    if auction_date is None:
        return
    from app.crm.models import CrmNoticeSession, CrmNoticeSessionStatus

    session = next((item for item in notice.notice_sessions if item.sequence == 1), None)
    if session is None:
        with db.no_autoflush:
            session = (
                db.query(CrmNoticeSession)
                .filter(CrmNoticeSession.notice_id == notice.id, CrmNoticeSession.sequence == 1)
                .first()
            )
    notes = _session_notes(result)
    if session is None:
        session = CrmNoticeSession(
            tenant_id=context.tenant.id,
            notice=notice,
            sequence=1,
            scheduled_at=auction_date,
            status=CrmNoticeSessionStatus.SCHEDULED,
            notes=notes,
            created_by=context.user.id,
        )
        db.add(session)
    else:
        session.scheduled_at = auction_date
        session.notes = notes


def _session_notes(result: dict[str, Any]) -> str | None:
    edital = result.get("edital") or {}
    items = result.get("itens_elegiveis") or []
    fields = [
        ("Itens", len(items) if items else None),
        ("Resumo", edital.get("resumo_itens") or edital.get("resumo_switches")),
        ("Prazo entrega", _most_common(item.get("prazo_entrega") for item in items)),
        ("Validade proposta", edital.get("validade_proposta")),
    ]
    parts = [f"{label}: {normalize_text(value)}" for label, value in fields if has_meaningful_value(value)]
    return "\n".join(parts) or None


def _most_common(values: Any) -> Any:
    counts: dict[str, int] = {}
    for value in values:
        if not has_meaningful_value(value):
            continue
        text = normalize_text(value)
        counts[text] = counts.get(text, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: item[1])[0]


def _notify_telegram_notice(notice: Any, products_count: int) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    title = getattr(notice, "title", None) or getattr(notice, "number", None) or "Novo processo"
    auction = getattr(notice, "auction_date", None)
    message = "\n".join(
        part
        for part in [
            "Novo processo importado",
            f"Edital: {title}",
            f"TOR ID: {getattr(notice, 'tor_id', None) or '-'}",
            f"Itens: {products_count}",
            f"Disputa: {auction.strftime('%d/%m/%Y %H:%M') if auction else '-'}",
        ]
        if part
    )
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            timeout=8,
        ).read()
    except Exception:
        # Notificacao nao pode quebrar importacao.
        return


def _upsert_products(
    db: Session,
    context: ImportContext,
    notice: Any,
    items: list[dict[str, Any]],
    *,
    original_items: list[Any] | None = None,
) -> int:
    from app.crm.models import CrmNoticeProduct
    from app.services.crm_notice_sync import sync_notice_from_product

    imported = 0
    original_items = original_items or []
    imported_product_ids: set[str] = set()
    for index, item in enumerate(items, start=1):
        original_item = _matching_original_item(item, original_items, index) or item
        original_features = (
            original_item.get("caracteristicas_bi")
            if isinstance(original_item, dict)
            else None
        )
        if not isinstance(original_features, dict):
            original_features = item.get("caracteristicas_bi") or {}
        original_direction = (
            original_item.get("direcionamento_marca")
            if isinstance(original_item, dict)
            else None
        )
        if not isinstance(original_direction, dict):
            original_direction = item.get("direcionamento_marca") or {}
        raw_item_number = _raw_item_number(item, index)
        item_number = _crm_item_number(item, index, items)
        lot = optional_meaningful_text(item.get("lote_grupo"))
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
        if product is None and item_number != raw_item_number and lot:
            product = (
                db.query(CrmNoticeProduct)
                .filter(
                    CrmNoticeProduct.notice_id == notice.id,
                    CrmNoticeProduct.item_number == raw_item_number,
                    CrmNoticeProduct.lot == lot,
                )
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

        product.item_number = item_number
        product.description = _description_for_item(item, item_number)
        product.lot = lot
        product.product_code = optional_meaningful_text((item.get("direcionamento_marca") or {}).get("marca_modelo"))
        product.is_exclusive_epp = parse_bool(item.get("exclusividade_me_epp_item"))
        product.exclusive_epp_label = optional_meaningful_text(item.get("exclusividade_me_epp_item"))
        product.quantity = quantity
        product.unit = optional_meaningful_text(item.get("unidade"))
        product.warranty = optional_meaningful_text(item.get("garantia"))
        product.delivery_deadline = optional_meaningful_text(item.get("prazo_entrega"))
        product.category = optional_meaningful_text(item.get("categoria"))
        product.technical_characteristics = optional_meaningful_text(
            _original_value(original_item, item, "caracteristicas_tecnicas")
        )
        product.risk_associated = optional_meaningful_text(item.get("risco_associado"))
        product.brand_direction_exists = bool(original_direction.get("existe"))
        product.brand_direction_model = optional_meaningful_text(original_direction.get("marca_modelo"))
        product.brand_direction_type = optional_meaningful_text(original_direction.get("tipo"))
        product.brand_direction_justification = optional_meaningful_text(original_direction.get("justificativa"))
        product.bi_features = original_features or None
        product.bi_feature_quantidade_portas = _bi_feature(original_features, "quantidade_portas")
        product.bi_feature_portas_acesso = _bi_feature(original_features, "portas_acesso")
        product.bi_feature_gerenciamento = _bi_feature(original_features, "gerenciamento")
        product.bi_feature_alimentacao_poe = _bi_feature(original_features, "alimentacao_poe")
        product.bi_feature_uplinks = _bi_feature(original_features, "uplinks")
        product.bi_feature_camada = _bi_feature(original_features, "camada")
        product.bi_feature_tecnologia_wifi = _bi_feature(original_features, "tecnologia_wifi")
        product.bi_feature_alimentacao = _bi_feature(original_features, "alimentacao")
        product.bi_feature_ambiente = _bi_feature(original_features, "ambiente")
        product.bi_feature_formato = _bi_feature(original_features, "formato")
        product.bi_feature_velocidade = _bi_feature(original_features, "velocidade")
        product.bi_feature_tipo_meio = _bi_feature(original_features, "tipo_meio")
        product.bi_feature_alcance = _bi_feature(original_features, "alcance")
        product.raw_payload = original_item if isinstance(original_item, dict) else item
        product.unit_price = unit_value
        product.reference_price = unit_value
        product.reference_total_price = total_value
        product.notes = _item_notes(item)
        product.sort_order = index - 1

        sync_notice_from_product(db, product, created_by=context.user.id)
        imported_product_ids.add(product.id)
        imported += 1
    _remove_stale_imported_products(db, notice, imported_product_ids)
    return imported


def _remove_stale_imported_products(db: Session, notice: Any, imported_product_ids: set[str]) -> None:
    """Remove old JSON-imported items that are no longer present in the current payload."""
    if not imported_product_ids:
        return
    from app.crm.models import CrmNoticeProduct

    stale_products = (
        db.query(CrmNoticeProduct)
        .filter(CrmNoticeProduct.notice_id == notice.id)
        .filter(CrmNoticeProduct.raw_payload.is_not(None))
        .all()
    )
    for product in stale_products:
        if product.id not in imported_product_ids:
            db.delete(product)


def _matching_original_item(item: dict[str, Any], original_items: list[Any], index: int) -> dict[str, Any] | None:
    if not original_items:
        return None
    item_number = normalize_text(item.get("numero_item_edital"))
    item_lot = normalize_text(item.get("lote_grupo"))
    for candidate in original_items:
        if not isinstance(candidate, dict):
            continue
        candidate_number = normalize_text(
            candidate.get("numero_item_edital")
            or candidate.get("numero_item")
            or candidate.get("item")
            or candidate.get("numero")
        )
        candidate_lot = normalize_text(candidate.get("lote_grupo") or candidate.get("lote") or candidate.get("grupo"))
        if item_number and candidate_number == item_number:
            if item_lot and candidate_lot and candidate_lot != item_lot:
                continue
            return candidate
    fallback_index = index - 1
    if 0 <= fallback_index < len(original_items) and isinstance(original_items[fallback_index], dict):
        return original_items[fallback_index]
    return None


def _raw_item_number(item: dict[str, Any], index: int) -> str:
    return optional_meaningful_text(item.get("numero_item_edital")) or str(index)


def _crm_item_number(item: dict[str, Any], index: int, items: list[dict[str, Any]]) -> str:
    item_number = _raw_item_number(item, index)
    lot = optional_meaningful_text(item.get("lote_grupo"))
    if not lot:
        return item_number

    lots = {
        optional_meaningful_text(candidate.get("lote_grupo"))
        for candidate in items
        if isinstance(candidate, dict) and optional_meaningful_text(candidate.get("lote_grupo"))
    }
    if len(lots) > 1:
        return f"Lote {lot} / Item {item_number}"

    same_number_lots = {
        optional_meaningful_text(candidate.get("lote_grupo"))
        for candidate in items
        if isinstance(candidate, dict)
        and optional_meaningful_text(candidate.get("numero_item_edital")) == item_number
        and optional_meaningful_text(candidate.get("lote_grupo"))
    }
    if len(same_number_lots) <= 1:
        return item_number
    return f"Lote {lot} / Item {item_number}"


def _bi_feature(features: dict[str, Any], key: str) -> str | None:
    if not isinstance(features, dict):
        return None
    return optional_meaningful_text(features.get(key))


def _original_value(original_item: Any, item: dict[str, Any], key: str) -> Any:
    if isinstance(original_item, dict) and has_meaningful_value(original_item.get(key)):
        return original_item.get(key)
    return item.get(key)


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
        ("Caracteristicas tecnicas", item.get("caracteristicas_tecnicas")),
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
