"""Checks for the restricted production PostgreSQL role."""

import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from app.db.rls import (
    BLING_RLS_TABLES,
    CRM_RLS_TABLES,
    OTHER_TENANT_RLS_TABLES,
    RLS_TABLES,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/provision_app_role.py"
SPEC = importlib.util.spec_from_file_location("provision_app_role", SCRIPT)
provision_app_role = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(provision_app_role)


class FakeCursor:
    def __init__(self, *, superuser=True, role_exists=False):
        self.answers = iter([
            ("postgres", "edital_matcher"),
            (superuser,),
            (1,) if role_exists else None,
        ])
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append((statement, parameters))

    def fetchone(self):
        return next(self.answers)

    def fetchall(self):
        return [(name, True, True) for name in RLS_TABLES]


class FakeConnection:
    def __init__(self, **kwargs):
        self.fake_cursor = FakeCursor(**kwargs)

    def cursor(self):
        return self.fake_cursor


def test_runtime_role_is_created_without_rls_bypass_and_granted_only_dml():
    connection = FakeConnection()
    provision_app_role.provision(connection, "ragmatch_app", "secret")
    queries = "\n".join(str(statement) for statement, _ in connection.fake_cursor.statements)

    assert "CREATE ROLE" in queries
    assert "NOSUPERUSER NOBYPASSRLS" in queries
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES" in queries
    assert "GRANT USAGE, SELECT ON ALL SEQUENCES" in queries
    assert "GRANT TRUNCATE" not in queries
    assert "GRANT CREATE" not in queries
    assert any(params == ("secret",) for _, params in connection.fake_cursor.statements)


def test_provisioning_rejects_admin_role_as_runtime_role():
    with pytest.raises(ValueError, match="diferente"):
        provision_app_role.provision(FakeConnection(), "postgres", "secret")


def test_provisioning_requires_admin_connection():
    with pytest.raises(ValueError, match="administrativa"):
        provision_app_role.provision(FakeConnection(superuser=False), "ragmatch_app", "secret")


def test_compose_uses_restricted_role_for_all_runtime_processes():
    compose = (ROOT / "docker-compose.prod.yaml").read_text(encoding="utf-8")
    for name in ("api", "worker", "worker-ai", "scheduler"):
        service = re.split(r"\n  [a-z][a-z0-9-]*:\n", compose.split(f"  {name}:\n", 1)[1], maxsplit=1)[0]
        assert "APP_DB_USER" in service
        assert "APP_DB_PASSWORD" in service
        assert "POSTGRES_USER" not in service
    assert "command: python scripts/provision_app_role.py" in compose
    assert "command: python scripts/migrate_database.py" in compose


def test_fresh_database_bootstrap_is_pinned_and_installs_both_policies():
    bootstrap = (ROOT / "backend/scripts/migrate_database.py").read_text(encoding="utf-8")
    assert 'BOOTSTRAP_REVISION = "20260926_01"' in bootstrap
    assert set(RLS_TABLES) == {
        "editais",
        "jobs",
        *CRM_RLS_TABLES,
        *OTHER_TENANT_RLS_TABLES,
        *BLING_RLS_TABLES,
    }
    assert "ENABLE ROW LEVEL SECURITY" in bootstrap
    assert "FORCE ROW LEVEL SECURITY" in bootstrap
    assert "command.stamp(config, BOOTSTRAP_REVISION)" in bootstrap
    assert "head != BOOTSTRAP_REVISION" in bootstrap


def test_crm_migration_protects_all_scoped_tables():
    migration = (ROOT / "backend/alembic/versions/20260922_01_crm_tenant_rls.py").read_text(
        encoding="utf-8"
    )
    assert len(CRM_RLS_TABLES) == 20
    assert 'down_revision = "20260921_01"' in migration
    assert "for table in CRM_RLS_TABLES" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "WITH CHECK (tenant_id" in migration


def test_other_tenant_tables_have_rls_migration():
    migration = (ROOT / "backend/alembic/versions/20260922_02_other_tenant_rls.py").read_text(
        encoding="utf-8"
    )
    assert len(OTHER_TENANT_RLS_TABLES) == 9
    assert 'down_revision = "20260922_01"' in migration
    assert "for table in OTHER_TENANT_RLS_TABLES" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration

    conlicitacao_migration = (
        ROOT / "backend/alembic/versions/20260926_01_conlicitacao_tenders.py"
    ).read_text(encoding="utf-8")
    assert '_enable_rls("tenders")' in conlicitacao_migration
    assert '_enable_rls("tender_sync_checkpoints")' in conlicitacao_migration


def test_bling_credentials_have_dedicated_rls_migration():
    migration = (
        ROOT / "backend/alembic/versions/20260924_01_bling_tenant_integration.py"
    ).read_text(encoding="utf-8")
    assert BLING_RLS_TABLES == ("bling_tenant_integrations",)
    assert 'down_revision = "20260922_02"' in migration
    assert "client_secret_encrypted" in migration
    assert "refresh_token_encrypted" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration


def test_production_startup_rejects_superuser_or_missing_rls():
    from app.core import startup

    class Connection:
        def __init__(self, *, superuser=False, force_rls=True):
            self.answers = iter([
                SimpleNamespace(one=lambda: SimpleNamespace(rolsuper=superuser, rolbypassrls=False)),
                SimpleNamespace(all=lambda: [
                    SimpleNamespace(relname=name, relrowsecurity=True, relforcerowsecurity=force_rls)
                    for name in RLS_TABLES
                ]),
            ])

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_):
            return next(self.answers)

    for connection, expected in [
        (Connection(superuser=True), "ignora RLS"),
        (Connection(force_rls=False), "RLS das tabelas de tenant"),
    ]:
        fake_session = SimpleNamespace(engine=SimpleNamespace(connect=lambda current=connection: current))
        with patch.dict(sys.modules, {"app.db.session": fake_session}), pytest.raises(RuntimeError, match=expected):
            startup._validate_production_database()
