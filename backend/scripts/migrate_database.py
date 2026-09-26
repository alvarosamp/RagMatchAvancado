"""Upgrade an existing database or bootstrap an entirely empty one.

The fresh-database snapshot is intentionally pinned to the migration revision
whose models it represents. A new Alembic head must update this bootstrap first.
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.rls import RLS_TABLES
from app.db.session import SessionLocal, engine

BOOTSTRAP_REVISION = "20260926_01"


def _bootstrap_empty_database(config: Config) -> None:
    from app.db.init_db import init_db

    db = SessionLocal()
    try:
        init_db(db)
        db.commit()
    finally:
        db.close()

    with engine.begin() as connection:
        for table in RLS_TABLES:
            connection.execute(text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            connection.execute(text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            connection.execute(text(
                f'CREATE POLICY "tenant_isolation_{table}" ON "{table}" '
                "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
                "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
            ))

    # Current models already include every historical migration. Running those
    # migrations against this snapshot would duplicate columns and tables.
    command.stamp(config, BOOTSTRAP_REVISION)


def main() -> None:
    config = Config("alembic.ini")
    head = ScriptDirectory.from_config(config).get_current_head()
    tables = set(inspect(engine).get_table_names(schema="public"))
    fresh = not (tables - {"alembic_version"})

    if fresh:
        if head != BOOTSTRAP_REVISION:
            raise RuntimeError(
                f"Bootstrap de banco vazio está fixado em {BOOTSTRAP_REVISION}; "
                f"a migration head atual é {head}. Atualize e valide o snapshot antes de implantar."
            )
        print("Banco vazio detectado; criando snapshot inicial e políticas RLS.")
        _bootstrap_empty_database(config)
    else:
        print("Banco existente detectado; aplicando migrations Alembic.")
        command.upgrade(config, "head")


if __name__ == "__main__":
    main()
