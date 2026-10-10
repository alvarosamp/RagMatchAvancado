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


def create_operational_tables(db):
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


def test_crm_reconciliation_updates_prices_and_deactivates_removed_items(db):
    create_operational_tables(db)
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


def test_triage_without_catalog_preserves_structured_json_and_pending_coverage(db):
    create_operational_tables(db)
    db.add(
        CrmNotice(
            id="n",
            tenant_id=1,
            number="1",
            title="Redes",
            bi_risk_identified="Amostra obrigatória",
        )
    )
    db.add(
        CrmNoticeProduct(
            id="i",
            tenant_id=1,
            notice_id="n",
            item_number=1,
            description="Switch",
            category="switch",
            quantity=12,
            reference_price=100,
            unit="UN",
            bi_features={"quantidade_portas": "24", "poe": {"potencia": "370 W"}},
            warranty="36 meses",
            delivery_deadline="30 dias",
        )
    )
    db.flush()
    reconcile_crm(db, 1, "triage")
    fact = scoped(db, Fact, 1).filter_by(kind="demand").one()
    assert float(fact.total_value) == 1200
    assert fact.coverage == "unassessed"
    assert fact.product_id is None
    assert fact.attributes["requested_bi_features"]["poe"]["potencia"] == "370 W"
    assert fact.attributes["item_context"]["warranty"] == "36 meses"
    assert fact.attributes["notice_context"]["risk_identified"] == "Amostra obrigatória"


def test_partial_reimport_keeps_existing_items_and_commercial_work(db, monkeypatch):
    from types import SimpleNamespace

    import app.services.crm_notice_sync as sync
    from app.crm.json_analysis_importer import _update_imported_notice, _upsert_products

    monkeypatch.setattr(sync, "sync_notice_from_product", lambda *args, **kwargs: None)
    create_operational_tables(db)
    notice = CrmNotice(
        id="n",
        tenant_id=1,
        number="1",
        stage="proposal",
        outcome="won",
        owner_id="owner",
        created_by="author",
        sales_status="Em negociação",
        particularities="Anotações do time",
    )
    db.add(notice)
    db.add_all(
        [
            CrmNoticeProduct(
                id=str(n),
                tenant_id=1,
                notice_id="n",
                item_number=n,
                description="Switch",
                quantity=5,
                reference_price=100,
                warranty="36 meses",
                notes="Cotação negociada",
                bi_features={"quantidade_portas": "24"},
                raw_payload={"item": n},
            )
            for n in (1, 2)
        ]
    )
    db.commit()
    context = SimpleNamespace(
        tenant=SimpleNamespace(id=1), user=SimpleNamespace(id="user")
    )
    _update_imported_notice(
        notice,
        {
            "stage": "triage",
            "outcome": "pending",
            "owner_id": "user",
            "created_by": "user",
            "sales_status": "novo",
            "particularities": None,
            "title": "Objeto revisado",
        },
    )
    _upsert_products(
        db,
        context,
        notice,
        [{"numero_item_edital": "1", "descricao": "Switch revisado"}],
    )
    db.commit()
    assert db.query(CrmNoticeProduct).count() == 2
    item = db.get(CrmNoticeProduct, "1")
    assert item.reference_price == 100 and item.quantity == 5
    assert item.description == "Switch"
    assert item.warranty == "36 meses" and item.notes == "Cotação negociada"
    assert item.bi_features["quantidade_portas"] == "24"
    assert (notice.stage, notice.outcome, notice.owner_id, notice.created_by) == (
        "proposal",
        "won",
        "owner",
        "author",
    )
    assert (
        notice.particularities == "Anotações do time"
        and notice.sales_status == "Em negociação"
    )
    # A failure before commit must leave the last committed edital intact.
    item.reference_price = 999
    db.flush()
    db.rollback()
    assert db.get(CrmNoticeProduct, "1").reference_price == 100


def test_partial_price_update_recomputes_total_from_saved_quantity(db, monkeypatch):
    from types import SimpleNamespace

    import app.services.crm_notice_sync as sync
    from app.crm.json_analysis_importer import _upsert_products

    monkeypatch.setattr(sync, "sync_notice_from_product", lambda *args, **kwargs: None)
    create_operational_tables(db)
    notice = CrmNotice(id="n", tenant_id=1, number="1")
    db.add(notice)
    db.add(
        CrmNoticeProduct(
            id="i",
            tenant_id=1,
            notice_id="n",
            item_number=1,
            description="Switch",
            quantity=5,
            reference_price=100,
            reference_total_price=500,
        )
    )
    db.flush()
    context = SimpleNamespace(
        tenant=SimpleNamespace(id=1), user=SimpleNamespace(id="user")
    )
    _upsert_products(
        db, context, notice, [{"numero_item_edital": "1", "preco_unitario": 200}]
    )
    db.flush()
    assert db.get(CrmNoticeProduct, "i").reference_total_price == 1000
