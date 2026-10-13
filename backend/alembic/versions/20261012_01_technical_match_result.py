"""Persist the complete technical comparison snapshot."""
from alembic import op
import sqlalchemy as sa
revision = '20261012_01'
down_revision = '20260926_01'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('crm_notice_product_matches', sa.Column('technical_result', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('crm_notice_product_matches', 'technical_result')
