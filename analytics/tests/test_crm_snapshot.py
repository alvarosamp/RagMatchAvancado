from app.auth import (
    models as auth_models,  # noqa: F401 -- operational mapper registration
)
from app.crm.models import (
    CrmCatalogProduct,
    CrmNotice,
    CrmNoticeItemResult,
    CrmNoticeProduct,
    CrmNoticeProductMatch,
)
from app.market_intelligence.crm_source import reconcile_crm
from app.market_intelligence.models import Fact, RawRecord
from app.market_intelligence.repository import scoped
from sqlalchemy import text
from sqlalchemy.schema import CreateTable


def test_crm_reconciliation_updates_prices_and_deactivates_removed_items(db):
    # SQLite exercises extraction/reconciliation, not foreign keys or RLS.
    # PostgreSQL constraints and isolation are tested separately in CI.
    for model in [
        CrmCatalogProduct,
        CrmNotice,
        CrmNoticeProduct,
        CrmNoticeItemResult,
        CrmNoticeProductMatch,
    ]:
        db.execute(
            text(
                str(
                    CreateTable(
                        model.__table__, include_foreign_key_constraints=[]
                    ).compile(db.get_bind())
                )
            )
        )
    product = CrmCatalogProduct(
        id="p",
        tenant_id=1,
        name="Switch",
        brand="ACME",
        sku="s",
        cost=0,
        supplier_name="Fornecedor",
    )
    notice = CrmNotice(id="n", tenant_id=1, number="1", state="SP")
    item = CrmNoticeProduct(
        id="i",
        tenant_id=1,
        notice_id="n",
        item_number=1,
        description="Switch",
        category="switch",
        quantity=2,
        reference_price=10,
        catalog_product_id="p",
        match_review_verdict="ATENDE",
        unit="UN",
        cost=0,
    )
    db.add_all([product, notice, item])
    db.flush()
    reconcile_crm(db, 1, "r1")
    db.flush()
    demand = scoped(db, Fact, 1).filter_by(kind="demand").one()
    offer = scoped(db, Fact, 1).filter_by(kind="offer").one()
    assert float(demand.total_value) == 20
    assert demand.coverage == "covered"
    assert offer.cost is None
    item.reference_price = 20
    db.flush()
    reconcile_crm(db, 1, "r2")
    assert float(demand.total_value) == 40
    assert scoped(db, Fact, 1).filter_by(kind="demand").count() == 1
    assert scoped(db, RawRecord, 1).filter_by(entity="demand").count() == 2
    db.execute(
        CrmNoticeProduct.__table__.delete().where(CrmNoticeProduct.id == item.id)
    )
    db.expunge(item)
    db.flush()
    reconcile_crm(db, 1, "r3")
    db.expire_all()
    assert scoped(db, Fact, 1).filter_by(kind="demand", active=True).count() == 0
