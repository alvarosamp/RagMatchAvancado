"""LPU validity, assigned review and retained process catalog snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '20261014_01'
down_revision = '20261013_01'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('crm_catalog_products')}
    for name, kind in [('lpu_missing_since', sa.Date()), ('lpu_review_deadline', sa.Date()),
                       ('lpu_review_owner_id', sa.Integer()), ('lpu_reviewed_by', sa.Integer()),
                       ('lpu_reviewed_at', sa.DateTime()), ('archived_at', sa.DateTime())]:
        if name not in columns:
            op.add_column('crm_catalog_products', sa.Column(name, kind))
    if 'catalog_snapshot' not in {c['name'] for c in inspector.get_columns('crm_notice_products')}:
        op.add_column('crm_notice_products', sa.Column('catalog_snapshot', sa.JSON()))
    if 'crm_lpu_versions' not in inspector.get_table_names():
        op.create_table('crm_lpu_versions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('version', sa.String(), nullable=False),
            sa.Column('drive_url', sa.Text(), nullable=False),
            sa.Column('valid_until', sa.Date(), nullable=False),
            sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id')),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('superseded_at', sa.DateTime()),
            sa.Column('extensions', sa.JSON(), nullable=False))
        op.create_index('ix_crm_lpu_versions_tenant_id', 'crm_lpu_versions', ['tenant_id'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE crm_lpu_versions ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE crm_lpu_versions FORCE ROW LEVEL SECURITY')
        op.execute("CREATE POLICY crm_lpu_versions_tenant ON crm_lpu_versions USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)")


def downgrade():
    op.drop_table('crm_lpu_versions')
    op.drop_column('crm_notice_products', 'catalog_snapshot')
    for name in ['lpu_missing_since', 'lpu_review_deadline', 'lpu_review_owner_id',
                 'lpu_reviewed_by', 'lpu_reviewed_at', 'archived_at']:
        op.drop_column('crm_catalog_products', name)
