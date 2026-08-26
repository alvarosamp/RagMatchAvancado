from __future__ import annotations

import json
import os
import tempfile
import csv
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import quote
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.crm.lpu_importer import import_lpu_catalog
from app.crm.sales_process_importer import build_import_context_for_user, run_import
from app.crm.models import (
    CrmBidAssistLog,
    CrmCatalogProduct,
    CrmCatalogProductDatasheet,
    CrmChecklistStatus,
    CrmNoticeDocument,
    CrmItemWinnerType,
    CrmNotice,
    CrmNoticeHistory,
    CrmNoticeProduct,
    CrmNoticeProductDatasheet,
    CrmNoticeSession,
    CrmNoticeStage,
)
from app.crm.query import TABLES, crm_user_payload, delete_records, insert_records, list_records, update_records
from app.db.session import get_db
from app.jobs.models import Job, JobStatus, JobType
from app.jobs.queue import JobQueue
from app.services.crm_item_matcher import (
    build_attached_products_llm_report,
    build_match_ground_truth_report,
    confirm_notice_item_match,
    flatten_attached_products_report_items,
    get_notice_item_match_payload,
    mark_notice_product_ground_truth,
    reject_notice_item_match,
    run_notice_item_match,
)
from app.services.ops_summary import summarize_crm
from app.services.proposal_generator import (
    build_notice_proposal_docx,
    proposal_filename,
)
from app.services.calendar_export import build_ics, session_calendar_payload
from app.services.email_monitor import email_monitor_configured, run_email_monitor_once
from app.services.decision_intelligence import (
    persist_notice_decision_intelligence,
    serialize_decision_intelligence,
)
from app.services.crm_notice_sync import sync_notice_relationships
from app.services.catalog_datasheets import current_catalog_datasheet, serialize as serialize_catalog_datasheet, store_catalog_datasheet

router = APIRouter(prefix="/crm", tags=["crm"])
DEFAULT_BID_DECREMENT = 1.0
MATCH_PAUSED_MESSAGE = "Match temporariamente pausado para manutenção."


@router.get("/catalog-products/{product_id}/datasheets")
def list_catalog_datasheets(product_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [serialize_catalog_datasheet(row) for row in db.query(CrmCatalogProductDatasheet).filter(CrmCatalogProductDatasheet.tenant_id == current_user.tenant_id, CrmCatalogProductDatasheet.catalog_product_id == product_id).order_by(CrmCatalogProductDatasheet.version.desc()).all()]


@router.post("/catalog-products/{product_id}/datasheets")
async def upload_catalog_datasheet(product_id: str, file: UploadFile = File(...), current_user: User = Depends(require_role("admin", "editor")), db: Session = Depends(get_db)):
    try:
        row = store_catalog_datasheet(db, tenant_id=current_user.tenant_id, user_id=current_user.id, product_id=product_id, fileobj=file.file, filename=file.filename or "datasheet", content_type=file.content_type)
        db.commit()
        return serialize_catalog_datasheet(row)
    finally:
        await file.close()


@router.get("/catalog-datasheets/{datasheet_id}/download")
def download_catalog_datasheet(datasheet_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(CrmCatalogProductDatasheet).filter(CrmCatalogProductDatasheet.id == datasheet_id, CrmCatalogProductDatasheet.tenant_id == current_user.tenant_id).first()
    if not row or not Path(row.storage_path).is_file():
        raise HTTPException(status_code=404, detail="Datasheet nao encontrado.")
    return FileResponse(row.storage_path, media_type=row.content_type or "application/octet-stream", filename=row.original_filename)


@router.post("/notices/{notice_id}/products/{notice_product_id}/catalog-product")
def link_catalog_product_and_datasheet(
    notice_id: str,
    notice_product_id: str,
    payload: dict[str, Any] = Body(...),
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    """Vincula o produto e inclui a revisao vigente do seu datasheet no edital."""
    catalog_product_id = str(payload.get("catalog_product_id") or "").strip()
    if not catalog_product_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o produto do catalogo.")
    notice_product = db.query(CrmNoticeProduct).filter(
        CrmNoticeProduct.id == notice_product_id,
        CrmNoticeProduct.notice_id == notice_id,
        CrmNoticeProduct.tenant_id == current_user.tenant_id,
    ).first()
    catalog_product = db.query(CrmCatalogProduct).filter_by(
        id=catalog_product_id, tenant_id=current_user.tenant_id
    ).first()
    if notice_product is None or catalog_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item ou produto do catalogo nao encontrado.")

    notice_product.catalog_product_id = catalog_product.id
    notice_product.catalog_match_source = "manual_confirmed"
    notice_product.catalog_match_confirmed_by = current_user.id
    notice_product.catalog_match_confirmed_at = datetime.utcnow()
    current = current_catalog_datasheet(db, tenant_id=current_user.tenant_id, product_id=catalog_product.id)
    link = db.query(CrmNoticeProductDatasheet).filter(
        CrmNoticeProductDatasheet.notice_product_id == notice_product.id
    ).first()
    if link is None:
        link = CrmNoticeProductDatasheet(
            tenant_id=current_user.tenant_id,
            notice_id=notice_id,
            notice_product_id=notice_product.id,
            catalog_product_id=catalog_product.id,
            catalog_datasheet_id=current.id if current else None,
        )
        db.add(link)
    else:
        link.catalog_product_id = catalog_product.id
        link.catalog_datasheet_id = current.id if current else None
    document = db.get(CrmNoticeDocument, link.notice_document_id) if link.notice_document_id else None
    if document is None:
        document = CrmNoticeDocument(tenant_id=current_user.tenant_id, notice_id=notice_id, name=f"Datasheet — {catalog_product.name}", category="Datasheets de produtos", is_required=False, is_specific=True, sort_order=9990)
        db.add(document)
        db.flush()
        link.notice_document_id = document.id
    document.source_kind = "catalog_datasheet"
    document.source_url = f"/api/crm/catalog-datasheets/{current.id}/download" if current else None
    document.notes = f"Produto do catalogo: {catalog_product.name}." if current else f"Produto do catalogo: {catalog_product.name}. Nenhum datasheet cadastrado."
    document.status = CrmChecklistStatus.READY if current else CrmChecklistStatus.PENDING
    db.commit()
    return {
        "notice_product_id": notice_product.id,
        "catalog_product_id": catalog_product.id,
        "datasheet": serialize_catalog_datasheet(current) if current else None,
        "message": "Datasheet vigente incluido." if current else "Produto vinculado; nenhum datasheet vigente cadastrado.",
    }


def _parse_json_param(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parametro JSON invalido.") from exc


def _ensure_table(table_name: str) -> None:
    if table_name not in TABLES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tabela CRM '{table_name}' nao suportada.")


def _raise_match_paused() -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=MATCH_PAUSED_MESSAGE,
    )


def _minimum_viable_bid(product: CrmNoticeProduct) -> float:
    if product.unit_price is not None:
        return float(product.unit_price or 0.0)
    catalog = product.catalog_product
    if catalog is not None:
        return float(getattr(catalog, "min_price", None) or catalog.cost or 0.0)
    return float(product.cost or 0.0)


def _normalize_portal_name(value: str | None) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFD", value or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()


def _portal_bid_mode(portal_name: str | None) -> dict[str, str | None]:
    normalized = _normalize_portal_name(portal_name)
    if "bnc" in normalized or "bolsa nacional" in normalized:
        return {
            "key": "bnc",
            "label": "BNC",
            "mode": "manual_seguro",
            "message": "Portal identificado como BNC. Calcule/copiei o lance aqui e confirme no ambiente autenticado.",
        }
    if "bll" in normalized or "bolsa de licit" in normalized:
        return {
            "key": "bll",
            "label": "BLL",
            "mode": "manual_seguro",
            "message": "Portal identificado como BLL. Calcule/copiei o lance aqui e confirme no ambiente autenticado.",
        }
    return {
        "key": None,
        "label": portal_name,
        "mode": "manual_seguro",
        "message": "Portal nao identificado como BLL/BNC. Revise o cadastro do processo antes da disputa.",
    }


def _notice_bid_decrement(notice: CrmNotice) -> float:
    import re

    interval = _normalize_portal_name(getattr(notice, "bi_interval", None))
    match = re.search(r"(\d+(?:[\.,]\d+)?)", interval)
    if not match:
        return DEFAULT_BID_DECREMENT
    try:
        return max(float(match.group(1).replace(",", ".")), 0.01)
    except ValueError:
        return DEFAULT_BID_DECREMENT


def _suggest_bid(
    *,
    current_best_bid: float | None,
    reference_price: float | None,
    minimum_viable_bid: float,
    decrement: float = DEFAULT_BID_DECREMENT,
) -> tuple[float | None, str, str]:
    anchor = current_best_bid if current_best_bid and current_best_bid > 0 else reference_price
    if not anchor or anchor <= 0:
        return None, "missing_price", "Informe o menor lance atual ou o preco de referencia."

    suggested = max(float(anchor) - decrement, 0.01)
    if minimum_viable_bid and suggested < minimum_viable_bid:
        return (
            minimum_viable_bid,
            "stop",
            "Sugestao chegou no limite minimo. Nao reduzir sem autorizacao.",
        )
    return suggested, "ok", "Lance sugerido dentro do limite configurado."


@router.get("/auth/user")
def crm_auth_user(current_user: User = Depends(get_current_user)):
    return {"user": crm_user_payload(current_user)}


@router.post("/imports/sales-processes")
async def crm_import_sales_processes(
    file: UploadFile = File(..., description="Planilha XLSX de processos de vendas"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Somente administradores podem importar a planilha de processos.")

    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie uma planilha .xlsx.")

    suffix = ".xlsx"
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
            content = await file.read()
            tmp.write(content)

        summary = run_import(
            Path(temp_path),
            context_override=build_import_context_for_user(current_user),
        )
        db.expire_all()
        return {"ok": True, "summary": summary}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/imports/lpu")
async def crm_import_lpu_catalog(
    file: UploadFile = File(..., description="Planilha XLSX de LPU/catalogo"),
    drive_url: str = Form(..., description="Link do Drive da LPU"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem importar a LPU.",
        )

    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Envie uma planilha .xlsx.",
        )

    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            temp_path = tmp.name
            tmp.write(await file.read())

        summary = import_lpu_catalog(
            Path(temp_path),
            db=db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            lpu_drive_url=drive_url,
        )
        db.expire_all()
        return {"ok": True, "summary": summary}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/summary")
def crm_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notices = (
        db.query(CrmNotice)
        .options(selectinload(CrmNotice.organ))
        .filter(CrmNotice.tenant_id == current_user.tenant_id)
        .all()
    )
    return summarize_crm(notices)


@router.post("/notices/{notice_id}/advance")
def crm_advance_notice(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    notice = (
        db.query(CrmNotice)
        .options(
            selectinload(CrmNotice.organ),
            selectinload(CrmNotice.portal),
            selectinload(CrmNotice.notice_products),
            selectinload(CrmNotice.notice_sessions),
        )
        .filter(CrmNotice.id == notice_id, CrmNotice.tenant_id == current_user.tenant_id)
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital CRM nao encontrado.")

    previous_stage = notice.stage.value if hasattr(notice.stage, "value") else str(notice.stage)
    next_stage = _next_notice_stage(previous_stage)
    if next_stage == previous_stage:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Edital ja esta na ultima etapa.")

    notice.stage = CrmNoticeStage(next_stage)
    notice.owner_id = current_user.id
    sync_notice_relationships(db, notice, created_by=current_user.id)
    db.add(
        CrmNoticeHistory(
            tenant_id=current_user.tenant_id,
            notice_id=notice.id,
            user_id=current_user.id,
            action=f"Avancado para {next_stage}",
            details={
                "from": previous_stage,
                "to": next_stage,
                "advanced_by": current_user.id,
            },
        )
    )
    db.commit()
    return {
        "ok": True,
        "notice_id": notice.id,
        "stage": next_stage,
        "advanced_by": current_user.id,
    }


@router.post("/email-monitor/run")
def crm_run_email_monitor(
    limit: int | None = Body(default=None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    return run_email_monitor_once(db, limit=limit)


@router.get("/email-monitor/status")
def crm_email_monitor_status(
    current_user: User = Depends(get_current_user),
):
    return {"configured": email_monitor_configured()}


@router.post("/notices/{notice_id}/proposal")
def crm_generate_notice_proposal(
    notice_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissao insuficiente para gerar proposta.",
        )

    notice = (
        db.query(CrmNotice)
        .options(
            selectinload(CrmNotice.organ),
            selectinload(CrmNotice.portal),
            selectinload(CrmNotice.notice_item_results),
            selectinload(CrmNotice.notice_products).selectinload(
                CrmNoticeProduct.catalog_product
            ),
        )
        .filter(
            CrmNotice.id == notice_id,
            CrmNotice.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edital CRM nao encontrado.",
        )

    payload = payload or {}
    try:
        content = build_notice_proposal_docx(
            notice,
            company=payload.get("company") or {},
            options=payload.get("options") or {},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    filename = proposal_filename(notice)
    encoded = quote(filename)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )


@router.get("/notices/{notice_id}/proposal.docx")
def crm_download_notice_proposal(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crm_generate_notice_proposal(
        notice_id=notice_id,
        payload={},
        db=db,
        current_user=current_user,
    )


def _next_notice_stage(current: str) -> str:
    if current == CrmNoticeStage.RESULT.value:
        return current
    order = [
        CrmNoticeStage.TRIAGE.value,
        CrmNoticeStage.ANALYSIS.value,
        CrmNoticeStage.DOCUMENTATION.value,
        CrmNoticeStage.PROPOSAL.value,
        CrmNoticeStage.AUCTION.value,
    ]
    try:
        index = order.index(current)
    except ValueError:
        return CrmNoticeStage.ANALYSIS.value
    return order[min(index + 1, len(order) - 1)]


def _ensure_notice_calendar_event(db: Session, notice: CrmNotice, user_id: int) -> CrmNoticeSession | None:
    if not notice.auction_date:
        return None
    session = next((item for item in notice.notice_sessions if item.sequence == 1), None)
    if session is None:
        session = CrmNoticeSession(
            tenant_id=notice.tenant_id,
            notice_id=notice.id,
            sequence=1,
            scheduled_at=notice.auction_date,
            created_by=user_id,
        )
        db.add(session)
        notice.notice_sessions.append(session)
    else:
        session.scheduled_at = notice.auction_date
    session.outcome_summary = _notice_calendar_title(notice)
    session.notes = _notice_calendar_description(notice)
    return session


def _notice_calendar_title(notice: CrmNotice) -> str:
    organ = notice.organ.name if notice.organ else None
    return " ".join(
        part
        for part in [
            notice.tor_id or notice.number,
            "Pregao",
            f"- {organ}" if organ else None,
        ]
        if part
    )


def _notice_calendar_description(notice: CrmNotice) -> str:
    products = list(notice.notice_products or [])
    total_value = sum(
        float(product.reference_total_price)
        if product.reference_total_price is not None
        else float(product.reference_price or 0) * float(product.quantity or 0)
        for product in products
    )
    parts = [
        f"Numero interno: {_value(notice.tor_id or notice.number)}",
        f"Cidade/UF: {_value(notice.municipality_name)}/{_value(notice.state)}",
        f"Local: {_value(notice.portal.name if notice.portal else None)}",
        f"Tipo de Licitacao: {_value(notice.modality)}",
        f"Criterio: {_value(notice.bi_criterion)}",
        f"UASG: {_value(notice.uasg)}",
        f"Numero do pregao: {_value(getattr(notice, 'bid_number', None) or notice.number)}",
        f"Exclusividade ME/EPP: {_value(notice.bi_exclusivity)}",
        f"Intervalo de lances: {_value(notice.bi_interval)}",
        f"Validade da proposta: {_value(notice.proposal_validity)}",
        f"Momento da entrega da Habilitacao: {_value(notice.document_delivery_moment)}",
        "",
        f"Resumo dos itens: {_value(notice.bi_item_summary)}",
        f"Valor total estimado dos itens: {_money(total_value or notice.estimated_value)}",
        "",
        f"Risco identificado: {_value(notice.bi_risk_identified)}",
    ]
    for index, product in enumerate(products, start=1):
        raw = product.raw_payload if isinstance(product.raw_payload, dict) else {}
        item_number = _value(product.item_number or raw.get("numero_item") or raw.get("numero_item_edital") or index)
        edital_item_number = _value(raw.get("numero_item_edital") or raw.get("numero_item") or product.item_number or index)
        item_title = _value(product.category or product.description)
        parts.extend(
            [
                "",
                f"Item {item_number}: {item_title}",
                f"Lote: {_value(product.lot)}",
                f"Numero no edital: {edital_item_number}",
                _value(product.description),
                f"Quantidade: {_value(product.quantity)}",
                f"Preco: {_money(product.reference_price)}",
                f"Garantia: {_value(product.warranty)}",
                f"Prazo de entrega: {_value(product.delivery_deadline)}",
                f"Exclusividade ME/EPP: {_value(product.exclusive_epp_label)}",
                f"Direcionamento de marca: {'Sim' if product.brand_direction_exists else 'Nao'}",
                f"Marca/modelo: {_value(product.brand_direction_model or product.product_code)}",
                f"Justificativa: {_value(product.brand_direction_justification)}",
            ]
        )
    return "\n".join(parts)


def _value(value: Any) -> str:
    if value is None or value == "":
        return "N/C"
    return str(value)


def _money(value: Any) -> str:
    if value is None or value == "":
        return "N/C"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return "R$ " + f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@router.get("/notices/{notice_id}/calendar")
def crm_notice_calendar_payload(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notice, session = _get_notice_calendar_session(db, notice_id, current_user)
    payload = session_calendar_payload(session, notice)
    return {
        "notice_id": notice.id,
        "session_id": session.id,
        "title": payload["title"],
        "starts_at": payload["starts_at"].isoformat() if payload["starts_at"] else None,
        "description": payload["description"],
        "google_calendar_url": payload["google_calendar_url"],
        "ics_url": f"/api/crm/notices/{notice.id}/calendar.ics",
    }


@router.get("/notices/{notice_id}/calendar.ics")
def crm_notice_calendar_ics(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notice, session = _get_notice_calendar_session(db, notice_id, current_user)
    payload = session_calendar_payload(session, notice)
    if not payload["starts_at"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Edital sem data de agenda.")
    content = build_ics(
        uid=f"tor-crm-{notice.id}-{session.id}",
        title=payload["title"],
        starts_at=payload["starts_at"],
        description=payload["description"],
    )
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="edital_{notice.number or notice.id}.ics"'},
    )


def _get_notice_calendar_session(db: Session, notice_id: str, current_user: User) -> tuple[CrmNotice, CrmNoticeSession]:
    notice = (
        db.query(CrmNotice)
        .options(
            selectinload(CrmNotice.organ),
            selectinload(CrmNotice.portal),
            selectinload(CrmNotice.notice_sessions),
            selectinload(CrmNotice.notice_products),
        )
        .filter(CrmNotice.id == notice_id, CrmNotice.tenant_id == current_user.tenant_id)
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital CRM nao encontrado.")
    session = _ensure_notice_calendar_event(db, notice, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Defina a data do pregao antes de abrir o agendamento.")
    # Regera titulo e resumo a cada exportacao: editais antigos tambem passam a
    # usar o padrao corporativo completo quando enviados para a agenda.
    db.add(
        CrmNoticeHistory(
            tenant_id=current_user.tenant_id,
            notice_id=notice.id,
            user_id=current_user.id,
            action="Resumo de agenda atualizado",
            details={"calendar_session_id": session.id},
        )
    )
    db.commit()
    db.refresh(session)
    return notice, session


@router.get("/notices/{notice_id}/bid-room")
def crm_notice_bid_room(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notice = (
        db.query(CrmNotice)
        .options(
            selectinload(CrmNotice.organ),
            selectinload(CrmNotice.portal),
            selectinload(CrmNotice.notice_products).selectinload(
                CrmNoticeProduct.catalog_product
            ),
            selectinload(CrmNotice.notice_item_results),
            selectinload(CrmNotice.bid_assist_logs),
        )
        .filter(
            CrmNotice.id == notice_id,
            CrmNotice.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edital CRM nao encontrado.",
        )

    portal_name = notice.portal.name if notice.portal else None
    portal_bid_mode = _portal_bid_mode(portal_name)
    decrement = _notice_bid_decrement(notice)
    result_by_product = {
        result.notice_product_id: result
        for result in notice.notice_item_results
    }
    logs_by_product: dict[str, list[CrmBidAssistLog]] = {}
    for log in sorted(
        notice.bid_assist_logs,
        key=lambda item: item.created_at,
        reverse=True,
    ):
        logs_by_product.setdefault(log.notice_product_id, []).append(log)

    items = []
    for product in notice.notice_products:
        if getattr(product, "selected_for_dispute", True) is False:
            continue
        result = result_by_product.get(product.id)
        if result and result.winner_type == CrmItemWinnerType.CANCELLED:
            continue

        last_log = (logs_by_product.get(product.id) or [None])[0]
        current_best_bid = (
            float(last_log.current_best_bid)
            if last_log and last_log.current_best_bid is not None
            else None
        )
        reference_price = (
            float(product.reference_price)
            if product.reference_price is not None
            else None
        )
        minimum = _minimum_viable_bid(product)
        suggested, status_value, message = _suggest_bid(
            current_best_bid=current_best_bid,
            reference_price=reference_price,
            minimum_viable_bid=minimum,
            decrement=decrement,
        )
        catalog = product.catalog_product
        items.append(
            {
                "id": product.id,
                "item_number": product.item_number,
                "lot": product.lot,
                "description": product.description,
                "quantity": product.quantity,
                "unit": product.unit,
                "warranty": product.warranty,
                "delivery_deadline": product.delivery_deadline,
                "category": product.category,
                "technical_characteristics": product.technical_characteristics,
                "risk_associated": product.risk_associated,
                "brand_direction_exists": product.brand_direction_exists,
                "brand_direction_model": product.brand_direction_model,
                "brand_direction_type": product.brand_direction_type,
                "brand_direction_justification": product.brand_direction_justification,
                "exclusive_epp_label": product.exclusive_epp_label,
                "bi_features": product.bi_features,
                "bi_feature_quantidade_portas": product.bi_feature_quantidade_portas,
                "bi_feature_portas_acesso": product.bi_feature_portas_acesso,
                "bi_feature_gerenciamento": product.bi_feature_gerenciamento,
                "bi_feature_alimentacao_poe": product.bi_feature_alimentacao_poe,
                "bi_feature_uplinks": product.bi_feature_uplinks,
                "bi_feature_camada": product.bi_feature_camada,
                "bi_feature_tecnologia_wifi": product.bi_feature_tecnologia_wifi,
                "bi_feature_alimentacao": product.bi_feature_alimentacao,
                "bi_feature_ambiente": product.bi_feature_ambiente,
                "bi_feature_formato": product.bi_feature_formato,
                "bi_feature_velocidade": product.bi_feature_velocidade,
                "bi_feature_tipo_meio": product.bi_feature_tipo_meio,
                "bi_feature_alcance": product.bi_feature_alcance,
                "raw_payload": product.raw_payload,
                "reference_price": product.reference_price,
                "reference_total_price": product.reference_total_price,
                "minimum_viable_bid": minimum,
                "suggested_bid": suggested,
                "suggestion_status": status_value,
                "suggestion_message": message,
                "current_best_bid": current_best_bid,
                "catalog_product": {
                    "id": catalog.id,
                    "name": catalog.name,
                    "brand": catalog.brand,
                    "model": catalog.model,
                    "sku": catalog.sku,
                    "min_price": getattr(catalog, "min_price", None),
                }
                if catalog
                else None,
                "last_logs": [
                    {
                        "id": log.id,
                        "current_best_bid": log.current_best_bid,
                        "suggested_bid": log.suggested_bid,
                        "minimum_viable_bid": log.minimum_viable_bid,
                        "decision": log.decision,
                        "notes": log.notes,
                        "created_at": log.created_at.isoformat()
                        if log.created_at
                        else None,
                    }
                    for log in (logs_by_product.get(product.id) or [])[:5]
                ],
            }
        )

    return {
        "notice": {
            "id": notice.id,
            "number": notice.number,
            "tor_id": notice.tor_id,
            "title": notice.title,
            "municipality_name": notice.municipality_name,
            "organ": notice.organ.name if notice.organ else None,
            "portal": notice.portal.name if notice.portal else None,
            "portal_bid": portal_bid_mode,
            "bid_decrement": decrement,
            "bid_interval": notice.bi_interval,
            "auction_date": notice.auction_date.isoformat()
            if notice.auction_date
            else None,
        },
        "items": items,
    }


@router.post("/notices/{notice_id}/bid-room/logs")
def crm_record_bid_room_log(
    notice_id: str,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissao insuficiente para registrar lance.",
        )

    product_id = payload.get("notice_product_id")
    if not product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="notice_product_id obrigatorio.",
        )

    product = (
        db.query(CrmNoticeProduct)
        .options(selectinload(CrmNoticeProduct.catalog_product))
        .filter(
            CrmNoticeProduct.id == product_id,
            CrmNoticeProduct.notice_id == notice_id,
            CrmNoticeProduct.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item do edital nao encontrado.",
        )

    current_best_bid = payload.get("current_best_bid")
    current_best_bid = float(current_best_bid) if current_best_bid not in (None, "") else None
    reference_price = (
        float(product.reference_price)
        if product.reference_price is not None
        else None
    )
    minimum = _minimum_viable_bid(product)
    suggested, status_value, message = _suggest_bid(
        current_best_bid=current_best_bid,
        reference_price=reference_price,
        minimum_viable_bid=minimum,
        decrement=float(payload.get("decrement") or DEFAULT_BID_DECREMENT),
    )
    requested_suggested = payload.get("suggested_bid")
    if requested_suggested not in (None, ""):
        suggested = float(requested_suggested)

    log = CrmBidAssistLog(
        tenant_id=current_user.tenant_id,
        notice_id=notice_id,
        notice_product_id=product.id,
        current_best_bid=current_best_bid,
        suggested_bid=suggested,
        minimum_viable_bid=minimum,
        reference_price=reference_price,
        quantity=product.quantity,
        decision=payload.get("decision") or status_value,
        authorized_by=current_user.id,
        notes=payload.get("notes") or message,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {
        "ok": True,
        "log": {
            "id": log.id,
            "current_best_bid": log.current_best_bid,
            "suggested_bid": log.suggested_bid,
            "minimum_viable_bid": log.minimum_viable_bid,
            "decision": log.decision,
            "notes": log.notes,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        },
    }


@router.get("/notices/{notice_id}/matches")
def crm_notice_matches(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return get_notice_item_match_payload(db, current_user, notice_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/notices/{notice_id}/matches/run")
def crm_run_notice_matches(
    notice_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _raise_match_paused()
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente para rodar o match.")
    payload = payload or {}
    try:
        return run_notice_item_match(
            db,
            current_user,
            notice_id,
            use_llm=payload.get("use_llm", True),
            notice_product_id=payload.get("notice_product_id"),
            category=payload.get("category"),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/notices/{notice_id}/decision-intelligence")
def crm_notice_decision_intelligence(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notice = (
        db.query(CrmNotice)
        .filter(CrmNotice.id == notice_id, CrmNotice.tenant_id == current_user.tenant_id)
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital CRM nao encontrado.")
    return {"data": serialize_decision_intelligence(notice)}


@router.post("/notices/{notice_id}/decision-intelligence/run")
def crm_run_notice_decision_intelligence(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    notice = (
        db.query(CrmNotice)
        .filter(CrmNotice.id == notice_id, CrmNotice.tenant_id == current_user.tenant_id)
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital CRM nao encontrado.")

    edital = None
    if notice.analysis_document_id:
        edital = None
    try:
        payload = persist_notice_decision_intelligence(
            db,
            notice_id=notice_id,
            edital=edital,
            user_id=current_user.id,
        )
        return {"data": payload}
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/notices/{notice_id}/matches/run-job")
def crm_run_notice_matches_job(
    notice_id: str,
    background_tasks: BackgroundTasks,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _raise_match_paused()
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente para rodar o match.")

    notice = (
        db.query(CrmNotice)
        .filter(CrmNotice.id == notice_id, CrmNotice.tenant_id == current_user.tenant_id)
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital CRM nao encontrado.")

    existing_job = next(
        (
            job
            for job in (
                db.query(Job)
                .filter(
                    Job.tenant_id == current_user.tenant.slug,
                    Job.job_type == JobType.CRM_NOTICE_MATCH,
                    Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
                )
                .order_by(Job.created_at.desc())
                .all()
            )
            if (job.payload or {}).get("notice_id") == notice_id
        ),
        None,
    )
    if existing_job:
        return {
            "job_id": existing_job.id,
            "notice_id": notice_id,
            "message": "Ja existe um match em andamento para este edital.",
            "status_url": f"/jobs/{existing_job.id}",
        }

    payload = payload or {}
    queue = JobQueue()
    job_id = queue.criar_job_crm_notice_match(
        background_tasks=background_tasks,
        notice_id=notice_id,
        tenant_id=current_user.tenant.slug,
        user_id=current_user.id,
        db=db,
        notice_product_id=payload.get("notice_product_id"),
        category=payload.get("category"),
        use_llm=bool(payload.get("use_llm", True)),
    )
    return {
        "job_id": job_id,
        "notice_id": notice_id,
        "message": "Match iniciado em segundo plano.",
        "status_url": f"/jobs/{job_id}",
    }


@router.get("/matches/jobs")
def crm_match_jobs(
    notice_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Job)
        .filter(
            Job.tenant_id == current_user.tenant.slug,
            Job.job_type == JobType.CRM_NOTICE_MATCH,
        )
        .order_by(Job.created_at.desc())
    )

    jobs = query.limit(limit).all()
    if notice_id:
        jobs = [job for job in jobs if (job.payload or {}).get("notice_id") == notice_id]
    return {
        "jobs": [
            {
                "id": job.id,
                "job_type": job.job_type.value if job.job_type else "",
                "status": job.status.value if job.status else "",
                "progress": job.progress or 0.0,
                "payload": job.payload,
                "result": job.result,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
            for job in jobs
        ]
    }


@router.get("/matches/ground-truth/report")
def crm_match_ground_truth_report(
    notice_id: str | None = Query(default=None),
    source: str | None = Query(default=None),
    include_unmarked: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    return build_match_ground_truth_report(
        db,
        current_user,
        notice_id=notice_id,
        source=source,
        limit=limit,
        include_unmarked=include_unmarked,
    )


@router.get("/matches/attached-products/report")
def crm_attached_products_report(
    notice_id: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    return build_attached_products_llm_report(
        db,
        current_user,
        notice_id=notice_id,
        limit=limit,
    )


@router.get("/matches/attached-products/report.csv")
def crm_attached_products_report_csv(
    notice_id: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=20000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    report = build_attached_products_llm_report(
        db,
        current_user,
        notice_id=notice_id,
        limit=limit,
    )
    rows = flatten_attached_products_report_items(report)
    output = StringIO()
    fieldnames = list(rows[0].keys()) if rows else [
        "notice_id",
        "notice_number",
        "notice_product_id",
        "item_description",
        "catalog_product_id",
        "catalog_name",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    filename = "attached-products-report.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/notice-products/{notice_product_id}/ground-truth")
def crm_mark_notice_product_ground_truth(
    notice_product_id: str,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    catalog_product_id = payload.get("catalog_product_id")
    if not catalog_product_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="catalog_product_id obrigatorio.")
    try:
        return mark_notice_product_ground_truth(
            db,
            current_user,
            notice_product_id,
            catalog_product_id,
            source=payload.get("source") or "manual_confirmed",
            notes=payload.get("notes"),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

@router.post("/matches/run-batch")
def crm_run_match_batch(
    background_tasks: BackgroundTasks,
    stage: str = Body(..., embed=True, description="Etapa do edital: triage|analysis|documentation|proposal|auction"),
    limit: int = Body(default=50, embed=True, ge=1, le=500),
    use_llm: bool = Body(default=True, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _raise_match_paused()
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente para rodar o match em lote.")

    try:
        stage_enum = CrmNoticeStage(stage)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Etapa invalida.") from exc

    notices = (
        db.query(CrmNotice)
        .options(selectinload(CrmNotice.notice_products))
        .filter(
            CrmNotice.tenant_id == current_user.tenant_id,
            CrmNotice.stage == stage_enum,
        )
        .order_by(CrmNotice.updated_at.desc())
        .limit(limit)
        .all()
    )

    queue = JobQueue()
    job_ids: list[str] = []
    skipped_existing: list[str] = []
    skipped_empty: list[str] = []

    # Pre-carrega jobs ativos para evitar N queries.
    active_jobs = (
        db.query(Job)
        .filter(
            Job.tenant_id == current_user.tenant.slug,
            Job.job_type == JobType.CRM_NOTICE_MATCH,
            Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
        )
        .order_by(Job.created_at.desc())
        .limit(500)
        .all()
    )
    active_notice_ids = {((job.payload or {}).get("notice_id") or "") for job in active_jobs}

    for notice in notices:
        if not (notice.notice_products or []):
            skipped_empty.append(notice.id)
            continue
        if notice.id in active_notice_ids:
            skipped_existing.append(notice.id)
            continue
        job_id = queue.criar_job_crm_notice_match(
            background_tasks=background_tasks,
            notice_id=notice.id,
            tenant_id=current_user.tenant.slug,
            user_id=current_user.id,
            db=db,
        )
        # Permite mudar o comportamento do job sem criar outro endpoint.
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is not None:
            job.payload = {**(job.payload or {}), "use_llm": bool(use_llm)}
            db.add(job)
        job_ids.append(job_id)

    db.commit()
    return {
        "ok": True,
        "stage": stage_enum.value,
        "requested": len(notices),
        "enqueued": len(job_ids),
        "skipped_existing": len(skipped_existing),
        "skipped_empty": len(skipped_empty),
        "job_ids": job_ids,
        "skipped_existing_notice_ids": skipped_existing,
        "skipped_empty_notice_ids": skipped_empty,
    }


@router.post("/matches/{match_id}/confirm")
def crm_confirm_match(
    match_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente para confirmar o match.")
    try:
        return confirm_notice_item_match(db, current_user, match_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/matches/{match_id}/reject")
def crm_reject_match(
    match_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente para rejeitar o match.")
    try:
        return reject_notice_item_match(db, current_user, match_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/query/{table_name}")
def crm_query_list(
    table_name: str,
    filters: str | None = Query(default=None),
    orders: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1),
    head: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_table(table_name)
    filter_values = _parse_json_param(filters, [])
    order_values = _parse_json_param(orders, [])

    try:
        data, count = list_records(
            db,
            current_user,
            table_name,
            filters=filter_values,
            orders=order_values,
            limit=limit,
            head=head,
        )
        return {"data": data, "count": count}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/query/{table_name}/insert")
def crm_query_insert(
    table_name: str,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_table(table_name)

    try:
        data = insert_records(db, current_user, table_name, payload.get("values", []))
        return {"data": data}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/query/{table_name}")
def crm_query_update(
    table_name: str,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_table(table_name)

    try:
        data = update_records(
            db,
            current_user,
            table_name,
            payload.get("values", {}),
            filters=payload.get("filters", []),
        )
        return {"data": data}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/query/{table_name}")
def crm_query_delete(
    table_name: str,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_table(table_name)
    payload = payload or {}

    try:
        deleted = delete_records(db, current_user, table_name, payload.get("filters", []))
        return {"deleted": deleted}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
