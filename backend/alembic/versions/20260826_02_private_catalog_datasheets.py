"""Keep catalog datasheets outside the shared document repository."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260826_02"
down_revision = "20260826_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "crm_catalog_product_datasheets" not in tables:
        op.create_table("crm_catalog_product_datasheets",
            sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("catalog_product_id", sa.String(36), sa.ForeignKey("crm_catalog_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("original_filename", sa.String(), nullable=False), sa.Column("stored_filename", sa.String(), nullable=False), sa.Column("storage_path", sa.Text(), nullable=False),
            sa.Column("content_type", sa.String()), sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"), sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("parent_datasheet_id", sa.String(36), sa.ForeignKey("crm_catalog_product_datasheets.id", ondelete="SET NULL")), sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
        op.create_index("ix_crm_catalog_product_datasheets_product_version", "crm_catalog_product_datasheets", ["tenant_id", "catalog_product_id", "version"])
    columns = {item["name"] for item in inspector.get_columns("crm_notice_product_datasheets")}
    if "catalog_datasheet_id" not in columns:
        op.add_column("crm_notice_product_datasheets", sa.Column("catalog_datasheet_id", sa.String(36), nullable=True))
        op.create_foreign_key("fk_notice_product_datasheets_catalog_datasheet", "crm_notice_product_datasheets", "crm_catalog_product_datasheets", ["catalog_datasheet_id"], ["id"], ondelete="SET NULL")
    if "notice_document_id" not in columns:
        op.add_column("crm_notice_product_datasheets", sa.Column("notice_document_id", sa.String(36), nullable=True))
        op.create_foreign_key("fk_notice_product_datasheets_notice_document", "crm_notice_product_datasheets", "crm_notice_documents", ["notice_document_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    pass
