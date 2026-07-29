from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.db.models import AnalysisDocument, Edital, ImportBatch
from app.db.session import get_db
from app.crm.json_analysis_importer import sync_analysis_json_to_crm
from app.crm.sales_process_importer import build_import_context_for_user
from app.services.analysis_export_service import export_analysis_pdf, export_analysis_report_pdf
from app.services.analysis_normalizer import normalize_analysis_result
from app.services.analysis_store import persist_analysis_document
from app.services.document_identity import is_unidentified_edital_result

router = APIRouter(prefix="/analysis", tags=["analysis"])

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")
PERIOD_LABELS = {
    "day": "Diario",
    "week": "Semanal",
    "month": "Mensal",
    "year": "Anual",
}


class StoreAnalysisRequest(BaseModel):
    source_kind: str = Field(..., examples=["edital", "ata", "datasheet"])
    source_name: str | None = None
    source_path: str | None = None
    full_text: str | None = None
    result: dict[str, Any]
    sync_targets: list[str] | None = None
    import_batch_id: int | None = None
    analysis_only: bool = False
    tokens_used: int = 0
    processing_ms: int | None = None
    status: str = "done"


class CreateImportBatchRequest(BaseModel):
    label: str
    source_path: str | None = None
    source_mode: str = "upload"
    analysis_only: bool = False
    sync_targets: list[str] | None = None
    total_files: int = 0


class DeleteImportBatchRequest(BaseModel):
    scope: str = Field(default="bi", examples=["bi", "all"])
    confirm: str | None = None


@router.post("/import-batches")
def create_import_batch(
    payload: CreateImportBatchRequest,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    label = payload.label.strip() or "Importacao"
    batch = ImportBatch(
        tenant_id=current_user.tenant_id,
        label=label,
        source_path=payload.source_path,
        source_mode=payload.source_mode,
        analysis_only=payload.analysis_only,
        sync_targets=payload.sync_targets if payload.sync_targets is not None else ([] if payload.analysis_only else ["crm"]),
        total_files=payload.total_files,
        created_by=current_user.id,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return _serialize_batch(db, batch)


@router.get("/import-batches")
def list_import_batches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    batches = (
        db.query(ImportBatch)
        .filter(ImportBatch.tenant_id == current_user.tenant_id)
        .order_by(ImportBatch.created_at.desc())
        .limit(80)
        .all()
    )
    return [_serialize_batch(db, batch) for batch in batches]


@router.get("/import-batches/{batch_id}")
def get_import_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    batch = _get_batch(db, batch_id, current_user.tenant_id)
    return _serialize_batch(db, batch, include_documents=True)


@router.delete("/import-batches/{batch_id}")
def delete_import_batch(
    batch_id: int,
    payload: DeleteImportBatchRequest,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    batch = _get_batch(db, batch_id, current_user.tenant_id)
    scope = payload.scope.strip().lower()
    if scope not in ("bi", "all"):
        raise HTTPException(status_code=400, detail="Escopo invalido. Use 'bi' ou 'all'.")
    if scope == "all" and payload.confirm != "APAGAR":
        raise HTTPException(status_code=400, detail="Para apagar BI + CRM, envie confirm='APAGAR'.")

    from app.crm.models import CrmNotice

    analysis_docs = (
        db.query(AnalysisDocument)
        .filter(
            AnalysisDocument.tenant_id == current_user.tenant_id,
            AnalysisDocument.import_batch_id == batch.id,
        )
        .all()
    )
    editais = (
        db.query(Edital)
        .filter(
            Edital.tenant_id == current_user.tenant.slug,
            Edital.import_batch_id == batch.id,
        )
        .all()
    )
    crm_notices = (
        db.query(CrmNotice)
        .filter(
            CrmNotice.tenant_id == current_user.tenant_id,
            CrmNotice.import_batch_id == batch.id,
        )
        .all()
        if scope == "all"
        else []
    )

    summary = {
        "batch_id": batch.id,
        "scope": scope,
        "analysis_documents_deleted": len(analysis_docs),
        "legacy_editais_deleted": len(editais),
        "crm_notices_deleted": len(crm_notices),
    }

    for document in analysis_docs:
        db.delete(document)
    for edital in editais:
        db.delete(edital)
    for notice in crm_notices:
        db.delete(notice)
    db.delete(batch)
    db.commit()
    return summary


@router.post("/documents")
def store_analysis_document(
    payload: StoreAnalysisRequest,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    result = (
        normalize_analysis_result(payload.result)
        if payload.source_kind == "edital"
        else payload.result
    )
    if payload.source_kind == "edital" and is_unidentified_edital_result(result):
        raise HTTPException(
            status_code=422,
            detail="Documento nao identificado. Informe n_interno ou dados do edital (pregao, orgao e data) antes de importar.",
        )

    crm_sync = None
    document, is_duplicate = persist_analysis_document(
        db,
        tenant_id=current_user.tenant_id,
        source_kind=payload.source_kind,
        source_name=payload.source_name,
        source_path=payload.source_path,
        full_text=payload.full_text,
        result=result,
        import_batch_id=payload.import_batch_id,
        analysis_only=payload.analysis_only,
        tokens_used=payload.tokens_used,
        processing_ms=payload.processing_ms,
        status=payload.status,
    )
    sync_targets = payload.sync_targets if payload.sync_targets is not None else ["crm"]
    if payload.source_kind == "edital" and "crm" in sync_targets:
        crm_sync = sync_analysis_json_to_crm(
            db,
            build_import_context_for_user(current_user),
            result,
            source_name=payload.source_name,
            import_batch_id=payload.import_batch_id,
            analysis_document_id=document.id,
            notify=not is_duplicate,
        )
        document.crm_notice_id = crm_sync.get("notice_id")
    db.commit()
    response = _serialize_document(document, include_items=True)
    response["crm_sync"] = crm_sync
    response["duplicate"] = is_duplicate
    return response


@router.get("/documents")
def list_analysis_documents(
    source_kind: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(AnalysisDocument).filter(
        AnalysisDocument.tenant_id == current_user.tenant_id
    )
    if source_kind:
        query = query.filter(AnalysisDocument.source_kind == source_kind)
    documents = query.order_by(AnalysisDocument.updated_at.desc()).limit(80).all()
    return [_serialize_document(document) for document in documents]


@router.get("/reports/export/pdf")
def export_analysis_report_pdf_endpoint(
    period: str = Query(default="month"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    period_key = _normalize_period(period)
    start_utc, end_utc = _period_bounds(period_key)
    query = db.query(AnalysisDocument).filter(
        AnalysisDocument.tenant_id == current_user.tenant_id,
        AnalysisDocument.source_kind == "edital",
    )
    query = query.filter(AnalysisDocument.created_at >= start_utc, AnalysisDocument.created_at < end_utc)
    documents = query.order_by(AnalysisDocument.created_at.desc()).limit(500).all()
    generated_at = datetime.now(BRASILIA_TZ).strftime("%d/%m/%Y %H:%M")
    filename = f"bi_editais_{period_key}_{datetime.now(BRASILIA_TZ).strftime('%Y%m%d')}.pdf"
    return Response(
        content=export_analysis_report_pdf(
            documents,
            period_label=PERIOD_LABELS[period_key],
            generated_at=generated_at,
        ),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/documents/{document_id}")
def get_analysis_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(AnalysisDocument)
        .filter(
            AnalysisDocument.id == document_id,
            AnalysisDocument.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Analise nao encontrada.")
    return _serialize_document(document, include_items=True)


@router.delete("/documents/{document_id}", status_code=204)
def delete_analysis_document(
    document_id: int,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    """Apaga um edital/JSON importado (e seus itens, via cascade). Não mexe no CRM já sincronizado."""
    document = (
        db.query(AnalysisDocument)
        .filter(
            AnalysisDocument.id == document_id,
            AnalysisDocument.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Analise nao encontrada.")
    db.delete(document)
    db.commit()
    return Response(status_code=204)


@router.get("/documents/{document_id}/export/pdf")
def export_analysis_document_pdf(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(AnalysisDocument)
        .filter(
            AnalysisDocument.id == document_id,
            AnalysisDocument.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Analise nao encontrada.")

    filename = f"bi_edital_analise_{document.id}.pdf"
    return Response(
        content=export_analysis_pdf(document),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _serialize_document(
    document: AnalysisDocument,
    *,
    include_items: bool = False,
) -> dict[str, Any]:
    result = document.result or {}
    edital_header = result.get("edital") or {}
    riscos = result.get("riscos") or {}
    payload: dict[str, Any] = {
        "id": document.id,
        "import_batch_id": document.import_batch_id,
        "source_kind": document.source_kind,
        "schema_name": document.schema_name,
        "schema_version": document.schema_version,
        "source_name": document.source_name,
        "source_path": document.source_path,
        "source_hash": document.source_hash,
        "business_key": document.business_key,
        "analysis_only": document.analysis_only,
        "crm_notice_id": document.crm_notice_id,
        "status": document.status,
        "tokens_used": document.tokens_used,
        "processing_ms": document.processing_ms,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "items_count": len(document.items),
        "edital": edital_header,
        "risco_identificado": riscos.get("risco_identificado"),
        "result": result if include_items else None,
    }
    if include_items:
        payload["riscos"] = riscos
        payload["documentacao"] = result.get("documentacao")
        payload["declaracoes"] = result.get("declaracoes")
        payload["items"] = [
            {
                "id": item.id,
                "item_number": item.item_number,
                "item_type": item.item_type,
                "description": item.description,
                "brand": item.brand,
                "model": item.model,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_value": item.unit_value,
                "total_value": item.total_value,
                "supplier": item.supplier,
                "supplier_tax_id": item.supplier_tax_id,
                "categoria": item.categoria,
                "uf": item.uf,
                "lote_grupo": item.lote_grupo,
                "garantia": item.garantia,
                "prazo_entrega": item.prazo_entrega,
                "caracteristicas_tecnicas": item.caracteristicas_tecnicas,
                "exclusividade_me_epp_item": item.exclusividade_me_epp_item,
                "risco_associado": item.risco_associado,
                "direcionamento_marca_tipo": item.direcionamento_marca_tipo,
                "direcionamento_marca_justificativa": item.direcionamento_marca_justificativa,
                "has_direcionamento_marca": item.has_direcionamento_marca,
                "has_risco": item.has_risco,
                "caracteristicas_bi": item.caracteristicas_bi,
                "raw_payload": item.raw_payload,
            }
            for item in document.items
        ]
    return payload


def _normalize_period(value: str) -> str:
    normalized = (value or "month").strip().lower()
    aliases = {
        "daily": "day",
        "diario": "day",
        "dia": "day",
        "weekly": "week",
        "semanal": "week",
        "semana": "week",
        "monthly": "month",
        "mensal": "month",
        "mes": "month",
        "annual": "year",
        "yearly": "year",
        "anual": "year",
        "ano": "year",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in PERIOD_LABELS:
        raise HTTPException(status_code=400, detail="Periodo invalido.")
    return normalized


def _period_bounds(period: str) -> tuple[datetime, datetime]:
    now = datetime.now(BRASILIA_TZ)
    today = now.date()
    if period == "day":
        start_date = today
        end_date = today + timedelta(days=1)
    elif period == "week":
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=7)
    elif period == "month":
        start_date = today.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
    else:
        start_date = today.replace(month=1, day=1)
        end_date = start_date.replace(year=start_date.year + 1)
    start = datetime.combine(start_date, time.min, tzinfo=BRASILIA_TZ)
    end = datetime.combine(end_date, time.min, tzinfo=BRASILIA_TZ)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _get_batch(db: Session, batch_id: int, tenant_id: int) -> ImportBatch:
    batch = (
        db.query(ImportBatch)
        .filter(ImportBatch.id == batch_id, ImportBatch.tenant_id == tenant_id)
        .first()
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Lote de importacao nao encontrado.")
    return batch


def _serialize_batch(
    db: Session,
    batch: ImportBatch,
    *,
    include_documents: bool = False,
) -> dict[str, Any]:
    from app.crm.models import CrmNotice

    analysis_query = db.query(AnalysisDocument).filter(
        AnalysisDocument.tenant_id == batch.tenant_id,
        AnalysisDocument.import_batch_id == batch.id,
    )
    editais_query = db.query(Edital).filter(Edital.import_batch_id == batch.id)
    crm_query = db.query(CrmNotice).filter(
        CrmNotice.tenant_id == batch.tenant_id,
        CrmNotice.import_batch_id == batch.id,
    )
    documents = analysis_query.order_by(AnalysisDocument.created_at.desc()).limit(200).all()
    errors = sum(1 for document in documents if document.status == "error")
    payload: dict[str, Any] = {
        "id": batch.id,
        "label": batch.label,
        "source_path": batch.source_path,
        "source_mode": batch.source_mode,
        "analysis_only": batch.analysis_only,
        "sync_targets": batch.sync_targets or [],
        "total_files": batch.total_files,
        "analysis_documents": analysis_query.count(),
        "legacy_editais": editais_query.count(),
        "crm_notices": crm_query.count(),
        "errors": errors,
        "status": batch.status,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
    }
    if include_documents:
        payload["documents"] = [
            {
                "id": document.id,
                "source_name": document.source_name,
                "source_path": document.source_path,
                "status": document.status,
                "business_key": document.business_key,
                "crm_notice_id": document.crm_notice_id,
                "created_at": document.created_at,
            }
            for document in documents
        ]
    return payload
