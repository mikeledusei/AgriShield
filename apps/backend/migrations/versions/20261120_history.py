"""Add a private history table without changing existing reports.

Revision ID: 20261120_history
Revises: 20261120_snapshots
"""
from alembic import op
import sqlalchemy as sa

revision = '20261120_history'
down_revision = '20261120_snapshots'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('assessment_history'):
        op.create_table('assessment_history',
                        sa.Column('id', sa.String(36), primary_key=True),
                        sa.Column('history_key_hash', sa.String(64), nullable=False),
                        sa.Column('snapshot_json', sa.Text(), nullable=False),
                        sa.Column('created_at', sa.DateTime(), nullable=False))
        op.create_index('ix_assessment_history_history_key_hash', 'assessment_history', ['history_key_hash'])
        op.create_index('ix_assessment_history_created_at', 'assessment_history', ['created_at'])


def downgrade():
    op.drop_table('assessment_history')
