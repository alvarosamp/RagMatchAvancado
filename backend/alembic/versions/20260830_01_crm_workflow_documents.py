"""CRM workflow, suspension, document generation and audit metadata."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "20260830_01"
down_revision = "20260829_01"
branch_labels = None
depends_on = None


def _columns(inspector, table: str) -> set[str]:
    return {row["name"] for row in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" in tables and "updated_at" not in _columns(inspector, "users"):
        op.add_column("users", sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))

    if "user_role_audit" not in tables:
        op.create_table(
            "user_role_audit",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("administrator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("previous_role", sa.String(), nullable=False),
            sa.Column("new_role", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_user_role_audit_tenant_id", "user_role_audit", ["tenant_id"])

    if "crm_notices" in tables and "bi_general_risks" not in _columns(inspector, "crm_notices"):
        op.add_column("crm_notices", sa.Column("bi_general_risks", sa.Text()))

    if "crm_notice_products" in tables:
        try:
            op.alter_column("crm_notice_products", "quantity", existing_type=sa.Float(), nullable=True, server_default=None)
        except Exception:
            pass

    if "crm_notice_sessions" in tables:
        session_columns = _columns(inspector, "crm_notice_sessions")
        additions = {
            "suspension_reason": sa.Column("suspension_reason", sa.Text()),
            "suspended_at": sa.Column("suspended_at", sa.DateTime()),
            "suspended_by": sa.Column("suspended_by", sa.Integer(), sa.ForeignKey("users.id")),
            "resumed_at": sa.Column("resumed_at", sa.DateTime()),
            "resumed_by": sa.Column("resumed_by", sa.Integer(), sa.ForeignKey("users.id")),
        }
        for name, column in additions.items():
            if name not in session_columns:
                op.add_column("crm_notice_sessions", column)

    if "crm_post_auction_transitions" not in tables:
        op.create_table(
            "crm_post_auction_transitions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("notice_id", sa.String(36), sa.ForeignKey("crm_notices.id", ondelete="CASCADE"), nullable=False),
            sa.Column("from_phase", sa.String()),
            sa.Column("to_phase", sa.String(), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("note", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_crm_post_auction_transitions_tenant_id", "crm_post_auction_transitions", ["tenant_id"])
        op.create_index("ix_crm_post_auction_transitions_notice_id", "crm_post_auction_transitions", ["notice_id"])
        op.create_index("ix_crm_post_auction_transition_notice_created", "crm_post_auction_transitions", ["tenant_id", "notice_id", "created_at"])

    if "document_files" in tables:
        document_columns = _columns(inspector, "document_files")
        additions = {
            "template_id": sa.Column("template_id", sa.String()),
            "template_version": sa.Column("template_version", sa.String()),
            "generated_by": sa.Column("generated_by", sa.Integer(), sa.ForeignKey("users.id")),
            "signer_id": sa.Column("signer_id", sa.Integer(), sa.ForeignKey("users.id")),
            "signature_status": sa.Column("signature_status", sa.String(), server_default="not_requested", nullable=False),
            "generation_key": sa.Column("generation_key", sa.String()),
        }
        for name, column in additions.items():
            if name not in document_columns:
                op.add_column("document_files", column)
        for name in ("template_id", "generated_by", "signer_id", "signature_status", "generation_key"):
            try:
                op.create_index(f"ix_document_files_{name}", "document_files", [name])
            except Exception:
                pass
        try:
            op.create_index("uq_document_files_tenant_generation_key", "document_files", ["tenant_id", "generation_key"], unique=True)
        except Exception:
            pass

    # converted/closed cease to be pipeline phases; outcomes preserve their meaning.
    if "crm_notices" in tables:
        # SQLAlchemy Enum(native_enum=False) persists member names in this schema.
        bind.execute(text("UPDATE crm_notices SET outcome='WON', post_auction_phase='HOMOLOGATION', stage='RESULT' WHERE lower(post_auction_phase)='converted'"))
        bind.execute(text("UPDATE crm_notices SET outcome='LOST', post_auction_phase='HOMOLOGATION', stage='RESULT' WHERE lower(post_auction_phase)='closed'"))


def downgrade() -> None:
    # Deliberately non-destructive: production data and generated-document audit must survive rollback.
    pass
