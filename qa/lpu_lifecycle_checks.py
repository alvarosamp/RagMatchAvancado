"""Run with the production dependency image against an isolated SQLite database.
No production connection or credentials are required.
"""
import asyncio
from datetime import timedelta, date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import app.main  # register every production ORM mapping
from fastapi import HTTPException, UploadFile
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.models import Tenant, User
from app.crm.models import CrmCatalogProduct, CrmNotice, CrmNoticeProduct, CrmLpuVersion
from app.crm.lpu_importer import import_lpu_catalog
from app.crm.query import delete_records, list_records, serialize_record, insert_records, update_records
from app.db.models import Base
from app.routers.crm import crm_import_lpu_catalog, crm_review_lpu_product, crm_extend_lpu, crm_lpu_status
from app.services.lpu_lifecycle import today_brasilia, month_later

engine = create_engine('sqlite://')
Base.metadata.create_all(engine)
assert month_later(date(2026, 1, 31)) == date(2026, 2, 28)
assert month_later(date(2028, 1, 31)) == date(2028, 2, 29)
assert month_later(date(2026, 12, 31)) == date(2027, 1, 31)

with Session(engine) as db, TemporaryDirectory() as directory:
    tenant = Tenant(name='QA', slug='lpu-qa')
    other = Tenant(name='Other', slug='lpu-other')
    db.add_all([tenant, other]); db.flush()
    admin = User(tenant_id=tenant.id, email='qa-admin@example.invalid', hashed_password='unused', role='admin')
    owner = User(tenant_id=tenant.id, email='qa-owner@example.invalid', hashed_password='unused', role='viewer')
    stranger = User(tenant_id=other.id, email='qa-other@example.invalid', hashed_password='unused', role='admin')
    db.add_all([admin, owner, stranger]); db.flush()
    product = CrmCatalogProduct(tenant_id=tenant.id, name='Old product', sku='OLD', category='switch', cost=100,
        min_price=120, lpu_version='old-lpu', lpu_drive_url='https://drive.google.com/file/d/old')
    updated = CrmCatalogProduct(tenant_id=tenant.id, name='Price update', sku='UPDATED', category='transceiver', cost=200,
        min_price=240, lpu_version='old-lpu', lpu_drive_url='https://drive.google.com/file/d/old')
    manual = CrmCatalogProduct(tenant_id=tenant.id, name='Manual', sku='MANUAL', cost=300)
    external = CrmCatalogProduct(tenant_id=other.id, name='External', sku='EXTERNAL', cost=400, lpu_version='external')
    db.add_all([product, updated, manual, external]); db.flush()
    notice = CrmNotice(tenant_id=tenant.id, number='QA-process')
    db.add(notice); db.flush()
    item = CrmNoticeProduct(tenant_id=tenant.id, notice_id=notice.id, description='Old product in process', catalog_product_id=product.id)
    price_item = CrmNoticeProduct(tenant_id=tenant.id, notice_id=notice.id, description='Price update in process', catalog_product_id=updated.id)
    db.add_all([item, price_item]); db.commit()
    workbook = Workbook(); sheet = workbook.active; sheet.title = 'Transceivers'
    sheet.append(['Marca', 'PN TOR', 'Description', 'Disponibilidade', 'Custo Final', 'Preco Minimo'])
    sheet.append(['TOR', 'UPDATED', 'Updated', 'Estoque', 250, 280])
    sheet.append(['TOR', 'NEW', 'New', 'Estoque', 90, 110])
    path = Path(directory) / 'lpu.xlsx'; workbook.save(path)
    kwargs = dict(db=db, tenant_id=tenant.id, user_id=admin.id, lpu_drive_url='https://drive.google.com/file/d/new',
                  valid_until=today_brasilia() + timedelta(days=10), owner_id=owner.id)
    # Route preview must leave every product, version, snapshot and pending review unchanged.
    upload = UploadFile(filename='lpu.xlsx', file=BytesIO(path.read_bytes()))
    preview = asyncio.run(crm_import_lpu_catalog(upload, kwargs['lpu_drive_url'], kwargs['valid_until'], owner.id, True, db, admin))
    assert preview['summary']['pending_review'] == 1
    assert db.query(CrmLpuVersion).count() == 0
    assert db.query(CrmCatalogProduct).filter_by(sku='NEW').count() == 0
    db.refresh(updated); db.refresh(product); db.refresh(price_item)
    assert updated.cost == 200 and product.lpu_missing_since is None and price_item.catalog_snapshot is None
    summary = import_lpu_catalog(path, **kwargs)
    assert summary['removed_stale'] == 0 and summary['pending_review'] == 1
    assert summary['missing_items'][0]['sku'] == 'OLD'  # entire missing category detected
    db.refresh(product); db.refresh(price_item)
    assert product.cost == 100 and product.lpu_drive_url.endswith('/old')
    assert price_item.catalog_snapshot['cost'] == 200 and price_item.catalog_snapshot['lpu_drive_url'].endswith('/old')
    deadline = product.lpu_review_deadline
    import_lpu_catalog(path, **kwargs); db.refresh(product)
    assert product.lpu_review_deadline == deadline  # reimports must not reset the grace period
    assert manual.lpu_missing_since is None and external.lpu_missing_since is None
    try:
        delete_records(db, admin, 'catalog_products', [{'column': 'id', 'op': 'eq', 'value': product.id}])
        raise AssertionError('Generic delete bypassed review')
    except ValueError:
        db.rollback()
    try:
        crm_review_lpu_product(product.id, {'action': 'confirm'}, db, stranger)
        raise AssertionError('Cross-tenant review allowed')
    except HTTPException as exc:
        assert exc.status_code == 404
    current = db.query(CrmLpuVersion).filter_by(superseded_at=None).one()
    current.valid_until = today_brasilia() - timedelta(days=1); db.commit()
    status = crm_lpu_status(db, owner)
    assert status['expired'] and status['pending'][0]['assigned_to_me']
    crm_extend_lpu(current.id, {'valid_until': kwargs['valid_until'].isoformat(), 'owner_id': admin.id}, db, admin)
    assert not crm_lpu_status(db, admin)['expired']
    db.refresh(current); assert len(current.extensions) == 1
    crm_review_lpu_product(product.id, {'action': 'confirm'}, db, owner)
    db.refresh(item); db.refresh(product)
    assert product.archived_at and not product.is_active
    assert item.catalog_product_id == product.id and item.catalog_snapshot['cost'] == 100
    assert serialize_record(item)['catalog_products']['lpu_drive_url'].endswith('/old')
    update_records(db, admin, 'notice_products', {'catalog_product_id': product.id, 'cost': 105},
                   [{'column': 'id', 'op': 'eq', 'value': item.id}])
    db.refresh(item)
    assert item.cost == 105 and item.catalog_snapshot['cost'] == 100
    try:
        update_records(db, admin, 'catalog_products', {'is_active': True},
                       [{'column': 'id', 'op': 'eq', 'value': product.id}])
        raise AssertionError('Archived product edited outside the import flow')
    except ValueError:
        db.rollback()
    inserted = insert_records(db, admin, 'catalog_products', {'brand': 'QA', 'model': 'Manual product', 'sku': 'MANUAL-NEW'})
    assert inserted[0]['name'] == 'QA Manual product'
    rows, _ = list_records(db, admin, 'catalog_products')
    assert product.id not in {row['id'] for row in rows}
    # Product returns later: same ID, active catalog restored, process still uses old snapshot.
    sheet.append(['TOR', 'OLD', 'Returned', 'Estoque', 500, 600]); workbook.save(path)
    import_lpu_catalog(path, **kwargs); db.refresh(product); db.refresh(item)
    assert not product.archived_at and product.is_active and product.lpu_missing_since is None
    assert product.cost == 500 and serialize_record(item)['catalog_products']['cost'] == 100
    print('LPU lifecycle: preview rollback, expiry, extension audit, missing-category retention, review permissions, process snapshots and reappearance passed.')
