"""Create normalized tenders and provider sync checkpoints."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260926_01"
down_revision = "20260924_01"
branch_labels = None
depends_on = None


def _enable_rls(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(
        f'CREATE POLICY "tenant_isolation_{table}" ON "{table}" '
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    ))


def upgrade() -> None:
    op.create_table(
        "tenders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("object", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("edital_number", sa.String(length=255), nullable=True),
        sa.Column("process_number", sa.String(length=255), nullable=True),
        sa.Column("uasg", sa.String(length=100), nullable=True),
        sa.Column("public_body_name", sa.String(length=500), nullable=True),
        sa.Column("public_body_city", sa.String(length=255), nullable=True),
        sa.Column("public_body_state", sa.String(length=10), nullable=True),
        sa.Column("opening_at", sa.DateTime(), nullable=True),
        sa.Column("proposal_deadline_at", sa.DateTime(), nullable=True),
        sa.Column("estimated_value", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "provider", "external_id",
            name="uq_tenders_tenant_provider_external_id",
        ),
    )
    op.create_index("ix_tenders_tenant_id", "tenders", ["tenant_id"])
    op.create_index("ix_tenders_provider", "tenders", ["provider"])
    op.create_index("ix_tenders_external_id", "tenders", ["external_id"])
    op.create_index("ix_tenders_status", "tenders", ["status"])
    op.create_index("ix_tenders_edital_number", "tenders", ["edital_number"])
    op.create_index("ix_tenders_process_number", "tenders", ["process_number"])
    op.create_index("ix_tenders_uasg", "tenders", ["uasg"])
    op.create_index("ix_tenders_public_body_name", "tenders", ["public_body_name"])
    op.create_index("ix_tenders_public_body_city", "tenders", ["public_body_city"])
    op.create_index("ix_tenders_public_body_state", "tenders", ["public_body_state"])
    op.create_index("ix_tenders_tenant_opening_at", "tenders", ["tenant_id", "opening_at"])
    op.create_index("ix_tenders_tenant_status", "tenders", ["tenant_id", "status"])

    op.create_table(
        "tender_sync_checkpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_filter_id", sa.String(length=255), nullable=False),
        sa.Column("last_bulletin_id", sa.String(length=255), nullable=True),
        sa.Column("last_bulletin_closed_at", sa.DateTime(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "provider", "external_filter_id",
            name="uq_tender_sync_checkpoint_tenant_provider_filter",
        ),
    )
    op.create_index(
        "ix_tender_sync_checkpoints_tenant_id", "tender_sync_checkpoints", ["tenant_id"]
    )
    op.create_index(
        "ix_tender_sync_checkpoints_provider", "tender_sync_checkpoints", ["provider"]
    )

    _enable_rls("tenders")
    _enable_rls("tender_sync_checkpoints")


def downgrade() -> None:
    op.drop_table("tender_sync_checkpoints")
    op.drop_table("tenders")
