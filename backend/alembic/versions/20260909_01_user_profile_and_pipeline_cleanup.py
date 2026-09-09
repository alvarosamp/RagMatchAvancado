"""Require complete user profiles and normalize terminal CRM notices."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "20260909_01"
down_revision = "20260831_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" in tables:
        columns = {row["name"] for row in inspector.get_columns("users")}
        if "cpf" not in columns:
            op.add_column("users", sa.Column("cpf", sa.String(11), nullable=True))
        if "phone" not in columns:
            op.add_column("users", sa.Column("phone", sa.String(11), nullable=True))
        indexes = {row["name"] for row in inspector.get_indexes("users")}
        if "ix_users_cpf" not in indexes:
            op.create_index("ix_users_cpf", "users", ["cpf"])

    if "crm_notices" in tables:
        bind.execute(text(
            "UPDATE crm_notices SET stage='RESULT' "
            "WHERE upper(outcome) IN ('WON', 'LOST', 'DISQUALIFIED', 'CANCELLED', 'DESERT') "
            "AND upper(stage) <> 'RESULT'"
        ))


def downgrade() -> None:
    # Existing profile data must survive a rollback.
    pass
