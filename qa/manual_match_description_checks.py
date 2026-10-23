"""Regression for opening an existing, dated CRM item without a JSON upload."""
from datetime import datetime
import json

import app.main  # register production ORM models
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.models import Base
from app.auth.models import Tenant, User
from app.crm.models import CrmNotice, CrmNoticeProduct
from app.routers.manual_match import get_manual_match, suggest_manual_match

engine = create_engine('sqlite://')
Base.metadata.create_all(engine)
with Session(engine) as db:
    tenant = Tenant(slug='description-qa', name='QA')
    db.add(tenant); db.flush()
    user = User(tenant_id=tenant.id, email='description@example.invalid', hashed_password='unused', role='admin')
    notice = CrmNotice(tenant_id=tenant.id, number='2026_10_06_11', auction_date=datetime(2026, 10, 19, 9, 0))
    db.add_all([user, notice]); db.flush()
    text = 'Switch L2 tipo I, 24 portas 10/100/1000, VLAN IEEE 802.1Q, mínimo 4 portas de expansão 10 Gigabit Ethernet'
    item = CrmNoticeProduct(tenant_id=tenant.id, notice_id=notice.id, item_number='2', category='switch',
        description=text, quantity=55, raw_payload=None)
    db.add(item); db.commit()
    initial = get_manual_match(notice.id, item.id, db, user)
    state = initial['state']
    assert initial['item']['descricao'] == text
    assert state['fonte_json']['payload']['item']['descricao_original'] == text
    assert state['fonte_json']['payload']['processo']['data_sessao'] == '2026-10-19T09:00:00'
    assert state['requisitos'] and not state['filtros']
    json.dumps(initial, allow_nan=False)
    suggested = suggest_manual_match(notice.id, item.id, db, user)
    assert suggested['state']['fonte_json']['payload']['item']['descricao_original'] == text
    json.dumps(suggested, allow_nan=False)
    db.refresh(item)
    assert item.description == text and item.raw_payload is None and item.quantity == 55
    assert initial['base_revision'] == suggested['base_revision']
print('Existing description opens and suggests requirements without upload; dated notice is JSON-safe; item data remains unchanged.')
