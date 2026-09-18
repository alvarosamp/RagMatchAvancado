"""Add job idempotency keys and structured failure codes."""

from alembic import op
import sqlalchemy as sa


revision = "20260918_01"
down_revision = "20260916_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.add_column("jobs", sa.Column("failure_code", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_jobs_tenant_type_idempotency",
        "jobs",
        ["tenant_id", "job_type", "idempotency_key"],
    )
    op.create_index("ix_jobs_failure_code", "jobs", ["failure_code"])


def downgrade() -> None:
    op.drop_index("ix_jobs_failure_code", table_name="jobs")
    op.drop_constraint("uq_jobs_tenant_type_idempotency", "jobs", type_="unique")
    op.drop_column("jobs", "failure_code")
    op.drop_column("jobs", "idempotency_key")
