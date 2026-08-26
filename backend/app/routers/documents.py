from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.crm.json_analysis_importer import sync_analysis_json_to_crm
from app.crm.sales_process_importer import build_import_context_for_user
from app.crm.models import CrmNoticeProductDatasheet
from app.db.models import AnalysisDocument, DocumentFile, DocumentSignatureRequest, DocumentSignatureStatus
from app.db.session import get_db
from app.services.document_files import (
    attach_document_to_targets,
    complete_signature_request,
    delete_document_file,
    create_signature_request,
    get_tenant_document_file,
    get_tenant_signature_request,
    serialize_document_file,
    serialize_signature_request,
    store_document_file,
)
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


class AttachDocumentRequest(BaseModel):
    crm_notice_id: str | None = None
    edital_id: int | None = None


class SignatureRequestPayload(BaseModel):
    signer_id: int
    message: str | None = None


class UpdateDocumentFileRequest(BaseModel):
    title: str | None = None
    category: str | None = None
    notes: str | None = None
    expires_at: datetime | None = None


@router.get("/schemas")
def get_document_schemas(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_document_schemas(db, current_user.tenant_id)


@router.get("/signers")
def list_signature_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    users = (
        db.query(User)
        .filter(User.tenant_id == current_user.tenant_id, User.is_active.is_(True))
        .order_by(User.full_name.asc(), User.email.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "email": row.email,
            "full_name": row.full_name,
            "role": row.role,
        }
        for row in users
    ]


@router.get("/files")
def list_document_files(
    crm_notice_id: str | None = Query(default=None),
    edital_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(DocumentFile).filter(DocumentFile.tenant_id == current_user.tenant_id)
    if crm_notice_id:
        linked_ids = db.query(CrmNoticeProductDatasheet.document_file_id).filter(
            CrmNoticeProductDatasheet.tenant_id == current_user.tenant_id,
            CrmNoticeProductDatasheet.notice_id == crm_notice_id,
            CrmNoticeProductDatasheet.document_file_id.is_not(None),
        )
        query = query.filter((DocumentFile.crm_notice_id == crm_notice_id) | DocumentFile.id.in_(linked_ids))
    if edital_id is not None:
        query = query.filter(DocumentFile.edital_id == edital_id)
    if status_filter:
        query = query.filter(DocumentFile.status == status_filter)
    rows = query.order_by(DocumentFile.updated_at.desc(), DocumentFile.created_at.desc()).limit(200).all()
    return [serialize_document_file(row) for row in rows]


@router.get("/files/notice/{notice_id}/download-all")
def download_all_notice_files(
    notice_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Gera o ZIP apenas em memoria, incluindo os datasheets vinculados aos itens."""
    linked_ids = db.query(CrmNoticeProductDatasheet.document_file_id).filter(
        CrmNoticeProductDatasheet.tenant_id == current_user.tenant_id,
        CrmNoticeProductDatasheet.notice_id == notice_id,
        CrmNoticeProductDatasheet.document_file_id.is_not(None),
    )
    documents = db.query(DocumentFile).filter(
        DocumentFile.tenant_id == current_user.tenant_id,
        (DocumentFile.crm_notice_id == notice_id) | DocumentFile.id.in_(linked_ids),
    ).order_by(DocumentFile.title.asc(), DocumentFile.version.desc()).all()
    if not documents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nao ha arquivos vinculados a este edital.")

    archive = BytesIO()
    used_names: set[str] = set()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zip_file:
        for document in documents:
            path = Path(document.storage_path)
            if not path.is_file():
                continue
            name = _zip_entry_name(document.original_filename, document.id, used_names)
            zip_file.write(path, arcname=name)
    if not used_names:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Os arquivos vinculados nao estao mais disponiveis.")
    archive.seek(0)
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="documentacao_{notice_id}.zip"'},
    )


@router.post("/files")
async def upload_document_file(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    category: str | None = Form(default=None),
    crm_notice_id: str | None = Form(default=None),
    edital_id: int | None = Form(default=None),
    parent_document_id: str | None = Form(default=None),
    catalog_product_id: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    expires_at: datetime | None = Form(default=None),
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    try:
        document = store_document_file(
            db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            fileobj=file.file,
            original_filename=file.filename or "documento",
            content_type=file.content_type,
            title=title,
            category=category,
            crm_notice_id=crm_notice_id,
            edital_id=edital_id,
            parent_document_id=parent_document_id,
            catalog_product_id=catalog_product_id,
            notes=notes,
            expires_at=expires_at,
        )
        if crm_notice_id or edital_id is not None:
            attach_document_to_targets(
                db,
                document,
                tenant_id=current_user.tenant_id,
                crm_notice_id=crm_notice_id,
                edital_id=edital_id,
            )
        db.commit()
        db.refresh(document)
        return serialize_document_file(document)
    finally:
        await file.close()


@router.post("/files/{document_id}/versions")
async def upload_document_version(
    document_id: str,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    parent = get_tenant_document_file(db, current_user.tenant_id, document_id)
    try:
        document = store_document_file(
            db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            fileobj=file.file,
            original_filename=file.filename or parent.original_filename,
            content_type=file.content_type,
            title=title or parent.title,
            category=parent.category,
            crm_notice_id=parent.crm_notice_id,
            edital_id=parent.edital_id,
            parent_document_id=parent.id,
            catalog_product_id=parent.catalog_product_id,
            notes=notes,
            expires_at=parent.expires_at,
        )
        db.commit()
        db.refresh(document)
        return serialize_document_file(document)
    finally:
        await file.close()


@router.post("/files/{document_id}/attach")
def attach_document_file(
    document_id: str,
    payload: AttachDocumentRequest,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    document = get_tenant_document_file(db, current_user.tenant_id, document_id)
    attach_document_to_targets(
        db,
        document,
        tenant_id=current_user.tenant_id,
        crm_notice_id=payload.crm_notice_id,
        edital_id=payload.edital_id,
    )
    db.commit()
    db.refresh(document)
    return serialize_document_file(document)


def _zip_entry_name(original_filename: str, document_id: str, used_names: set[str]) -> str:
    safe = Path(original_filename).name or f"documento_{document_id}"
    candidate = safe
    index = 2
    while candidate.lower() in used_names:
        suffix = Path(safe).suffix
        candidate = f"{Path(safe).stem} ({index}){suffix}"
        index += 1
    used_names.add(candidate.lower())
    return candidate


@router.patch("/files/{document_id}")
def update_document_file(
    document_id: str,
    payload: UpdateDocumentFileRequest,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    document = get_tenant_document_file(db, current_user.tenant_id, document_id)
    fields = payload.model_fields_set if hasattr(payload, "model_fields_set") else payload.__fields_set__
    if "title" in fields and payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Titulo do documento nao pode ficar vazio.")
        document.title = title
    if "category" in fields:
        document.category = payload.category.strip() or None
    if "notes" in fields:
        document.notes = payload.notes.strip() or None
    if "expires_at" in fields:
        document.expires_at = payload.expires_at
    db.commit()
    db.refresh(document)
    return serialize_document_file(document)


@router.delete("/files/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    delete_document_file(db, tenant_id=current_user.tenant_id, document_id=document_id)
    db.commit()


@router.get("/files/{document_id}/download")
def download_document_file(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_tenant_document_file(db, current_user.tenant_id, document_id)
    path = Path(document.storage_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo fisico nao encontrado.")
    return FileResponse(
        path,
        media_type=document.content_type or "application/octet-stream",
        filename=document.original_filename,
    )


@router.post("/files/{document_id}/signature-requests")
def request_document_signature(
    document_id: str,
    payload: SignatureRequestPayload,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    request = create_signature_request(
        db,
        tenant_id=current_user.tenant_id,
        document_id=document_id,
        requester_id=current_user.id,
        signer_id=payload.signer_id,
        message=payload.message,
    )
    db.commit()
    db.refresh(request)
    return serialize_signature_request(request)


@router.get("/signature-requests")
def list_signature_requests(
    role: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(DocumentSignatureRequest)
        .options(
            selectinload(DocumentSignatureRequest.document),
            selectinload(DocumentSignatureRequest.signed_document),
        )
        .filter(DocumentSignatureRequest.tenant_id == current_user.tenant_id)
    )
    if role == "signer":
        query = query.filter(DocumentSignatureRequest.signer_id == current_user.id)
    elif role == "requester":
        query = query.filter(DocumentSignatureRequest.requester_id == current_user.id)
    elif role is None:
        query = query.filter(
            (DocumentSignatureRequest.signer_id == current_user.id)
            | (DocumentSignatureRequest.requester_id == current_user.id)
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Perfil de listagem invalido.")

    if status_filter:
        try:
            status_value = DocumentSignatureStatus(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status de assinatura invalido.") from exc
        query = query.filter(DocumentSignatureRequest.status == status_value)

    rows = query.order_by(DocumentSignatureRequest.updated_at.desc()).limit(100).all()
    return [serialize_signature_request(row) for row in rows]


@router.get("/signature-alert")
def signature_alert(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pending_query = (
        db.query(DocumentSignatureRequest)
        .options(selectinload(DocumentSignatureRequest.document))
        .filter(
            DocumentSignatureRequest.tenant_id == current_user.tenant_id,
            DocumentSignatureRequest.signer_id == current_user.id,
            DocumentSignatureRequest.status == DocumentSignatureStatus.PENDING,
        )
    )
    pending_count = pending_query.count()
    pending = (
        pending_query.filter(DocumentSignatureRequest.signer_notification_dismissed.is_(False))
        .order_by(DocumentSignatureRequest.created_at.asc())
        .first()
    )
    if pending is not None:
        return {"count": pending_count, "kind": "signature_requested", "request": serialize_signature_request(pending)}

    signed_query = (
        db.query(DocumentSignatureRequest)
        .options(
            selectinload(DocumentSignatureRequest.document),
            selectinload(DocumentSignatureRequest.signed_document),
        )
        .filter(
            DocumentSignatureRequest.tenant_id == current_user.tenant_id,
            DocumentSignatureRequest.requester_id == current_user.id,
            DocumentSignatureRequest.status == DocumentSignatureStatus.SIGNED,
        )
    )
    signed_count = signed_query.count()
    signed = (
        signed_query.filter(DocumentSignatureRequest.requester_notification_dismissed.is_(False))
        .order_by(DocumentSignatureRequest.signed_at.desc(), DocumentSignatureRequest.updated_at.desc())
        .first()
    )
    return {
        "count": signed_count,
        "kind": "signed_document" if signed is not None else None,
        "request": serialize_signature_request(signed) if signed else None,
    }


@router.post("/signature-requests/{request_id}/dismiss")
def dismiss_signature_notification(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = get_tenant_signature_request(db, current_user.tenant_id, request_id)
    if request.signer_id == current_user.id and request.status == DocumentSignatureStatus.PENDING:
        request.signer_notification_dismissed = True
    elif request.requester_id == current_user.id and request.status == DocumentSignatureStatus.SIGNED:
        request.requester_notification_dismissed = True
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Aviso pertence a outro usuario.")
    db.commit()
    return {"ok": True}


@router.post("/signature-requests/{request_id}/signed")
async def upload_signed_document(
    request_id: str,
    file: UploadFile = File(...),
    notes: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        request = complete_signature_request(
            db,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            signer_id=current_user.id,
            fileobj=file.file,
            original_filename=file.filename or "documento_assinado",
            content_type=file.content_type,
            notes=notes,
        )
        db.commit()
        db.refresh(request)
        return serialize_signature_request(request)
    finally:
        await file.close()


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
