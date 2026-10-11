"""Exercise PostgreSQL enforcement, not only filters in application queries."""

import psycopg2
import pytest


def test_runtime_account_cannot_bypass_rls(runtime_db):
    with runtime_db.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user")
        assert cursor.fetchone() == (False, False, False, False)


@pytest.mark.parametrize("table", ["crm_notices", "crm_organs", "crm_portals", "crm_notice_products", "jobs", "editais"])
def test_direct_sql_without_tenant_context_returns_no_rows(runtime_db, table):
    from psycopg2 import sql
    with runtime_db.cursor() as cursor:
        cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
        assert cursor.fetchone()[0] == 0


@pytest.mark.parametrize("tenant", ["alpha", "beta"])
def test_direct_sql_tenant_context_prevents_cross_company_reads(runtime_db, seed, tenant):
    tenant_id = seed["tenants"][tenant]["id"]
    with runtime_db.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_tenant_id', %s, true)", (str(tenant_id),))
        cursor.execute("SELECT DISTINCT tenant_id FROM crm_notices")
        assert cursor.fetchall() == [(tenant_id,)]


def test_rls_rejects_foreign_tenant_insert(runtime_db, seed):
    with runtime_db.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_tenant_id', %s, true)", (str(seed["tenants"]["alpha"]["id"]),))
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute("INSERT INTO crm_organs(id, tenant_id, name) VALUES ('qa-forbidden', %s, 'Forbidden')", (seed["tenants"]["beta"]["id"],))
    runtime_db.rollback()


def test_tenant_context_is_transaction_local(runtime_db, seed):
    with runtime_db.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_tenant_id', %s, true)", (str(seed["tenants"]["alpha"]["id"]),))
        cursor.execute("SELECT count(*) FROM crm_notices")
        assert cursor.fetchone()[0] >= 1
    runtime_db.commit()
    with runtime_db.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM crm_notices")
        assert cursor.fetchone()[0] == 0


def test_runtime_role_cannot_create_tables(runtime_db):
    with runtime_db.cursor() as cursor:
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute("CREATE TABLE public.qa_forbidden(id integer)")
    runtime_db.rollback()


def test_migration_head_is_installed_and_tenant_tables_are_forced(admin_db):
    with admin_db.cursor() as cursor:
        cursor.execute("SELECT version_num FROM alembic_version")
        assert cursor.fetchone()[0]
        cursor.execute("SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('crm_notices','jobs','editais')")
        rows = cursor.fetchall()
        assert len(rows) == 3
        assert all(enabled and forced for _, enabled, forced in rows)
