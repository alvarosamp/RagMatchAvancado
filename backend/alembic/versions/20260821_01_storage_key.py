"""Add persistent object-storage reference for edital source PDFs."""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "20260821_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "editais" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("editais")}
    if "storage_key" not in columns:
        op.execute("ALTER TABLE editais ADD COLUMN storage_key VARCHAR")
    indexes = {index["name"] for index in inspector.get_indexes("editais")}
    if "ix_editais_storage_key" not in indexes:
        op.execute("CREATE INDEX ix_editais_storage_key ON editais (storage_key)")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "editais" not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes("editais")}
    if "ix_editais_storage_key" in indexes:
        op.execute("DROP INDEX ix_editais_storage_key")
    columns = {column["name"] for column in inspector.get_columns("editais")}
    if "storage_key" in columns:
        op.execute("ALTER TABLE editais DROP COLUMN storage_key")
