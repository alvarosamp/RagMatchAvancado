"""LPU expiry and reversible catalog retirement; process history stays addressable."""
from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.crm.models import CrmNoticeProduct


def today_brasilia():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()


def month_later(value: date):
    year, month = (value.year + 1, 1) if value.month == 12 else (value.year, value.month + 1)
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def preserve_process_products(db, product):
    from app.crm.query import serialize_record
    snapshot = serialize_record(product)
    for item in db.query(CrmNoticeProduct).filter(
        CrmNoticeProduct.tenant_id == product.tenant_id,
        CrmNoticeProduct.catalog_product_id == product.id,
    ).all():
        if not item.catalog_snapshot or item.catalog_snapshot.get('id') != product.id:
            item.catalog_snapshot = snapshot
            item.catalog_lpu_version = product.lpu_version
