"""Revocable supplier presentation grants with FORCE RLS."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261010_03"
down_revision = "20261009_02"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "supplier_presentation_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("public.tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("supplier_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("scope", JSONB(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        schema="core",
    )
    op.create_index(
        "ix_core_supplier_presentation_links_tenant_id",
        "supplier_presentation_links",
        ["tenant_id"],
        schema="core",
    )
    op.execute("ALTER TABLE core.supplier_presentation_links ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE core.supplier_presentation_links FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON core.supplier_presentation_links USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::integer) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::integer)"
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
                f"GRANT {privilege} ON core.supplier_presentation_links TO {quoted}"
            )
        )


def downgrade():
    op.drop_table("supplier_presentation_links", schema="core")
