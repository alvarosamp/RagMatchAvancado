from types import SimpleNamespace

import app.jobs.models  # noqa: F401 -- registers Tenant's related Job mapper
from app.crm.models import CrmChecklistTemplate, CrmChecklistTemplateItem
from app.crm.query import DEFAULT_TEMPLATE_ITEMS, ensure_default_template
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_default_template_creation_is_idempotent_and_tenant_scoped():
    engine = create_engine("sqlite://")
    for model in (CrmChecklistTemplate, CrmChecklistTemplateItem):
        model.__table__.create(engine)
    try:
        with Session(engine) as db:
            for tenant in (1, 1, 2, 2):
                ensure_default_template(db, SimpleNamespace(tenant_id=tenant))
            assert db.query(CrmChecklistTemplate).count() == 2
            assert db.query(CrmChecklistTemplateItem).count() == 2 * len(
                DEFAULT_TEMPLATE_ITEMS
            )
            row = db.query(CrmChecklistTemplate).filter_by(tenant_id=1).one()
            row.is_default = False
            db.commit()
            ensure_default_template(db, SimpleNamespace(tenant_id=1))
            assert db.query(CrmChecklistTemplate).count() == 2
            assert not row.is_default
    finally:
        engine.dispose()
