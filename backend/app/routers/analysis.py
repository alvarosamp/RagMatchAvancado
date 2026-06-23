from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.db.models import AnalysisDocument
from app.db.session import get_db
from app.services.analysis_store import persist_analysis_document

router = APIRouter(prefix="/analysis", tags=["analysis"])


class StoreAnalysisRequest(BaseModel):
    source_kind: str = Field(..., examples=["edital", "ata", "datasheet"])
    source_name: str | None = None
    full_text: str | None = None
    result: dict[str, Any]
    tokens_used: int = 0
    processing_ms: int | None = None
    status: str = "done"


@router.post("/documents")
def store_analysis_document(
    payload: StoreAnalysisRequest,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    document = persist_analysis_document(
        db,
        tenant_id=current_user.tenant_id,
        source_kind=payload.source_kind,
        source_name=payload.source_name,
        full_text=payload.full_text,
        result=payload.result,
        tokens_used=payload.tokens_used,
        processing_ms=payload.processing_ms,
        status=payload.status,
    )
    db.commit()
    return _serialize_document(document, include_items=True)


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


def _serialize_document(
    document: AnalysisDocument,
    *,
    include_items: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": document.id,
        "source_kind": document.source_kind,
        "source_name": document.source_name,
        "source_hash": document.source_hash,
        "status": document.status,
        "tokens_used": document.tokens_used,
        "processing_ms": document.processing_ms,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "items_count": len(document.items),
        "result": document.result if include_items else None,
    }
    if include_items:
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
                "raw_payload": item.raw_payload,
            }
            for item in document.items
        ]
    return payload
