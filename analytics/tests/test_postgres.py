"""Requires a fresh, disposable PostgreSQL 15+ database ending in _test."""

import importlib.util
import os
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from analytics.provision_bi import provision_sql


@pytest.fixture(scope="module")
def postgres():
    url = os.getenv("TEST_MARKET_PG_URL")
    if not url:
        pytest.skip(
            "TEST_MARKET_PG_URL not configured; PostgreSQL integration runs in CI"
        )
    engine = create_engine(url)
    assert engine.url.database.endswith("_test"), (
        "Only a disposable test database is allowed"
    )
    with engine.begin() as connection:
        assert (
            connection.scalar(text("select to_regclass('public.tenants')")) is None
        ), "Test DB must be fresh"
        connection.execute(
            text(
                "CREATE TABLE public.tenants(id integer primary key); INSERT INTO public.tenants VALUES(1),(2)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE public.crm_catalog_products(id integer); CREATE TABLE public.crm_notice_item_results(id integer)"
            )
        )
        spec = importlib.util.spec_from_file_location(
            "market_migration",
            Path(__file__).resolve().parents[2]
            / "backend/alembic/versions/20261009_01_market_intelligence.py",
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        spec = importlib.util.spec_from_file_location(
            "procurement_migration",
            Path(__file__).resolve().parents[2]
            / "backend/alembic/versions/20261009_02_procurement.py",
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        connection.execute(
            text(
                "CREATE ROLE procurement_test_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS; GRANT USAGE ON SCHEMA core TO procurement_test_runtime; GRANT SELECT, INSERT ON core.procurement_requests, core.supplier_quotes TO procurement_test_runtime"
            )
        )
        connection.execute(
            text(
                "CREATE ROLE market_test_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS; GRANT USAGE ON SCHEMA core TO market_test_runtime; GRANT SELECT, INSERT ON core.entities TO market_test_runtime"
            )
        )
        connection.execute(
            text(
                "INSERT INTO core.entities(id,tenant_id,kind,identity_key,name,normalized_name,active,attributes,updated_at) VALUES ('a',1,'supplier','a','Empresa A','empresa a',true,'{}',now()), ('b',2,'supplier','b','Empresa B','empresa b',true,'{}',now())"
            )
        )
        connection.execute(
            text(provision_sql(1).replace("BEGIN;", "").replace("COMMIT;", ""))
        )
        connection.execute(
            text(
                "CREATE ROLE market_transform_test LOGIN PASSWORD 'test-only' NOSUPERUSER NOBYPASSRLS; GRANT USAGE ON SCHEMA raw TO market_transform_test; GRANT SELECT ON ALL TABLES IN SCHEMA raw,core TO market_transform_test; GRANT USAGE,CREATE ON SCHEMA staging,core,mart TO market_transform_test"
            )
        )
        connection.execute(
            text(
                "INSERT INTO core.facts(id,tenant_id,source,kind,source_id,category,currency,unit,total_value,coverage,event_at,available_at,active,attributes,updated_at) VALUES ('d1',1,'crm','demand','d1','Switch','BRL','UN',100,'covered',now(),now(),true,'{}',now()),('d2',2,'crm','demand','d2','Switch','BRL','UN',200,'unassessed',now(),now(),true,'{}',now())"
            )
        )
    yield engine
    engine.dispose()


def test_migration_forces_rls_and_denies_missing_context(postgres):
    with postgres.begin() as connection:
        assert connection.scalar(
            text(
                "SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('raw','core','mart') AND c.relkind='r'"
            )
        )
        connection.execute(text("SET LOCAL ROLE market_test_runtime"))
        assert connection.scalar(text("SELECT count(*) FROM core.entities")) == 0
        connection.execute(text("SELECT set_config('app.current_tenant_id','1',true)"))
        assert connection.scalars(text("SELECT name FROM core.entities")).all() == [
            "Empresa A"
        ]


def test_fixed_tenant_bi_view_cannot_be_switched_by_session_setting(postgres):
    with postgres.begin() as connection:
        connection.execute(text("SET LOCAL ROLE market_bi_1"))
        connection.execute(text("SELECT set_config('app.current_tenant_id','2',true)"))
        assert connection.scalars(
            text("SELECT name FROM bi_tenant_1.entities")
        ).all() == ["Empresa A"]
    with (
        pytest.raises(Exception, match="permission denied"),
        postgres.begin() as connection,
    ):
        connection.execute(text("SET LOCAL ROLE market_bi_1"))
        connection.execute(text("SELECT * FROM core.entities"))


def test_rls_blocks_cross_tenant_insert(postgres):
    with (
        pytest.raises(Exception, match="row-level security"),
        postgres.begin() as connection,
    ):
        connection.execute(text("SET LOCAL ROLE market_test_runtime"))
        connection.execute(text("SELECT set_config('app.current_tenant_id','1',true)"))
        connection.execute(
            text(
                "INSERT INTO core.entities(id,tenant_id,kind,identity_key,name,normalized_name,active,attributes,updated_at) VALUES ('evil',2,'supplier','evil','Wrong tenant','wrong tenant',true,'{}',now())"
            )
        )


def test_procurement_rls_and_composite_references(postgres):
    request = "INSERT INTO core.procurement_requests(id,tenant_id,product_id,quantity,unit,status,user_id,snapshot,selection_history) VALUES ('rfq',1,'a',2,'UN','open',1,'{}','[]')"
    quote = "INSERT INTO core.supplier_quotes(id,tenant_id,request_id,supplier_id,unit_price,valid_until,user_id,evidence) VALUES ('quote',1,'rfq','a',5,current_date,1,'{}')"
    with postgres.begin() as connection:
        connection.execute(text(request))
        connection.execute(text(quote))
        connection.execute(text("SET LOCAL ROLE procurement_test_runtime"))
        assert (
            connection.scalar(text("SELECT count(*) FROM core.procurement_requests"))
            == 0
        )
        connection.execute(text("SELECT set_config('app.current_tenant_id','2',true)"))
        assert connection.scalar(text("SELECT count(*) FROM core.supplier_quotes")) == 0
        connection.execute(text("SELECT set_config('app.current_tenant_id','1',true)"))
        assert connection.scalar(text("SELECT count(*) FROM core.supplier_quotes")) == 1
    with pytest.raises(Exception, match="foreign key"), postgres.begin() as connection:
        connection.execute(
            text(quote.replace("'quote'", "'cross'", 1).replace("'a',5", "'b',5"))
        )
    with (
        pytest.raises(Exception, match="row-level security"),
        postgres.begin() as connection,
    ):
        connection.execute(text("SET LOCAL ROLE procurement_test_runtime"))
        connection.execute(text("SELECT set_config('app.current_tenant_id','2',true)"))
        connection.execute(text(request.replace("'rfq'", "'forbidden'", 1)))


def test_negotiation_aggregations_under_restricted_postgres_role(postgres):
    from app.market_intelligence.models import ProcurementRequest
    from app.market_intelligence.negotiations import filter_requests, overview
    from app.market_intelligence.repository import scoped
    from sqlalchemy.orm import Session

    with postgres.begin() as connection:
        connection.execute(
            text("GRANT SELECT ON core.entities TO procurement_test_runtime")
        )
        connection.execute(text("SET LOCAL ROLE procurement_test_runtime"))
        connection.execute(text("SELECT set_config('app.current_tenant_id','1',true)"))
        with Session(bind=connection) as session:
            data = overview(session, 1)
            assert data["requests"] == 1 and data["quotes"] == 1
            assert data["incomplete"] == 1 and data["expiring"] == 1
            assert data["suppliers"][0]["name"] == "Empresa A"
            assert (
                filter_requests(
                    session,
                    1,
                    scoped(session, ProcurementRequest, 1),
                    "incomplete",
                    search="rfq",
                ).count()
                == 1
            )
            connection.execute(
                text("SELECT set_config('app.current_tenant_id','2',true)")
            )
            assert overview(session, 2)["quotes"] == 0
            assert overview(session, 1)["quotes"] == 0
