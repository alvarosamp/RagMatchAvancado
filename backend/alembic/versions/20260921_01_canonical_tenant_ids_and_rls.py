"""Canonical integer tenant ids and RLS for editais/jobs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "20260921_01"
down_revision = "20260918_01"
branch_labels = None
depends_on = None

TABLES = ("editais", "jobs")


def _drop_tenant_foreign_keys(table_name: str) -> None:
    inspector = inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key.get("constrained_columns") == ["tenant_id"] and foreign_key.get("name"):
            op.drop_constraint(foreign_key["name"], table_name, type_="foreignkey")


def _drop_tenant_index(table_name: str) -> None:
    inspector = inspect(op.get_bind())
    for index in inspector.get_indexes(table_name):
        if index.get("column_names") == ["tenant_id"] and index.get("name"):
            op.drop_index(index["name"], table_name=table_name)


def _assert_complete(table_name: str, column_name: str) -> None:
    missing = op.get_bind().execute(
        text(f'SELECT count(*) FROM "{table_name}" WHERE "{column_name}" IS NULL')
    ).scalar_one()
    if missing:
        raise RuntimeError(
            f"Migracao cancelada: {missing} registros de {table_name} possuem tenant desconhecido."
        )


def _enable_rls(table_name: str) -> None:
    policy = f"tenant_isolation_{table_name}"
    op.execute(text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'))
    op.execute(text(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY'))
    op.execute(text(
        f'CREATE POLICY "{policy}" ON "{table_name}" '
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    ))


def _disable_rls(table_name: str) -> None:
    op.execute(text(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"'))
    op.execute(text(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY'))
    op.execute(text(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY'))


def upgrade() -> None:
    for table_name in TABLES:
        op.add_column(table_name, sa.Column("tenant_id_v2", sa.Integer(), nullable=True))
        op.execute(text(
            f'UPDATE "{table_name}" AS source SET tenant_id_v2 = tenants.id '
            f'FROM tenants WHERE source.tenant_id = tenants.slug'
        ))
        if table_name == "jobs":
            op.execute(text(
                "UPDATE jobs SET payload = jsonb_set(COALESCE(payload::jsonb, '{}'::jsonb), "
                "'{tenant_id}', to_jsonb(tenant_id_v2), true)::json "
                "WHERE tenant_id_v2 IS NOT NULL"
            ))
        _assert_complete(table_name, "tenant_id_v2")
        _drop_tenant_foreign_keys(table_name)
        _drop_tenant_index(table_name)
        op.drop_column(table_name, "tenant_id")
        op.alter_column(table_name, "tenant_id_v2", new_column_name="tenant_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table_name}_tenant_id_tenants",
            table_name,
            "tenants",
            ["tenant_id"],
            ["id"],
        )
        op.create_index(f"ix_{table_name}_tenant_id", table_name, ["tenant_id"])
        _enable_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_rls(table_name)
        op.add_column(table_name, sa.Column("tenant_slug_v1", sa.String(), nullable=True))
        op.execute(text(
            f'UPDATE "{table_name}" AS source SET tenant_slug_v1 = tenants.slug '
            f'FROM tenants WHERE source.tenant_id = tenants.id'
        ))
        if table_name == "jobs":
            op.execute(text(
                "UPDATE jobs SET payload = jsonb_set(COALESCE(payload::jsonb, '{}'::jsonb), "
                "'{tenant_id}', to_jsonb(tenant_slug_v1), true)::json "
                "WHERE tenant_slug_v1 IS NOT NULL"
            ))
        _assert_complete(table_name, "tenant_slug_v1")
        _drop_tenant_foreign_keys(table_name)
        _drop_tenant_index(table_name)
        op.drop_column(table_name, "tenant_id")
        op.alter_column(table_name, "tenant_slug_v1", new_column_name="tenant_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table_name}_tenant_id_tenants_slug",
            table_name,
            "tenants",
            ["tenant_id"],
            ["slug"],
        )
        op.create_index(f"ix_{table_name}_tenant_id", table_name, ["tenant_id"])
