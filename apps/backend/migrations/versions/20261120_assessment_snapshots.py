"""Add capability-protected assessment snapshots.

Revision ID: 20261120_snapshots
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = '20261120_snapshots'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table('assessment_report_snapshots'):
        op.create_table('assessment_report_snapshots',
                        sa.Column('id', sa.String(36), primary_key=True),
                        sa.Column('access_hash', sa.String(64), nullable=False),
                        sa.Column('snapshot_json', sa.Text(), nullable=False),
                        sa.Column('created_at', sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table('assessment_report_snapshots')
