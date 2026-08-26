"""Add requester acknowledgement for completed document signatures."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "20260825_01"
down_revision = "20260821_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "document_signature_requests" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("document_signature_requests")}
    if "requester_notification_dismissed" not in columns:
        op.add_column(
            "document_signature_requests",
            sa.Column("requester_notification_dismissed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "document_signature_requests" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("document_signature_requests")}
    if "requester_notification_dismissed" in columns:
        op.drop_column("document_signature_requests", "requester_notification_dismissed")
