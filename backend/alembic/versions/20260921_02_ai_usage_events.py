"""Record tenant-scoped provider usage without prompts or responses."""

from alembic import op
import sqlalchemy as sa


revision = "20260921_02"
down_revision = "20260921_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_slug", sa.String(), sa.ForeignKey("tenants.slug"), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_usage_events_tenant_slug", "ai_usage_events", ["tenant_slug"])
    op.create_index("ix_ai_usage_events_created_at", "ai_usage_events", ["created_at"])
    op.create_index(
        "ix_ai_usage_events_tenant_created_at", "ai_usage_events", ["tenant_slug", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_events_tenant_created_at", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_created_at", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_tenant_slug", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
