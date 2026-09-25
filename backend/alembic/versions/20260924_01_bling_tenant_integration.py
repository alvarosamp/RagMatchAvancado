"""Store encrypted Bling credentials per tenant with RLS isolation."""

import sqlalchemy as sa
from alembic import op

revision = "20260924_01"
down_revision = "20260922_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bling_tenant_integrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_state_hash", sa.String(length=64), nullable=True),
        sa.Column("pending_state_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", name="uq_bling_tenant_integrations_tenant"
        ),
    )
    op.create_index(
        "ix_bling_tenant_integrations_tenant_id",
        "bling_tenant_integrations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_bling_tenant_integrations_pending_state_hash",
        "bling_tenant_integrations",
        ["pending_state_hash"],
    )
    op.execute("ALTER TABLE bling_tenant_integrations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bling_tenant_integrations FORCE ROW LEVEL SECURITY")
    op.execute(
        'CREATE POLICY "tenant_isolation_bling_tenant_integrations" '
        "ON bling_tenant_integrations "
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    )


def downgrade() -> None:
    op.drop_table("bling_tenant_integrations")
