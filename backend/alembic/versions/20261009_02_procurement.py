"""Auditable procurement inquiries and supplier quotes with tenant isolation."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261009_02"
down_revision = "20261009_01"
branch_labels = None
depends_on = None


def common():
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
    ]


def upgrade():
    op.create_table(
        "procurement_requests",
        *common(),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("needed_by", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("selection_history", JSONB(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"], ["core.entities.tenant_id", "core.entities.id"]
        ),
        sa.CheckConstraint("quantity > 0"),
        schema="core",
    )
    op.create_table(
        "supplier_quotes",
        *common(),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("supplier_id", sa.String(36), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("shipping", sa.Numeric(20, 6)),
        sa.Column("taxes", sa.Numeric(20, 6)),
        sa.Column("available_quantity", sa.Numeric(20, 6)),
        sa.Column("minimum_quantity", sa.Numeric(20, 6)),
        sa.Column("lead_time_days", sa.Integer()),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("evidence", JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "request_id"],
            ["core.procurement_requests.tenant_id", "core.procurement_requests.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["core.entities.tenant_id", "core.entities.id"],
        ),
        sa.CheckConstraint("unit_price > 0"),
        sa.CheckConstraint("shipping IS NULL OR shipping >= 0"),
        sa.CheckConstraint("taxes IS NULL OR taxes >= 0"),
        schema="core",
    )
    for table in ("procurement_requests", "supplier_quotes"):
        op.create_index(
            f"ix_{table}_tenant_created",
            table,
            ["tenant_id", "created_at"],
            schema="core",
        )
        op.execute(sa.text(f"ALTER TABLE core.{table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE core.{table} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation ON core.{table} USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::integer) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::integer)"
            )
        )
    bind = op.get_bind()
    for role, privilege in bind.execute(
        sa.text(
            "SELECT DISTINCT grantee, privilege_type FROM information_schema.role_table_grants WHERE table_schema='core' AND table_name='facts' AND grantee <> 'PUBLIC' AND grantee <> current_user AND privilege_type IN ('SELECT','INSERT','UPDATE','DELETE')"
        )
    ):
        quoted = bind.dialect.identifier_preparer.quote(role)
        op.execute(
            sa.text(
                f"GRANT {privilege} ON core.procurement_requests, core.supplier_quotes TO {quoted}"
            )
        )


def downgrade():
    op.drop_table("supplier_quotes", schema="core")
    op.drop_table("procurement_requests", schema="core")
