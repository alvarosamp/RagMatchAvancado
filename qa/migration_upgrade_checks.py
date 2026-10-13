"""Exercise released migration branches using only disposable QA databases."""

import importlib.util
import json
import os
import subprocess
import sys
import uuid
from contextlib import closing
from pathlib import Path

import psycopg2
from alembic.migration import MigrationContext
from alembic.operations import Operations
from psycopg2 import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    admin_url = make_url(os.environ["QA_ADMIN_DATABASE_URL"])
    if admin_url.database != "ragmatch_quality":
        raise RuntimeError("Migration checks require the disposable QA stack.")
    root = Path("/app")
    originals = ("20260926_01", "20261010_03", "20261012_01", "20261012_02")
    with closing(psycopg2.connect(admin_url.render_as_string(hide_password=False))) as admin:
        admin.autocommit = True
        for original in originals:
            database = "qa_migrations_" + uuid.uuid4().hex + "_test"
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
            case_url = admin_url.set(database=database)
            engine = create_engine(case_url)
            try:
                with engine.begin() as connection:
                    # Minimal old operational schema: historical analytical
                    # migrations are real, never stamped without execution.
                    for statement in (
                        "CREATE TABLE users(id integer primary key)",
                        "INSERT INTO users VALUES(1)",
                        "CREATE TABLE tenants(id integer primary key)",
                        "INSERT INTO tenants VALUES(1),(2)",
                        "CREATE TABLE crm_catalog_products(id text primary key, tenant_id integer, name text)",
                        "INSERT INTO crm_catalog_products VALUES('saved',1,'Produto preservado')",
                        "CREATE TABLE crm_notice_item_results(id text primary key)",
                        "CREATE TABLE crm_notices(id text primary key, tenant_id integer, notes text)",
                        "INSERT INTO crm_notices VALUES('saved',1,'Anotação preservada')",
                        "CREATE TABLE crm_notice_product_matches(id text primary key)",
                    ):
                        connection.execute(text(statement))
                    if original in {"20261010_03", "20261012_02"}:
                        for name in ("20261009_01_market_intelligence", "20261009_02_procurement", "20261010_03_supplier_sharing"):
                            path = root / "alembic/versions" / (name + ".py")
                            spec = importlib.util.spec_from_file_location(name, path)
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            with Operations.context(MigrationContext.configure(connection)):
                                module.upgrade()
                    if original in {"20261012_01", "20261012_02"}:
                        connection.execute(text("ALTER TABLE crm_notice_product_matches ADD COLUMN technical_result JSON"))
                        connection.execute(text("INSERT INTO crm_notice_product_matches VALUES('saved','{\"status\":\"VERIFICAR\"}')"))
                    # Stamp records an already-built fixture, not a production
                    # recovery operation. The target upgrade uses the real CLI.
                    MigrationContext.configure(connection)._ensure_version_table()
                    connection.execute(text("INSERT INTO alembic_version VALUES(:revision)"), {"revision": original})
                env = {**os.environ, "DATABASE_URL": case_url.render_as_string(hide_password=False)}
                result = subprocess.run([sys.executable, "scripts/migrate_database.py"], cwd=root, env=env, capture_output=True, text=True, timeout=90)
                if result.returncode:
                    raise AssertionError(original + ": " + result.stdout + result.stderr)
                with engine.connect() as connection:
                    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261013_01"
                    assert connection.scalar(text("SELECT count(*) FROM users WHERE id=1")) == 1
                    assert connection.scalar(text("SELECT to_regclass('public.auth_sessions') IS NOT NULL"))
                    assert connection.scalar(text("SELECT notes FROM crm_notices WHERE id='saved'")) == "Anotação preservada"
                    assert connection.scalar(text("SELECT name FROM crm_catalog_products WHERE id='saved'")) == "Produto preservado"
                    assert connection.scalar(text("SELECT to_regclass('core.supplier_presentation_links') IS NOT NULL"))
                    assert connection.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_name='crm_notice_product_matches' AND column_name='technical_result'")) == 1
                    if original in {"20261012_01", "20261012_02"}:
                        assert connection.scalar(text("SELECT technical_result FROM crm_notice_product_matches WHERE id='saved'")) == {"status": "VERIFICAR"}
                print(json.dumps({"from": original, "to": "20261013_01", "preserved": True}), flush=True)
            finally:
                engine.dispose()
                with admin.cursor() as cursor:
                    cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
