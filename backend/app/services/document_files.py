from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import Tenant, User
from app.crm.models import CrmNotice
from app.db.models import (
    DocumentFile,
    DocumentSignatureRequest,
    DocumentSignatureStatus,
    Edital,
)


DEFAULT_DOCUMENTS_ROOT = r"D:\TOR\Documentos" if os.name == "nt" else "/data/documents"
DOCUMENT_LIBRARY_ROOT = Path(os.getenv("TOR_DOCUMENTS_ROOT", DEFAULT_DOCUMENTS_ROOT))
MAX_DOCUMENT_UPLOAD_BYTES = int(os.getenv("MAX_DOCUMENT_UPLOAD_BYTES", str(50 * 1024 * 1024)))


def store_document_file(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    fileobj: BinaryIO,
    original_filename: str,
    content_type: str | None = None,
    title: str | None = None,
    category: str | None = None,
    crm_notice_id: str | None = None,
    edital_id: int | None = None,
    parent_document_id: str | None = None,
    notes: str | None = None,
    expires_at: datetime | None = None,
    status_value: str = "active",
) -> DocumentFile:
    safe_name = _safe_filename(original_filename)
    parent = _get_parent_document(db, tenant_id, parent_document_id)
    if crm_notice_id:
        _get_tenant_notice(db, tenant_id, crm_notice_id)
    if edital_id is not None:
        _get_tenant_edital(db, tenant_id, edital_id)
    version = _next_version(db, tenant_id, parent.id if parent else None)
    document_id = str(uuid.uuid4())
    stored_filename = f"{document_id}_{safe_name}"
    tenant_dir = DOCUMENT_LIBRARY_ROOT / f"tenant_{tenant_id}"
    tenant_dir.mkdir(parents=True, exist_ok=True)
    storage_path = tenant_dir / stored_filename

    size_bytes = 0
    try:
        with storage_path.open("wb") as output:
            size_bytes = _copy_stream(fileobj, output, MAX_DOCUMENT_UPLOAD_BYTES)
    except HTTPException:
        storage_path.unlink(missing_ok=True)
        raise

    document = DocumentFile(
        id=document_id,
        tenant_id=tenant_id,
        title=(title or Path(safe_name).stem or safe_name).strip(),
        original_filename=safe_name,
        stored_filename=stored_filename,
        storage_path=str(storage_path),
        content_type=content_type,
        size_bytes=size_bytes,
        category=(category or None),
        status=status_value,
        version=version,
        parent_document_id=parent.id if parent else None,
        crm_notice_id=crm_notice_id or None,
        edital_id=edital_id,
        uploaded_by=user_id,
        notes=notes,
        expires_at=expires_at,
    )
    db.add(document)
    return document


def attach_document_to_targets(
    db: Session,
    document: DocumentFile,
    *,
    tenant_id: int,
    crm_notice_id: str | None = None,
    edital_id: int | None = None,
) -> DocumentFile:
    if crm_notice_id:
        _get_tenant_notice(db, tenant_id, crm_notice_id)
        document.crm_notice_id = crm_notice_id
    if edital_id is not None:
        _get_tenant_edital(db, tenant_id, edital_id)
        document.edital_id = edital_id
    return document


def create_signature_request(
    db: Session,
    *,
    tenant_id: int,
    document_id: str,
    requester_id: int,
    signer_id: int,
    message: str | None = None,
) -> DocumentSignatureRequest:
    document = get_tenant_document_file(db, tenant_id, document_id)
    signer = db.query(User).filter(User.id == signer_id, User.tenant_id == tenant_id).first()
    if signer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assinante nao encontrado.")
    request = DocumentSignatureRequest(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        document_id=document.id,
        requester_id=requester_id,
        signer_id=signer_id,
        message=message,
    )
    document.status = "signature_pending"
    db.add(request)
    return request


def complete_signature_request(
    db: Session,
    *,
    tenant_id: int,
    request_id: str,
    signer_id: int,
    fileobj: BinaryIO,
    original_filename: str,
    content_type: str | None,
    notes: str | None = None,
) -> DocumentSignatureRequest:
    request = get_tenant_signature_request(db, tenant_id, request_id)
    if request.signer_id != signer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Somente o assinante pode enviar este documento.")
    if request.status != DocumentSignatureStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solicitacao ja finalizada.")

    signed = store_document_file(
        db,
        tenant_id=tenant_id,
        user_id=signer_id,
        fileobj=fileobj,
        original_filename=original_filename,
        content_type=content_type,
        title=f"{request.document.title} - assinado",
        category=request.document.category or "Assinado",
        crm_notice_id=request.document.crm_notice_id,
        edital_id=request.document.edital_id,
        parent_document_id=request.document_id,
        notes=notes,
        expires_at=request.document.expires_at,
        status_value="signed_result",
    )
    request.signed_document_id = signed.id
    request.status = DocumentSignatureStatus.SIGNED
    request.document.status = "signed"
    request.signed_at = datetime.utcnow()
    return request


def get_tenant_document_file(db: Session, tenant_id: int, document_id: str) -> DocumentFile:
    document = (
        db.query(DocumentFile)
        .filter(DocumentFile.id == document_id, DocumentFile.tenant_id == tenant_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento nao encontrado.")
    return document


def get_tenant_signature_request(db: Session, tenant_id: int, request_id: str) -> DocumentSignatureRequest:
    request = (
        db.query(DocumentSignatureRequest)
        .filter(DocumentSignatureRequest.id == request_id, DocumentSignatureRequest.tenant_id == tenant_id)
        .first()
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitacao nao encontrada.")
    return request


def serialize_document_file(document: DocumentFile) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "category": document.category,
        "status": document.status,
        "version": document.version,
        "parent_document_id": document.parent_document_id,
        "crm_notice_id": document.crm_notice_id,
        "edital_id": document.edital_id,
        "uploaded_by": document.uploaded_by,
        "notes": document.notes,
        "expires_at": document.expires_at,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "download_url": f"/api/documents/files/{document.id}/download",
    }


def serialize_signature_request(request: DocumentSignatureRequest) -> dict:
    document = request.document
    signed_document = request.signed_document
    return {
        "id": request.id,
        "status": request.status.value if hasattr(request.status, "value") else request.status,
        "message": request.message,
        "requester_id": request.requester_id,
        "signer_id": request.signer_id,
        "signer_notification_dismissed": request.signer_notification_dismissed,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
        "signed_at": request.signed_at,
        "document": serialize_document_file(document) if document else None,
        "signed_document": serialize_document_file(signed_document) if signed_document else None,
    }


def _copy_stream(source: BinaryIO, target: BinaryIO, max_bytes: int) -> int:
    before = target.tell()
    total = 0
    while True:
        chunk = source.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Arquivo excede o limite de {max_bytes // (1024 * 1024)} MB.",
            )
        target.write(chunk)
    return target.tell() - before


def _safe_filename(value: str | None) -> str:
    name = Path(value or "documento").name.strip() or "documento"
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:180]


def _get_parent_document(db: Session, tenant_id: int, parent_document_id: str | None) -> DocumentFile | None:
    if not parent_document_id:
        return None
    return get_tenant_document_file(db, tenant_id, parent_document_id)


def _next_version(db: Session, tenant_id: int, parent_document_id: str | None) -> int:
    if not parent_document_id:
        return 1
    latest = (
        db.query(DocumentFile)
        .filter(
            DocumentFile.tenant_id == tenant_id,
            DocumentFile.parent_document_id == parent_document_id,
        )
        .order_by(DocumentFile.version.desc())
        .first()
    )
    return int((latest.version if latest else 1) or 1) + 1


def _get_tenant_notice(db: Session, tenant_id: int, notice_id: str) -> CrmNotice:
    notice = db.query(CrmNotice).filter(CrmNotice.id == notice_id, CrmNotice.tenant_id == tenant_id).first()
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital CRM nao encontrado.")
    return notice


def _get_tenant_edital(db: Session, tenant_id: int, edital_id: int) -> Edital:
    edital = db.query(Edital).filter(Edital.id == edital_id).first()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    tenant_slug = tenant.slug if tenant else None
    if edital is None or (tenant_slug and edital.tenant_id != tenant_slug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital nao encontrado.")
    return edital
