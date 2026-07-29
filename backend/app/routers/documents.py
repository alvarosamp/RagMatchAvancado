from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.crm.json_analysis_importer import sync_analysis_json_to_crm
from app.crm.sales_process_importer import build_import_context_for_user
from app.db.models import AnalysisDocument
from app.db.session import get_db
from app.services.document_platform import (
    list_document_schemas,
    store_structured_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


class StoreDocumentRequest(BaseModel):
    document_type: str = Field(..., examples=["edital", "datasheet_tor", "generic"])
    source_name: str | None = None
    full_text: str | None = None
    payload: dict[str, Any]
    schema_name: str | None = None
    schema_version: str | None = None
    sync_targets: list[str] | None = None
    tokens_used: int = 0
    processing_ms: int | None = None
    status: str = "done"


@router.get("/schemas")
def get_document_schemas(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_document_schemas(db, current_user.tenant_id)


@router.post("")
def store_document(
    payload: StoreDocumentRequest,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    document, is_duplicate, schema, normalized_payload = store_structured_document(
        db,
        tenant_id=current_user.tenant_id,
        document_type=payload.document_type,
        source_name=payload.source_name,
        full_text=payload.full_text,
        payload=payload.payload,
        schema_name=payload.schema_name,
        schema_version=payload.schema_version,
        tokens_used=payload.tokens_used,
        processing_ms=payload.processing_ms,
        status=payload.status,
    )

    crm_sync = None
    sync_targets = payload.sync_targets if payload.sync_targets is not None else list(schema.sync_targets)
    if not is_duplicate and payload.document_type.strip().lower() == "edital" and "crm" in sync_targets:
        crm_sync = sync_analysis_json_to_crm(
            db,
            build_import_context_for_user(current_user),
            normalized_payload,
            source_name=payload.source_name,
        )

    db.commit()
    response = _serialize_document(document, include_payload=True)
    response["duplicate"] = is_duplicate
    response["schema"] = schema.to_payload()
    response["crm_sync"] = crm_sync
    return response


@router.get("")
def list_documents(
    document_type: str | None = Query(default=None),
    schema_name: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(AnalysisDocument).filter(
        AnalysisDocument.tenant_id == current_user.tenant_id
    )
    if document_type:
        query = query.filter(AnalysisDocument.source_kind == document_type)
    if schema_name:
        query = query.filter(AnalysisDocument.schema_name == schema_name)
    documents = query.order_by(AnalysisDocument.updated_at.desc()).limit(100).all()
    return [_serialize_document(document) for document in documents]


@router.get("/{document_id}")
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _get_tenant_document(db, document_id, current_user.tenant_id)
    return _serialize_document(document, include_payload=True)


def _get_tenant_document(db: Session, document_id: int, tenant_id: int) -> AnalysisDocument:
    document = (
        db.query(AnalysisDocument)
        .filter(
            AnalysisDocument.id == document_id,
            AnalysisDocument.tenant_id == tenant_id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Documento nao encontrado.")
    return document


def _serialize_document(
    document: AnalysisDocument,
    *,
    include_payload: bool = False,
) -> dict[str, Any]:
    result = document.result or {}
    return {
        "id": document.id,
        "document_type": document.source_kind,
        "schema_name": document.schema_name,
        "schema_version": document.schema_version,
        "source_name": document.source_name,
        "source_hash": document.source_hash,
        "business_key": document.business_key,
        "status": document.status,
        "tokens_used": document.tokens_used,
        "processing_ms": document.processing_ms,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "items_count": len(document.items),
        "payload": result if include_payload else None,
    }
