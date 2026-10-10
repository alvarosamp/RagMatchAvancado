from app.crm.dashboard import dashboard_snapshot
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def make_db():
    db = Session(create_engine("sqlite://"))
    definitions = [
        "tenants (id integer primary key, name text)",
        "crm_organs (id text, tenant_id integer, name text)",
        "crm_portals (id text, tenant_id integer, name text)",
        "crm_notices (id text, tenant_id integer, number text, title text, auction_date timestamp, created_at timestamp, stage text, outcome text, post_auction_phase text, organ_id text, portal_id text)",
        "crm_notice_products (id text, tenant_id integer, notice_id text, quantity float)",
        "crm_notice_item_results (id text, tenant_id integer, notice_id text, notice_product_id text, winner_type text, winning_price float, winning_quantity float)",
        "crm_notice_documents (id text, tenant_id integer, status text)",
        "editais (id integer, tenant_id integer)",
        "requirements (id integer, edital_id integer)",
    ]
    for definition in definitions:
        db.execute(text("create table " + definition))
    for tenant in (1, 2):
        db.execute(text("insert into tenants values (:id, :name)"), {"id": tenant, "name": f"Empresa {tenant}"})
        db.execute(text("insert into crm_notices values (:id, :tenant, 'PE 123', 'Rede', null, null, 'TRIAGE', 'PENDING', null, null, null)"), {"id": str(tenant), "tenant": tenant})
        db.execute(text("insert into crm_notice_products values (:id, :tenant, :id, 3)"), {"id": str(tenant), "tenant": tenant})
        db.execute(text("insert into editais values (:id, :id)"), {"id": tenant})
        db.execute(text("insert into requirements values (:id, :id)"), {"id": tenant})
    db.commit()
    return db


def test_dashboard_uses_projection_without_catalog_or_relationship_columns():
    with make_db() as db:
        report = dashboard_snapshot(db, 1)
        assert report["errors"] == []
        assert report["tenant_name"] == "Empresa 1"
        assert [row["id"] for row in report["notices"]] == ["1"]
        assert report["notices"][0]["outcome"] == "pending"
        assert [row["id"] for row in report["products"]] == ["1"]
        assert report["analyzed_points"] == 1
        assert report["pending_documents"] == 0


def test_failed_section_is_unknown_and_does_not_erase_available_indicators():
    with make_db() as db:
        db.execute(text("drop table crm_notice_item_results"))
        db.commit()
        report = dashboard_snapshot(db, 1)
        assert report["results"] is None
        assert report["errors"] == ["results"]
        assert len(report["notices"]) == 1
        assert report["analyzed_points"] == 1
