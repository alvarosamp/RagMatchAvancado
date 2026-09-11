"""Add labeling, shipment and fulfillment history for won CRM items."""

from alembic import op
import sqlalchemy as sa


revision = "20260910_01"
down_revision = "20260909_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_item_fulfillments",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("item_result_id", sa.String(36), nullable=True),
        sa.Column("manual_description", sa.Text(), nullable=True),
        sa.Column("manual_quantity", sa.Float(), nullable=True),
        sa.Column("manual_unit", sa.String(), nullable=True),
        sa.Column("manual_item_number", sa.String(), nullable=True),
        sa.Column("manual_reference", sa.String(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("serial_numbers", sa.JSON(), nullable=False),
        sa.Column("label_notes", sa.Text(), nullable=True),
        sa.Column("labeled_at", sa.DateTime(), nullable=True),
        sa.Column("labeled_by", sa.Integer(), nullable=True),
        sa.Column("carrier", sa.String(), nullable=True),
        sa.Column("shipment_reference", sa.String(), nullable=True),
        sa.Column("shipped_at", sa.DateTime(), nullable=True),
        sa.Column("estimated_delivery_at", sa.DateTime(), nullable=True),
        sa.Column("shipment_notes", sa.Text(), nullable=True),
        sa.Column("shipped_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["item_result_id"], ["crm_notice_item_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["labeled_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["shipped_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_result_id", name="uq_crm_item_fulfillments_result"),
    )
    op.create_index("ix_crm_item_fulfillments_tenant_id", "crm_item_fulfillments", ["tenant_id"])
    op.create_index("ix_crm_item_fulfillments_item_result_id", "crm_item_fulfillments", ["item_result_id"])
    op.create_index("ix_crm_item_fulfillments_tenant_shipped", "crm_item_fulfillments", ["tenant_id", "shipped_at"])

    op.create_table(
        "crm_item_fulfillment_history",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("fulfillment_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["fulfillment_id"], ["crm_item_fulfillments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_item_fulfillment_history_tenant_id", "crm_item_fulfillment_history", ["tenant_id"])
    op.create_index("ix_crm_item_fulfillment_history_fulfillment_id", "crm_item_fulfillment_history", ["fulfillment_id"])
    op.create_index("ix_crm_item_fulfillment_history_item_created", "crm_item_fulfillment_history", ["tenant_id", "fulfillment_id", "created_at"])

    op.create_table(
        "crm_item_fulfillment_invoices",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("fulfillment_id", sa.String(36), nullable=False),
        sa.Column("document_file_id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["fulfillment_id"], ["crm_item_fulfillments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_file_id"], ["document_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fulfillment_id", "document_file_id", name="uq_crm_item_fulfillment_invoice"),
    )
    op.create_index("ix_crm_item_fulfillment_invoices_tenant_id", "crm_item_fulfillment_invoices", ["tenant_id"])
    op.create_index("ix_crm_item_fulfillment_invoices_fulfillment_id", "crm_item_fulfillment_invoices", ["fulfillment_id"])
    op.create_index("ix_crm_item_fulfillment_invoices_document_file_id", "crm_item_fulfillment_invoices", ["document_file_id"])
    op.create_index("ix_crm_item_fulfillment_invoice_tenant_document", "crm_item_fulfillment_invoices", ["tenant_id", "document_file_id"])


def downgrade() -> None:
    op.drop_table("crm_item_fulfillment_invoices")
    op.drop_table("crm_item_fulfillment_history")
    op.drop_table("crm_item_fulfillments")
