"""Differentiate repository signed archives from edital-only signed files."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260826_03"
down_revision = "20260826_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "document_files" in inspector.get_table_names():
        columns = {row["name"] for row in inspector.get_columns("document_files")}
        if "is_repository_signed_archive" not in columns:
            op.add_column("document_files", sa.Column("is_repository_signed_archive", sa.Boolean(), nullable=False, server_default=sa.false()))
            op.create_index("ix_document_files_repository_signed_archive", "document_files", ["is_repository_signed_archive"])
    if "document_signature_requests" in inspector.get_table_names():
        columns = {row["name"] for row in inspector.get_columns("document_signature_requests")}
        if "archive_signed_result" not in columns:
            op.add_column("document_signature_requests", sa.Column("archive_signed_result", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    pass
