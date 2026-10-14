"""Current operational demand, independent of warehouse ingestion and fuzzy identity jobs."""
from uuid import uuid5, NAMESPACE_URL
from sqlalchemy.orm import selectinload
from app.crm.models import CrmCatalogProduct, CrmNotice, CrmNoticeProduct
from app.services.catalog_identity import product_category
from .domain import coverage, number, timestamp, unit, normalize
from .models import Identity
from .repository import scoped


def snapshot(db, tenant_id):
    identities = {r.source_id:r.entity_id for r in scoped(db, Identity, tenant_id).filter_by(source='crm',kind='product')}
    supplier_ids={r.source_id:r.entity_id for r in scoped(db, Identity, tenant_id).filter_by(source='crm',kind='supplier')}
    products=db.query(CrmCatalogProduct).filter_by(tenant_id=tenant_id).all()
    entities, relations, facts, suppliers = [], [], [], {}
    for product in products:
        identity=identities.get(product.id) or product.id
        identities[product.id]=identity
        active=bool(product.is_active and not product.archived_at)
        entities.append({'id':identity,'kind':'product','name':product.name,'brand':product.brand,
            'category':product_category(product.category,product.description,product.model), 'mpn':product.manufacturer_part_number,
            'gtin':product.gtin,'active':active,'attributes':{'crm_product_id':product.id}})
        if product.supplier_name and active:
            key=product.supplier_tax_id or product.supplier_name.strip().casefold()
            supplier_id=supplier_ids.get(normalize(product.supplier_name)) or str(uuid5(NAMESPACE_URL,f'crm-supplier:{tenant_id}:{key}'))
            suppliers[supplier_id]={'id':supplier_id,'kind':'supplier','name':product.supplier_name,'tax_id':product.supplier_tax_id,'active':True}
            relations.append({'source':'crm','product_id':identity,'supplier_id':supplier_id,'active':True,'cost':number(product.cost,positive=True)})
    rows=db.query(CrmNoticeProduct,CrmNotice).join(CrmNotice,
        (CrmNotice.id==CrmNoticeProduct.notice_id)&(CrmNotice.tenant_id==tenant_id)).filter(CrmNoticeProduct.tenant_id==tenant_id).all()
    for item, notice in rows:
        if str(getattr(notice.outcome,'value',notice.outcome))=='not_pursued':
            continue
        raw=item.raw_payload if isinstance(item.raw_payload,dict) else {}
        raw={**(raw.get('_raw_input') if isinstance(raw.get('_raw_input'),dict) else {}),**raw}
        if raw.get('kit_component'):
            continue
        quantity=number(item.quantity,positive=True)
        reference=number(item.reference_price,positive=True)
        total=number(item.reference_total_price,positive=True)
        if total is None and reference is not None and quantity is not None:
            total=reference*quantity
        direction=raw.get('direcionamento_marca')
        brand=raw.get('marca') or raw.get('brand')
        if not brand and isinstance(direction,dict) and direction.get('existe') is True:
            brand=direction.get('marca') or direction.get('fabricante')
        if not isinstance(brand,str) or brand.strip().lower() in {'n/c','não informado','nao informado',''}:
            brand=None
        event_at=timestamp(notice.created_at)
        facts.append({'id':'crm-demand:'+item.id,'source_id':item.id,'unit_price':reference,'source':'crm','kind':'demand','notice_id':notice.id,'item_id':item.id,
            'product_id':identities.get(item.catalog_product_id),'supplier_id':None,'category':item.category,'brand':brand,
            'state':notice.state,'unit':unit(item.unit),'quantity':quantity,'reference_price':reference,'total_value':total,
            'currency':'BRL','description':item.description,'event_at':event_at,'active':True,
            'coverage':coverage(item.match_review_verdict,bool(item.catalog_product_id)),
            'attributes':{'technical_verdict':item.match_review_verdict,'selected_for_dispute':item.selected_for_dispute,
                          'requested_bi_features':{**(raw.get('caracteristicas_bi') if isinstance(raw.get('caracteristicas_bi'),dict) else {}),**(item.bi_features if isinstance(item.bi_features,dict) else {})},
                          'notice_context':{'title':notice.title,'auction_date':notice.auction_date.isoformat() if notice.auction_date else None},
                          'item_context':{'warranty':item.warranty,'delivery_deadline':item.delivery_deadline,'technical_characteristics':item.technical_characteristics}}})
    return facts, entities+list(suppliers.values()), relations


def filter_facts(facts, filters):
    from .service import local_boundary
    output=[]
    for row in facts:
        if filters.get('date_from') and row['event_at']<local_boundary(filters['date_from']):continue
        if filters.get('date_to') and row['event_at']>=local_boundary(filters['date_to'],True):continue
        if any(filters.get(key) and row.get(key)!=filters[key] for key in ('category','state','brand','supplier_id','product_id','source','price_type')):continue
        if filters.get('unresolved_product') and row.get('product_id'):continue
        if filters.get('search') and filters['search'].casefold() not in str(row.get('description') or '').casefold():continue
        output.append(row)
    return output
