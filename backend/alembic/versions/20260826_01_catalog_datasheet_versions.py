"""Store catalog datasheets and their inclusion in CRM notice documentation."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260826_01"
down_revision = "20260825_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "document_files" in tables:
        columns = {column["name"] for column in inspector.get_columns("document_files")}
        if "catalog_product_id" not in columns:
            op.add_column("document_files", sa.Column("catalog_product_id", sa.String(length=36), nullable=True))
            op.create_foreign_key("fk_document_files_catalog_product", "document_files", "crm_catalog_products", ["catalog_product_id"], ["id"], ondelete="SET NULL")
            op.create_index("ix_document_files_catalog_product_id", "document_files", ["catalog_product_id"])
    if "crm_notice_product_datasheets" not in tables:
        op.create_table(
            "crm_notice_product_datasheets",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("notice_id", sa.String(length=36), sa.ForeignKey("crm_notices.id", ondelete="CASCADE"), nullable=False),
            sa.Column("notice_product_id", sa.String(length=36), sa.ForeignKey("crm_notice_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("catalog_product_id", sa.String(length=36), sa.ForeignKey("crm_catalog_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_file_id", sa.String(length=36), sa.ForeignKey("document_files.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("notice_product_id", name="uq_crm_notice_product_datasheets_notice_product"),
        )
        op.create_index("ix_crm_notice_product_datasheets_notice", "crm_notice_product_datasheets", ["tenant_id", "notice_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "crm_notice_product_datasheets" in tables:
        op.drop_index("ix_crm_notice_product_datasheets_notice", table_name="crm_notice_product_datasheets")
        op.drop_table("crm_notice_product_datasheets")
    if "document_files" in tables:
        columns = {column["name"] for column in inspector.get_columns("document_files")}
        if "catalog_product_id" in columns:
            op.drop_index("ix_document_files_catalog_product_id", table_name="document_files")
            op.drop_constraint("fk_document_files_catalog_product", "document_files", type_="foreignkey")
            op.drop_column("document_files", "catalog_product_id")
