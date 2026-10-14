"""Read the operational demand without serializing catalogue embeddings or attachments."""
import enum
import math
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import selectinload
from app.crm.models import CrmNotice, CrmNoticeProduct


def json_value(value):
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (float, Decimal)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def demand_notices(db, tenant_id):
    rows = db.query(CrmNotice).filter_by(tenant_id=tenant_id).options(
        selectinload(CrmNotice.notice_products), selectinload(CrmNotice.organ), selectinload(CrmNotice.portal)
    ).order_by(CrmNotice.created_at.desc()).all()
    output = []
    for row in rows:
        data = {c.name: json_value(getattr(row, c.name)) for c in CrmNotice.__table__.columns}
        data['organs'] = {k: getattr(row.organ, k) for k in ('name', 'city', 'state')} if row.organ else None
        data['portals'] = {'name': row.portal.name} if row.portal else None
        data['notice_products'] = []
        for item in row.notice_products:
            if item.tenant_id != tenant_id:
                continue
            product = {c.name: json_value(getattr(item, c.name)) for c in CrmNoticeProduct.__table__.columns}
            quantity = product.get('quantity')
            if product.get('reference_total_price') is None and product.get('reference_price') is not None and quantity is not None:
                product['reference_total_price'] = json_value(product['reference_price'] * quantity)
            data['notice_products'].append(product)
        output.append(data)
    return output
