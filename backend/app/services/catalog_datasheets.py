"""Armazenamento privado de datasheets do catalogo (nao usa document_files)."""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crm.models import CrmCatalogProduct, CrmCatalogProductDatasheet, CrmChecklistStatus, CrmNoticeDocument, CrmNoticeProductDatasheet
from app.db.models import DocumentFile

ROOT = Path(os.getenv("TOR_CATALOG_DATASHEETS_ROOT", r"D:\TOR\CatalogDatasheets" if os.name == "nt" else "/data/catalog_datasheets"))
MAX_BYTES = int(os.getenv("MAX_DOCUMENT_UPLOAD_BYTES", str(50 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def store_catalog_datasheet(db: Session, *, tenant_id: int, user_id: int, product_id: str, fileobj: BinaryIO, filename: str, content_type: str | None) -> CrmCatalogProductDatasheet:
    product = _product(db, tenant_id, product_id)
    safe_name = _safe_name(filename)
    if Path(safe_name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Envie um datasheet em PDF ou DOCX.")
    previous = current_catalog_datasheet(db, tenant_id=tenant_id, product_id=product.id)
    version = (previous.version if previous else 0) + 1
    item_id = str(uuid.uuid4())
    directory = ROOT / f"tenant_{tenant_id}" / product.id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{item_id}_{safe_name}"
    total = 0
    try:
        with path.open("wb") as output:
            while chunk := fileobj.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Datasheet excede o limite permitido.")
                output.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    row = CrmCatalogProductDatasheet(id=item_id, tenant_id=tenant_id, catalog_product_id=product.id, original_filename=safe_name, stored_filename=path.name, storage_path=str(path), content_type=content_type, size_bytes=total, version=version, parent_datasheet_id=previous.id if previous else None, uploaded_by=user_id)
    db.add(row)
    db.flush()
    sync_product_datasheet_links(db, tenant_id=tenant_id, product_id=product.id, datasheet=row)
    return row


def current_catalog_datasheet(db: Session, *, tenant_id: int, product_id: str) -> CrmCatalogProductDatasheet | None:
    return db.query(CrmCatalogProductDatasheet).filter(CrmCatalogProductDatasheet.tenant_id == tenant_id, CrmCatalogProductDatasheet.catalog_product_id == product_id).order_by(CrmCatalogProductDatasheet.version.desc()).first()


def sync_product_datasheet_links(db: Session, *, tenant_id: int, product_id: str, datasheet: CrmCatalogProductDatasheet | None = None) -> None:
    current = datasheet or current_catalog_datasheet(db, tenant_id=tenant_id, product_id=product_id)
    for link in db.query(CrmNoticeProductDatasheet).filter(CrmNoticeProductDatasheet.tenant_id == tenant_id, CrmNoticeProductDatasheet.catalog_product_id == product_id).all():
        document = db.get(CrmNoticeDocument, link.notice_document_id) if link.notice_document_id else None
        if document:
            attach_catalog_datasheet_to_notice_document(db, link=link, document=document, datasheet=current)


def attach_catalog_datasheet_to_notice_document(
    db: Session,
    *,
    link: CrmNoticeProductDatasheet,
    document: CrmNoticeDocument,
    datasheet: CrmCatalogProductDatasheet | None,
) -> DocumentFile | None:
    """Materializa o datasheet privado como anexo real do checklist do edital."""
    previous_datasheet_id = link.catalog_datasheet_id
    previous_document_id = link.document_file_id
    link.catalog_datasheet_id = datasheet.id if datasheet else None

    if datasheet is None:
        if previous_document_id:
            previous = db.get(DocumentFile, previous_document_id)
            expected_prefix = f"catalog-datasheet:{link.notice_product_id}:"
            if previous and str(previous.generation_key or "").startswith(expected_prefix):
                previous.crm_notice_id = None
        link.document_file_id = None
        document.attached_document_file_id = None
        document.source_url = None
        document.status = CrmChecklistStatus.PENDING
        return None

    generation_key = f"catalog-datasheet:{link.notice_product_id}:{datasheet.id}"
    attached = db.query(DocumentFile).filter(
        DocumentFile.tenant_id == link.tenant_id,
        DocumentFile.generation_key == generation_key,
    ).first()
    if attached is None:
        # Importacao local evita acoplamento circular entre os dois servicos.
        from app.services.document_files import store_document_file

        parent_id = previous_document_id if previous_document_id else None
        with Path(datasheet.storage_path).open("rb") as source:
            attached = store_document_file(
                db,
                tenant_id=link.tenant_id,
                user_id=datasheet.uploaded_by,
                fileobj=source,
                original_filename=datasheet.original_filename,
                content_type=datasheet.content_type,
                title=document.name,
                category=document.category or "Datasheets de produtos",
                crm_notice_id=link.notice_id,
                parent_document_id=parent_id,
                notes=document.notes,
                generation_key=generation_key,
            )
        # O produto e associado depois da copia para nao disparar o sincronismo
        # global de DocumentFile, pois cada edital precisa do seu proprio anexo.
        attached.catalog_product_id = link.catalog_product_id

    link.document_file_id = attached.id
    should_replace_attachment = (
        previous_datasheet_id != datasheet.id
        or not previous_document_id
        or not document.attached_document_file_id
        or document.attached_document_file_id == previous_document_id
    )
    if should_replace_attachment:
        document.attached_document_file_id = attached.id

    if previous_document_id and previous_document_id != attached.id:
        previous = db.get(DocumentFile, previous_document_id)
        expected_prefix = f"catalog-datasheet:{link.notice_product_id}:"
        if previous and str(previous.generation_key or "").startswith(expected_prefix):
            # A versao antiga continua na biblioteca, mas deixa de entrar no ZIP
            # e na lista de anexos vigentes deste edital.
            previous.crm_notice_id = None

    document.source_kind = "catalog_datasheet"
    document.source_url = f"/api/crm/catalog-datasheets/{datasheet.id}/download"
    document.status = CrmChecklistStatus.READY
    return attached


def serialize(row: CrmCatalogProductDatasheet) -> dict:
    return {"id": row.id, "catalog_product_id": row.catalog_product_id, "original_filename": row.original_filename, "content_type": row.content_type, "size_bytes": row.size_bytes, "version": row.version, "created_at": row.created_at, "download_url": f"/api/crm/catalog-datasheets/{row.id}/download"}


def _product(db: Session, tenant_id: int, product_id: str) -> CrmCatalogProduct:
    row = db.query(CrmCatalogProduct).filter(CrmCatalogProduct.id == product_id, CrmCatalogProduct.tenant_id == tenant_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Produto de catalogo nao encontrado.")
    return row


def _safe_name(filename: str) -> str:
    name = Path(filename or "datasheet").name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:180]
