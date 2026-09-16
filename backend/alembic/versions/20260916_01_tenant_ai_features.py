"""Add tenant-scoped AI feature rollout configuration."""

from alembic import op
import sqlalchemy as sa


revision = "20260916_01"
down_revision = "20260910_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("ai_features", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("tenants", "ai_features")
