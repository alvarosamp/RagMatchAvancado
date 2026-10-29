"""Add WhatsApp identity bridge and content-free delivery deduplication."""

import sqlalchemy as sa
from alembic import op

revision = "20261028_01"
down_revision = "20261012_02"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "whatsapp_contacts",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(15), unique=True),
        sa.Column("token_hash", sa.String(64), unique=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("auth_version", sa.Integer(), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_request_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "whatsapp_deliveries",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Identity lookup must work before tenant discovery, as with password reset
    # tokens. Business queries run only after user validation and RLS context.


def downgrade():
    op.drop_table("whatsapp_deliveries")
    op.drop_table("whatsapp_contacts")
