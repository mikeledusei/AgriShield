"""Index the report snapshot retention column.

Revision ID: 20261120_retention_indexes
Revises: 20261120_history

Every report save runs ``DELETE ... WHERE created_at < cutoff``. The history table
already carried that index; the snapshot table did not, so the delete was a
sequential scan that grows with the table.
"""
import sqlalchemy as sa
from alembic import op

revision = '20261120_retention_indexes'
down_revision = '20261120_history'
branch_labels = None
depends_on = None

INDEX = 'ix_assessment_report_snapshots_created_at'
TABLE = 'assessment_report_snapshots'


def upgrade():
    existing = {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(TABLE)}
    if INDEX not in existing:
        op.create_index(INDEX, TABLE, ['created_at'])


def downgrade():
    op.drop_index(INDEX, table_name=TABLE)
