from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from requests import RequestException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.crm.models import CrmNotice
from app.db.models import OpportunityDecision, Product
from app.db.session import get_db
from app.jobs.queue import JobQueue
from app.services.opportunity_crm import (
    pncp_file_name,
    pncp_file_url,
    send_opportunity_to_crm,
    sync_radar_items_to_crm,
    sync_pncp_files_to_crm,
)
from app.services.document_identity import content_hash
from app.services.opportunity_radar import (
    build_catalog_terms,
    predict_competitor_entries,
    score_opportunity,
    serialize_competitor_prediction,
    serialize_score,
)
from app.services.pncp_client import (
    download_file,
    get_purchase_detail,
    list_purchase_files,
    search_publications,
)
from app.services.pncp_radar_cache import (
    get_cached_notices,
    latest_cache_update,
    refresh_pncp_radar_cache,
)

router = APIRouter(prefix="/pncp", tags=["pncp"])
_queue = JobQueue()


class PncpImportRequest(BaseModel):
    id_pncp: str


class OpportunityDecisionRequest(BaseModel):
    id_pncp: str | None = None
    decision: str
    reason: str | None = None
    score: int | None = None
    priority: str | None = None
    notice: dict[str, Any] | None = None


ALLOWED_DECISIONS = {
    "disputar",
    "analisar",
    "descartar",
    "falso_positivo",
    "fora_segmento",
}


@router.get("/search")
def search_pncp(
    texto: str | None = None,
    cnpj: str | None = None,
    modalidade: str | None = None,
    dataInicio: str | None = None,
    dataFim: str | None = None,
    pagina: int = Query(1, ge=1),
    tamanhoPagina: int = Query(20, ge=10, le=50),
    maxPages: int = Query(1, ge=1, le=8),
    propostasAbertas: bool = False,
    current_user: User = Depends(get_current_user),
):
    try:
        return search_publications(
            texto=texto,
            cnpj=cnpj,
            modalidade=modalidade,
            data_inicio=dataInicio,
            data_fim=dataFim,
            pagina=pagina,
            tamanho_pagina=tamanhoPagina,
            propostas_abertas=propostasAbertas,
            max_pages=maxPages,
        )
    except RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao consultar o PNCP: {exc}",
        ) from exc


@router.get("/radar")
def radar_pncp(
    texto: str | None = None,
    cnpj: str | None = None,
    modalidade: str | None = None,
    dataInicio: str | None = None,
    dataFim: str | None = None,
    pagina: int = Query(1, ge=1),
    tamanhoPagina: int = Query(20, ge=10, le=50),
    maxPages: int = Query(5, ge=1, le=8),
    propostasAbertas: bool = True,
    minScore: int = Query(0, ge=0, le=100),
    useCache: bool = True,
    refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_summary = None
    cache_update = None
    source = "pncp-live"
    if refresh:
        try:
            cache_summary = refresh_pncp_radar_cache(
                db,
                max_pages=maxPages,
                tamanho_pagina=tamanhoPagina,
                propostas_abertas=propostasAbertas,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao atualizar o cache diario do Radar PNCP: {exc}",
            ) from exc

    if useCache:
        rows = get_cached_notices(db, limit=tamanhoPagina * maxPages, text_filter=texto)
        cache_update = latest_cache_update(db)
        payload = {
            "items": rows,
            "total": len(rows),
            "pagina": pagina,
            "paginas_restantes": 0,
            "paginas_varridas": 0,
            "source": "pncp-radar-cache",
        }
        source = "pncp-radar-cache"
    else:
        try:
            payload = search_publications(
                texto=texto,
                cnpj=cnpj,
                modalidade=modalidade,
                data_inicio=dataInicio,
                data_fim=dataFim,
                pagina=pagina,
                tamanho_pagina=tamanhoPagina,
                propostas_abertas=propostasAbertas,
                max_pages=maxPages,
            )
        except RequestException as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao consultar o PNCP: {exc}",
            ) from exc

    products = (
        db.query(Product)
        .filter(or_(Product.is_competitor.is_(False), Product.is_competitor.is_(None)))
        .all()
    )
    competitor_products = (
        db.query(Product)
        .filter(Product.is_competitor.is_(True))
        .all()
    )
    catalog_terms = build_catalog_terms(products)
    decisions = _decisions_by_id(db, current_user.tenant_id)
    opportunities: list[dict[str, Any]] = []
    for item in payload["items"]:
        score = score_opportunity(item, catalog_terms)
        if score.score < minScore:
            continue
        id_pncp = _item_id(item)
        opportunities.append({
            **item,
            "opportunity": serialize_score(score),
            "competitor_predictions": [
                serialize_competitor_prediction(prediction)
                for prediction in predict_competitor_entries(item, competitor_products)
            ],
            "decision": decisions.get(id_pncp),
        })

    opportunities.sort(key=lambda row: row["opportunity"]["score"], reverse=True)
    return {
        **payload,
        "items": opportunities,
        "catalog_terms_count": len(catalog_terms),
        "competitor_products_count": len(competitor_products),
        "scoring": "technical_fit 55%, commercial_fit 22%, urgency 13%, risk 10%",
        "source": source,
        "cache_last_update": cache_update.isoformat() if cache_update else None,
        "cache_refresh": cache_summary,
    }


@router.post("/radar/refresh")
def refresh_radar_cache(
    maxPages: int = Query(8, ge=1, le=8),
    tamanhoPagina: int = Query(50, ge=10, le=50),
    propostasAbertas: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    try:
        return refresh_pncp_radar_cache(
            db,
            max_pages=maxPages,
            tamanho_pagina=tamanhoPagina,
            propostas_abertas=propostasAbertas,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao atualizar Radar PNCP: {exc}",
        ) from exc


@router.get("/opportunities/decisions")
def list_opportunity_decisions(
    decision: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(OpportunityDecision)
        .filter(OpportunityDecision.tenant_id == current_user.tenant_id)
    )
    if decision:
        query = query.filter(OpportunityDecision.decision == decision)
    rows = (
        query
        .order_by(OpportunityDecision.updated_at.desc(), OpportunityDecision.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"items": [_serialize_decision(row, db=db) for row in rows]}


@router.post("/opportunities/decision")
def save_opportunity_decision(
    payload: OpportunityDecisionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    id_pncp = (payload.id_pncp or "").strip()
    if not id_pncp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o id_pncp da oportunidade.",
        )
    decision = payload.decision.strip().lower()
    if decision not in ALLOWED_DECISIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Decisao invalida. Use uma de: {', '.join(sorted(ALLOWED_DECISIONS))}.",
        )

    row = (
        db.query(OpportunityDecision)
        .filter(
            OpportunityDecision.tenant_id == current_user.tenant_id,
            OpportunityDecision.id_pncp == id_pncp,
        )
        .first()
    )
    if row is None:
        row = OpportunityDecision(
            tenant_id=current_user.tenant_id,
            id_pncp=id_pncp,
            created_by=current_user.id,
        )
        db.add(row)

    row.decision = decision
    row.reason = payload.reason
    row.score = payload.score
    row.priority = payload.priority
    row.notice_snapshot = payload.notice
    row.created_by = current_user.id
    if decision == "disputar":
        crm_notice = send_opportunity_to_crm(
            db,
            current_user=current_user,
            id_pncp=id_pncp,
            notice_payload=payload.notice,
            score=payload.score,
            priority=payload.priority,
        )
        row.crm_notice_id = crm_notice.id
        sync_radar_items_to_crm(
            db,
            notice=crm_notice,
            current_user=current_user,
            radar_items=(payload.notice or {}).get("radar_items") or [],
        )
        _try_import_pncp_documents(
            db=db,
            row=row,
            crm_notice=crm_notice,
            id_pncp=id_pncp,
            background_tasks=background_tasks,
            current_user=current_user,
        )

    db.commit()
    db.refresh(row)
    return _serialize_decision(row, db=db)


@router.get("/{id_pncp:path}")
def pncp_detail(
    id_pncp: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return get_purchase_detail(id_pncp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao consultar detalhe no PNCP: {exc}") from exc


@router.post("/import", status_code=202)
def import_pncp_notice(
    payload: PncpImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    try:
        files = list_purchase_files(payload.id_pncp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao listar arquivos no PNCP: {exc}") from exc

    pdf_file = _choose_pdf_file(files)
    if not pdf_file:
        raise HTTPException(status_code=404, detail="Nenhum PDF do edital encontrado para esta contratacao no PNCP.")

    url = pdf_file.get("url") or pdf_file.get("link") or pdf_file.get("uri")
    if not url:
        raise HTTPException(status_code=404, detail="Arquivo encontrado sem URL de download.")

    try:
        pdf_bytes = download_file(url)
    except RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao baixar PDF do PNCP: {exc}") from exc

    filename = pdf_file.get("nome") or pdf_file.get("titulo") or f"{payload.id_pncp}.pdf"
    if not str(filename).lower().endswith(".pdf"):
        filename = f"{filename}.pdf"

    job_id = _queue.criar_job_upload(
        background_tasks=background_tasks,
        pdf_bytes=pdf_bytes,
        filename=str(filename),
        tenant_id=current_user.tenant.slug,
        user_id=current_user.id,
        db=db,
        source_hash=content_hash(pdf_bytes),
        analysis_only=False,
        source_path=url,
    )
    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"Edital PNCP {payload.id_pncp} importado para processamento.",
    }


def _choose_pdf_file(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not files:
        return None
    preferred_terms = ("edital", "termo de referencia", "termo de referência", "tr")
    pdfs = [item for item in files if ".pdf" in " ".join(str(value).lower() for value in item.values())]
    if not pdfs:
        pdfs = files
    for item in pdfs:
        text = " ".join(str(value).lower() for value in item.values())
        if any(term in text for term in preferred_terms):
            return item
    return pdfs[0]


def _try_import_pncp_documents(
    *,
    db: Session,
    row: OpportunityDecision,
    crm_notice: Any,
    id_pncp: str,
    background_tasks: BackgroundTasks,
    current_user: User,
) -> None:
    try:
        files = list_purchase_files(id_pncp)
        row.pncp_files_count = sync_pncp_files_to_crm(
            db,
            notice=crm_notice,
            current_user=current_user,
            files=files,
        )
        pdf_file = _choose_pdf_file(files)
        if not pdf_file:
            row.import_error = "Nenhum PDF principal encontrado no PNCP."
            crm_notice.analysis_status = "Documentos PNCP localizados; PDF principal nao identificado"
            return

        url = pncp_file_url(pdf_file)
        if not url:
            row.import_error = "Arquivo PDF principal sem URL de download."
            crm_notice.analysis_status = "PDF principal sem URL de download"
            return

        pdf_bytes = download_file(url)
        filename = pncp_file_name(pdf_file)
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
        row.import_job_id = _queue.criar_job_upload(
            background_tasks=background_tasks,
            pdf_bytes=pdf_bytes,
            filename=filename,
            tenant_id=current_user.tenant.slug,
            user_id=current_user.id,
            db=db,
            source_hash=content_hash(pdf_bytes),
            analysis_only=False,
            source_path=url,
            crm_notice_id=crm_notice.id,
        )
        row.import_error = None
        crm_notice.analysis_status = "Analise de edital enfileirada"
    except (RequestException, ValueError) as exc:
        row.import_error = f"Falha ao importar documentos PNCP: {exc}"
        crm_notice.analysis_status = "Falha ao importar documentos PNCP"


def _item_id(item: dict[str, Any]) -> str | None:
    value = item.get("id_pncp") or item.get("numero_controle") or item.get("numeroControlePNCP")
    return str(value) if value else None


def _decisions_by_id(db: Session, tenant_id: int) -> dict[str | None, dict[str, Any]]:
    rows = (
        db.query(OpportunityDecision)
        .filter(OpportunityDecision.tenant_id == tenant_id)
        .all()
    )
    return {row.id_pncp: _serialize_decision(row, db=db) for row in rows}


def _serialize_decision(row: OpportunityDecision, db: Session | None = None) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "id_pncp": row.id_pncp,
        "score": row.score,
        "priority": row.priority,
        "decision": row.decision,
        "reason": row.reason,
        "crm_notice_id": row.crm_notice_id,
        "import_job_id": row.import_job_id,
        "pncp_files_count": row.pncp_files_count,
        "import_error": row.import_error,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if db is not None and row.crm_notice_id:
        notice = db.get(CrmNotice, row.crm_notice_id)
        if notice is not None:
            payload["decision_intelligence"] = notice.decision_intelligence
            payload["decision_recommendation"] = notice.decision_recommendation
            payload["decision_score"] = notice.decision_score
            payload["decision_risk_score"] = notice.decision_risk_score
    return payload
