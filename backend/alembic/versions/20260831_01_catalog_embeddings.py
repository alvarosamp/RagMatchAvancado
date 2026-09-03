"""Persist versioned catalog embeddings for hybrid retrieval."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from pgvector.sqlalchemy import Vector


revision = "20260831_01"
down_revision = "20260830_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "crm_catalog_products" not in inspector.get_table_names():
        return
    columns = {row["name"] for row in inspector.get_columns("crm_catalog_products")}
    additions = {
        "embedding": sa.Column("embedding", Vector(768)),
        "embedding_model": sa.Column("embedding_model", sa.String()),
        "embedding_provider": sa.Column("embedding_provider", sa.String()),
        "embedding_dimensions": sa.Column("embedding_dimensions", sa.Integer()),
        "embedding_source_hash": sa.Column("embedding_source_hash", sa.String(64)),
        "embedding_updated_at": sa.Column("embedding_updated_at", sa.DateTime()),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("crm_catalog_products", column)
    indexes = {row["name"] for row in inspector.get_indexes("crm_catalog_products")}
    if "ix_crm_catalog_products_embedding_source_hash" not in indexes:
        op.create_index(
            "ix_crm_catalog_products_embedding_source_hash",
            "crm_catalog_products",
            ["embedding_source_hash"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "crm_catalog_products" not in inspector.get_table_names():
        return
    indexes = {row["name"] for row in inspector.get_indexes("crm_catalog_products")}
    if "ix_crm_catalog_products_embedding_source_hash" in indexes:
        op.drop_index("ix_crm_catalog_products_embedding_source_hash", table_name="crm_catalog_products")
    columns = {row["name"] for row in inspector.get_columns("crm_catalog_products")}
    for name in (
        "embedding_updated_at",
        "embedding_source_hash",
        "embedding_dimensions",
        "embedding_provider",
        "embedding_model",
        "embedding",
    ):
        if name in columns:
            op.drop_column("crm_catalog_products", name)
