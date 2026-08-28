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
        link.catalog_datasheet_id = current.id if current else None
        document = db.get(CrmNoticeDocument, link.notice_document_id) if link.notice_document_id else None
        if document:
            document.source_url = f"/api/crm/catalog-datasheets/{current.id}/download" if current else None
            document.status = CrmChecklistStatus.READY if current else CrmChecklistStatus.PENDING


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
