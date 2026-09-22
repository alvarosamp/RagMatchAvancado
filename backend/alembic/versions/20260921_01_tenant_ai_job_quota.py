"""Add an optional monthly async-job admission quota per tenant."""

from alembic import op
import sqlalchemy as sa


revision = "20260921_01"
down_revision = "20260918_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("ai_monthly_job_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "ai_monthly_job_limit")
