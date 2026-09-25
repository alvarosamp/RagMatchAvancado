"""Enforce tenant RLS on remaining directly tenant-owned data tables."""

from alembic import op
from app.db.rls import OTHER_TENANT_RLS_TABLES
from sqlalchemy import inspect, text

revision = "20260922_02"
down_revision = "20260922_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    available = set(inspector.get_table_names(schema="public"))
    missing = set(OTHER_TENANT_RLS_TABLES) - available
    if missing:
        raise RuntimeError(f"Tabelas de tenant ausentes; RLS não aplicado: {sorted(missing)}")

    for table in OTHER_TENANT_RLS_TABLES:
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "tenant_id" not in columns:
            raise RuntimeError(f"Tabela sem tenant_id: {table}")
        op.execute(text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        op.execute(text(
            f'CREATE POLICY "tenant_isolation_{table}" ON "{table}" '
            "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
            "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
        ))


def downgrade() -> None:
    for table in reversed(OTHER_TENANT_RLS_TABLES):
        op.execute(text(f'DROP POLICY IF EXISTS "tenant_isolation_{table}" ON "{table}"'))
        op.execute(text(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY'))
        op.execute(text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
