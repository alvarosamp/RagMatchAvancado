"""Add first-class observability fields to asynchronous jobs."""

from alembic import op
import sqlalchemy as sa


revision = "20260916_02"
down_revision = "20260916_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("correlation_id", sa.String(36), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
    )
    op.add_column("jobs", sa.Column("last_enqueued_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE jobs SET correlation_id = id WHERE correlation_id IS NULL")
    op.alter_column("jobs", "correlation_id", nullable=False)
    op.create_index("ix_jobs_correlation_id", "jobs", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_correlation_id", table_name="jobs")
    op.drop_column("jobs", "last_enqueued_at")
    op.drop_column("jobs", "max_attempts")
    op.drop_column("jobs", "attempt_count")
    op.drop_column("jobs", "correlation_id")
