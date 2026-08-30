"""Add human technical-decision labels for CRM match evaluation."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260829_01"
down_revision = "20260826_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "crm_notice_products" not in inspector.get_table_names():
        return
    columns = {row["name"] for row in inspector.get_columns("crm_notice_products")}
    additions = {
        "match_review_verdict": sa.Column("match_review_verdict", sa.String()),
        "match_review_confidence": sa.Column("match_review_confidence", sa.Float()),
        "match_review_reason_codes": sa.Column("match_review_reason_codes", sa.JSON()),
        "match_review_evidence": sa.Column("match_review_evidence", sa.JSON()),
        "match_review_notes": sa.Column("match_review_notes", sa.Text()),
        "match_reviewed_by": sa.Column("match_reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        "match_reviewed_at": sa.Column("match_reviewed_at", sa.DateTime()),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("crm_notice_products", column)


def downgrade() -> None:
    pass
