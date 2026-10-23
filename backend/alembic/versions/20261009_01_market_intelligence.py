"""Tenant-scoped analytical ledger and provenance."""

import sqlalchemy as sa
from alembic import op

revision = "20261009_01"
down_revision = "20260926_01"
branch_labels = None
depends_on = None


def upgrade():
    # This revision's schema is held in a dedicated, versioned snapshot.
    from app.market_intelligence.schema_v1 import metadata

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, columns in {
        "crm_catalog_products": ["gtin", "supplier_tax_id"],
        "crm_notice_item_results": ["competitor_tax_id"],
    }.items():
        if inspector.has_table(table, schema="public"):
            existing = {
                column["name"]
                for column in inspector.get_columns(table, schema="public")
            }
            for column in columns:
                if column not in existing:
                    op.add_column(
                        table, sa.Column(column, sa.String(14)), schema="public"
                    )
    for schema in ("raw", "staging", "core", "mart"):
        op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    metadata.create_all(bind=bind)
    for table in metadata.sorted_tables:
        name = f'"{table.schema}"."{table.name}"'
        op.create_foreign_key(
            f"fk_{table.schema}_{table.name}_tenant",
            table.name,
            "tenants",
            ["tenant_id"],
            ["id"],
            source_schema=table.schema,
            referent_schema="public",
        )
        op.execute(sa.text(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation ON {name} USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
            )
        )
    # Grant the same runtime roles already authorized on CRM, never PUBLIC.
    grants = bind.execute(
        sa.text(
            "SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE table_schema='public' AND table_name='crm_notices' AND privilege_type IN ('SELECT','INSERT','UPDATE','DELETE') AND grantee <> 'PUBLIC' AND grantee <> current_user"
        )
    ).all()
    role_privileges = {}
    for role, privilege in grants:
        role_privileges.setdefault(role, set()).add(privilege)
    for role, privileges in role_privileges.items():
        quoted = bind.dialect.identifier_preparer.quote(role)
        for schema in ("raw", "core", "mart", "staging"):
            op.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO {quoted}'))
        for table in metadata.sorted_tables:
            allowed = ", ".join(sorted(privileges))
            op.execute(
                sa.text(
                    f'GRANT {allowed} ON "{table.schema}"."{table.name}" TO {quoted}'
                )
            )


def downgrade():
    # Only this revision's tables; schema contents belonging to dbt are retained.
    from app.market_intelligence.schema_v1 import metadata

    metadata.drop_all(bind=op.get_bind())
