"""Track provider failures without storing error messages or payloads."""

from alembic import op
import sqlalchemy as sa


revision = "20260922_01"
down_revision = "20260921_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_usage_events",
        sa.Column("succeeded", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("ai_usage_events", sa.Column("failure_code", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_usage_events", "failure_code")
    op.drop_column("ai_usage_events", "succeeded")
