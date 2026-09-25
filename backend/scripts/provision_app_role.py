"""Provision a least-privilege runtime role after Alembic migrations.

Run this with the migration/owner connection, never with the application role.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.rls import RLS_TABLES


def provision(connection, app_user: str, app_password: str) -> None:
    if not app_user or not app_password:
        raise ValueError("APP_DB_USER e APP_DB_PASSWORD são obrigatórios.")

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user, current_database()")
        owner, database = cursor.fetchone()
        if app_user == owner:
            raise ValueError("APP_DB_USER deve ser diferente do usuário de migração.")

        cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname = %s", (owner,))
        if not cursor.fetchone()[0]:
            raise ValueError("O provisionamento exige uma conexão administrativa.")

        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE relnamespace = 'public'::regnamespace "
            "AND relname = ANY(%s)",
            (list(RLS_TABLES),),
        )
        rls_tables = cursor.fetchall()
        if {name for name, _, _ in rls_tables} != set(RLS_TABLES) or any(
            not enabled or not forced for _, enabled, forced in rls_tables
        ):
            raise ValueError("Migration de isolamento incompleta: RLS das tabelas de tenant não está ativo.")

        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,))
        if cursor.fetchone() is None:
            cursor.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(app_user)))

        cursor.execute(
            sql.SQL(
                "ALTER ROLE {} WITH LOGIN NOSUPERUSER NOBYPASSRLS "
                "NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %s"
            ).format(sql.Identifier(app_user)),
            (app_password,),
        )
        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), sql.Identifier(app_user)
            )
        )
        cursor.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(app_user))
        )
        cursor.execute(
            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
                sql.Identifier(app_user)
            )
        )
        cursor.execute(
            sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                sql.Identifier(app_user)
            )
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
            ).format(sql.Identifier(owner), sql.Identifier(app_user))
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT USAGE, SELECT ON SEQUENCES TO {}"
            ).format(sql.Identifier(owner), sql.Identifier(app_user))
        )


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    app_user = os.environ["APP_DB_USER"]
    app_password = os.environ["APP_DB_PASSWORD"]
    with psycopg2.connect(database_url) as connection:
        provision(connection, app_user, app_password)
    print(f"Conta de aplicação {app_user!r} provisionada.")


if __name__ == "__main__":
    main()
