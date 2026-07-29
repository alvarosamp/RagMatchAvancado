from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import (
    CrmChecklistStatus,
    CrmNotice,
    CrmNoticeDocument,
    CrmNoticeHistory,
    CrmNoticeProduct,
    CrmNoticeStage,
    CrmOrgan,
    CrmPortal,
)


INITIAL_CHECKLIST = [
    ("Baixar edital e anexos", "Triagem", True),
    ("Analisar requisitos tecnicos", "Analise tecnica", True),
    ("Validar documentacao de habilitacao", "Documentacao", True),
    ("Estimar preco e margem", "Comercial", True),
    ("Definir responsavel interno", "Operacao", True),
    ("Preparar proposta comercial", "Proposta", True),
]


def send_opportunity_to_crm(
    db: Session,
    *,
    current_user: User,
    id_pncp: str,
    notice_payload: dict[str, Any] | None,
    score: int | None,
    priority: str | None,
) -> CrmNotice:
    payload = notice_payload or {}
    import_key = f"pncp:{id_pncp}"
    notice = (
        db.query(CrmNotice)
        .filter(
            CrmNotice.tenant_id == current_user.tenant_id,
            CrmNotice.import_key == import_key,
        )
        .first()
    )

    organ_payload = payload.get("orgao_entidade") or {}
    unit_payload = payload.get("unidade_orgao") or {}
    organ = _ensure_organ(
        db,
        current_user=current_user,
        name=organ_payload.get("nome_razao_social") or organ_payload.get("nome") or "Orgao PNCP",
        cnpj=organ_payload.get("cnpj"),
        city=unit_payload.get("municipio"),
        state=unit_payload.get("uf"),
    )
    portal = _ensure_portal(db, current_user=current_user)

    number = id_pncp
    title = _clean(payload.get("objeto")) or f"Oportunidade PNCP {id_pncp}"
    estimated_value = _coerce_float(payload.get("valor_total_estimado"))
    auction_date = _parse_datetime(
        payload.get("data_encerramento_proposta")
        or payload.get("dataEncerramentoProposta")
    )

    if notice is None:
        notice = CrmNotice(
            tenant_id=current_user.tenant_id,
            number=number,
            tor_id=_tor_id(id_pncp),
            title=title,
            organ_id=organ.id if organ else None,
            portal_id=portal.id if portal else None,
            modality=payload.get("modalidade"),
            auction_date=auction_date,
            estimated_value=estimated_value,
            state=unit_payload.get("uf"),
            municipality_name=unit_payload.get("municipio"),
            stage=CrmNoticeStage.TRIAGE,
            sales_status="radar_disputar",
            analysis_status="Aguardando analise tecnica",
            analysis_mode="Radar IA",
            analysis_confidence=priority,
            bi_item_summary=title[:1000],
            particularities=_build_notes(score=score, priority=priority),
            import_key=import_key,
            owner_id=current_user.id,
            created_by=current_user.id,
        )
        db.add(notice)
        db.flush()
        _create_initial_documents(db, notice=notice, current_user=current_user)
        _add_history(
            db,
            notice=notice,
            current_user=current_user,
            action="Criada pelo Radar IA",
            details={"id_pncp": id_pncp, "score": score, "priority": priority},
        )
    else:
        notice.title = title or notice.title
        notice.organ_id = notice.organ_id or (organ.id if organ else None)
        notice.portal_id = notice.portal_id or (portal.id if portal else None)
        notice.modality = payload.get("modalidade") or notice.modality
        notice.auction_date = auction_date or notice.auction_date
        notice.estimated_value = estimated_value if estimated_value is not None else notice.estimated_value
        notice.stage = CrmNoticeStage.TRIAGE
        notice.sales_status = "radar_disputar"
        notice.analysis_status = notice.analysis_status or "Aguardando analise tecnica"
        notice.analysis_mode = notice.analysis_mode or "Radar IA"
        notice.analysis_confidence = priority or notice.analysis_confidence
        _ensure_initial_documents(db, notice=notice, current_user=current_user)
        _add_history(
            db,
            notice=notice,
            current_user=current_user,
            action="Atualizada pelo Radar IA",
            details={"id_pncp": id_pncp, "score": score, "priority": priority},
        )

    return notice


def sync_pncp_files_to_crm(
    db: Session,
    *,
    notice: CrmNotice,
    current_user: User,
    files: list[dict[str, Any]],
) -> int:
    if not files:
        _add_history(
            db,
            notice=notice,
            current_user=current_user,
            action="Radar IA nao encontrou anexos PNCP",
            details={"files": 0},
        )
        return 0

    existing_by_url = {
        doc.source_url: doc
        for doc in notice.notice_documents
        if getattr(doc, "source_url", None)
    }
    created_or_updated = 0
    next_sort = len(notice.notice_documents) + 1
    for file_info in files:
        url = pncp_file_url(file_info)
        if not url:
            continue
        name = pncp_file_name(file_info)
        category = _document_category(name, file_info)
        document = existing_by_url.get(url)
        if document is None:
            document = CrmNoticeDocument(
                tenant_id=current_user.tenant_id,
                notice_id=notice.id,
                name=name,
                category=category,
                is_required=category in {"Edital", "Termo de Referencia"},
                status=CrmChecklistStatus.PENDING,
                source_url=url,
                source_kind="pncp",
                notes="Arquivo localizado automaticamente no PNCP.",
                sort_order=next_sort,
            )
            next_sort += 1
            db.add(document)
            created_or_updated += 1
        else:
            document.name = name or document.name
            document.category = category or document.category
            document.source_kind = "pncp"
            created_or_updated += 1

    download_step = next((doc for doc in notice.notice_documents if doc.name == "Baixar edital e anexos"), None)
    if download_step is not None:
        download_step.status = CrmChecklistStatus.READY
        download_step.notes = f"{created_or_updated} arquivo(s) localizado(s) no PNCP."

    notice.analysis_status = "Documentos PNCP localizados"
    _add_history(
        db,
        notice=notice,
        current_user=current_user,
        action="Anexos PNCP sincronizados",
        details={"files": created_or_updated},
    )
    return created_or_updated


def sync_radar_items_to_crm(
    db: Session,
    *,
    notice: CrmNotice,
    current_user: User,
    radar_items: list[dict[str, Any]],
) -> int:
    existing_by_number = {
        str(item.item_number or "").strip(): item
        for item in notice.notice_products
        if item.item_number
    }
    created_or_updated = 0
    next_sort = len(notice.notice_products) + 1
    for index, item in enumerate(radar_items or [], start=1):
        description = _clean(item.get("descricao"))
        if not description:
            continue
        item_number = str(item.get("numero_item") or index)
        product = existing_by_number.get(item_number)
        if product is None:
            product = CrmNoticeProduct(
                tenant_id=current_user.tenant_id,
                notice_id=notice.id,
                item_number=item_number,
                description=description,
                quantity=_coerce_float(item.get("quantidade")) or 1.0,
                unit=item.get("unidade"),
                reference_price=_coerce_float(item.get("valor_unitario")),
                reference_total_price=_coerce_float(item.get("valor_total")),
                category="Rede / TIC",
                technical_characteristics=", ".join(item.get("matched_terms") or []),
                raw_payload=item,
                sort_order=next_sort,
            )
            next_sort += 1
            db.add(product)
        else:
            product.description = description
            product.quantity = _coerce_float(item.get("quantidade")) or product.quantity or 1.0
            product.unit = item.get("unidade") or product.unit
            product.reference_price = _coerce_float(item.get("valor_unitario")) if item.get("valor_unitario") is not None else product.reference_price
            product.reference_total_price = _coerce_float(item.get("valor_total")) if item.get("valor_total") is not None else product.reference_total_price
            product.technical_characteristics = ", ".join(item.get("matched_terms") or []) or product.technical_characteristics
            product.raw_payload = item
        created_or_updated += 1

    if created_or_updated:
        notice.analysis_status = "Itens PNCP importados para analise"
        notice.bi_item_summary = _items_summary(radar_items)
        _add_history(
            db,
            notice=notice,
            current_user=current_user,
            action="Itens PNCP adicionados pelo Radar IA",
            details={"items": created_or_updated},
        )
    return created_or_updated


def pncp_file_url(file_info: dict[str, Any]) -> str | None:
    for key in (
        "url",
        "link",
        "uri",
        "urlArquivo",
        "urlDownload",
        "linkDownload",
        "linkArquivo",
    ):
        value = file_info.get(key)
        if value:
            return str(value)
    return None


def pncp_file_name(file_info: dict[str, Any]) -> str:
    for key in ("nome", "titulo", "nomeArquivo", "sequencialDocumento", "tipoDocumentoNome"):
        value = file_info.get(key)
        if value:
            return str(value)
    return "Documento PNCP"


def _ensure_organ(
    db: Session,
    *,
    current_user: User,
    name: str,
    cnpj: str | None,
    city: str | None,
    state: str | None,
) -> CrmOrgan:
    clean_cnpj = re.sub(r"\D", "", cnpj or "") or None
    query = db.query(CrmOrgan).filter(CrmOrgan.tenant_id == current_user.tenant_id)
    organ = None
    if clean_cnpj:
        organ = query.filter(CrmOrgan.cnpj == clean_cnpj).first()
    if organ is None:
        organ = query.filter(CrmOrgan.name == name).first()
    if organ is None:
        organ = CrmOrgan(
            tenant_id=current_user.tenant_id,
            name=name,
            cnpj=clean_cnpj,
            city=city,
            state=(state or "").upper()[:8] or None,
            created_by=current_user.id,
        )
        db.add(organ)
        db.flush()
    else:
        organ.city = organ.city or city
        organ.state = organ.state or ((state or "").upper()[:8] or None)
    return organ


def _ensure_portal(db: Session, *, current_user: User) -> CrmPortal:
    portal = (
        db.query(CrmPortal)
        .filter(CrmPortal.tenant_id == current_user.tenant_id, CrmPortal.name == "PNCP")
        .first()
    )
    if portal is None:
        portal = CrmPortal(
            tenant_id=current_user.tenant_id,
            name="PNCP",
            url="https://pncp.gov.br",
            notes="Portal Nacional de Contratacoes Publicas",
            created_by=current_user.id,
        )
        db.add(portal)
        db.flush()
    return portal


def _create_initial_documents(db: Session, *, notice: CrmNotice, current_user: User) -> None:
    for sort_order, (name, category, required) in enumerate(INITIAL_CHECKLIST, start=1):
        db.add(
            CrmNoticeDocument(
                tenant_id=current_user.tenant_id,
                notice_id=notice.id,
                name=name,
                category=category,
                is_required=required,
                status=CrmChecklistStatus.PENDING,
                sort_order=sort_order,
            )
        )


def _ensure_initial_documents(db: Session, *, notice: CrmNotice, current_user: User) -> None:
    existing = {doc.name for doc in notice.notice_documents}
    for sort_order, (name, category, required) in enumerate(INITIAL_CHECKLIST, start=1):
        if name in existing:
            continue
        db.add(
            CrmNoticeDocument(
                tenant_id=current_user.tenant_id,
                notice_id=notice.id,
                name=name,
                category=category,
                is_required=required,
                status=CrmChecklistStatus.PENDING,
                sort_order=sort_order,
            )
        )


def _document_category(name: str, file_info: dict[str, Any]) -> str:
    text = " ".join([name, *(str(value) for value in file_info.values() if value)]).lower()
    if "edital" in text:
        return "Edital"
    if "termo de refer" in text or re.search(r"\btr\b", text):
        return "Termo de Referencia"
    if "anexo" in text:
        return "Anexo"
    return "Documento PNCP"


def _add_history(
    db: Session,
    *,
    notice: CrmNotice,
    current_user: User,
    action: str,
    details: dict[str, Any],
) -> None:
    db.add(
        CrmNoticeHistory(
            tenant_id=current_user.tenant_id,
            notice_id=notice.id,
            user_id=current_user.id,
            action=action,
            details=details,
        )
    )


def _tor_id(id_pncp: str) -> str:
    digest = re.sub(r"\W+", "", id_pncp)[-10:].upper() or "PNCP"
    return f"TOR-PNCP-{digest}"


def _build_notes(*, score: int | None, priority: str | None) -> str:
    parts = ["Origem: Radar IA"]
    if score is not None:
        parts.append(f"Score inicial: {score}")
    if priority:
        parts.append(f"Prioridade inicial: {priority}")
    return " | ".join(parts)


def _items_summary(items: list[dict[str, Any]]) -> str:
    lines = []
    for item in (items or [])[:6]:
        desc = _clean(item.get("descricao")) or "Item PNCP"
        score = item.get("fit_score")
        qty = item.get("quantidade")
        prefix = f"Item {item.get('numero_item')}: " if item.get("numero_item") else ""
        suffix = f" | fit {score}" if score is not None else ""
        qty_text = f" | qtd {qty}" if qty else ""
        lines.append(f"{prefix}{desc[:180]}{qty_text}{suffix}")
    return "\n".join(lines)[:1200]


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt)
        except ValueError:
            continue
    return None
