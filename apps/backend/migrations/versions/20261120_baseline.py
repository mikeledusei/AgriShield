"""Baseline schema: every table that previously existed only via ``create_all``.

Revision ID: 20261120_baseline
Revises:
Create Date: 2026-11-20

Until now ``init_db.py`` created the counties/predictions/reports/uploads tables
with ``Base.metadata.create_all`` while Alembic tracked only the two capability
tables, so the database could never be reproduced or downgraded from migrations
alone. This revision adopts the pre-existing tables idempotently, which keeps it
safe on databases that were already created by ``init_db.py``.
"""
import sqlalchemy as sa
from alembic import op

revision = '20261120_baseline'
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade():
    if not _has_table('counties'):
        op.create_table(
            'counties',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('region', sa.String()),
            sa.Column('latitude', sa.Float()),
            sa.Column('longitude', sa.Float()),
            sa.Column('primary_focus', sa.String()),
        )
        op.create_index('ix_counties_name', 'counties', ['name'], unique=True)
        op.create_index('ix_counties_region', 'counties', ['region'])

    if not _has_table('county_features'):
        op.create_table(
            'county_features',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('county_id', sa.Integer(), sa.ForeignKey('counties.id')),
            sa.Column('record_date', sa.DateTime()),
            sa.Column('rainfall_anomaly_30d', sa.Float()),
            sa.Column('ndvi_pasture_index', sa.Float()),
            sa.Column('temp_max_avg', sa.Float()),
            sa.Column('soil_moisture_deficit', sa.Float()),
        )
        op.create_index('ix_county_features_county_id', 'county_features', ['county_id'])

    if not _has_table('predictions'):
        op.create_table(
            'predictions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('county_id', sa.Integer(), sa.ForeignKey('counties.id')),
            sa.Column('prediction_date', sa.DateTime()),
            sa.Column('focus', sa.String()),
            sa.Column('risk_score', sa.Float()),
            sa.Column('risk_level', sa.String()),
            sa.Column('main_driver', sa.String()),
            sa.Column('recommendation', sa.Text()),
            sa.Column('created_at', sa.DateTime()),
        )
        op.create_index('ix_predictions_county_id', 'predictions', ['county_id'])

    if not _has_table('reports'):
        op.create_table(
            'reports',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('county_id', sa.Integer(), sa.ForeignKey('counties.id')),
            sa.Column('report_type', sa.String()),
            sa.Column('detailed', sa.Boolean()),
            sa.Column('file_path', sa.String()),
            sa.Column('created_at', sa.DateTime()),
        )
        op.create_index('ix_reports_county_id', 'reports', ['county_id'])

    if not _has_table('chat_messages'):
        op.create_table(
            'chat_messages',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('county_name', sa.String()),
            sa.Column('user_message', sa.Text()),
            sa.Column('gria_reply', sa.Text()),
            sa.Column('risk_score', sa.Float()),
            sa.Column('created_at', sa.DateTime()),
        )

    if not _has_table('uploads'):
        op.create_table(
            'uploads',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('file_name', sa.String()),
            sa.Column('file_type', sa.String()),
            sa.Column('county_name', sa.String()),
            sa.Column('risk_score', sa.Float()),
            sa.Column('risk_level', sa.String()),
            sa.Column('created_at', sa.DateTime()),
        )


def downgrade():
    # Only tables owned by this baseline are removed; capability tables belong to
    # the revisions that follow it.
    for table in ('uploads', 'chat_messages', 'reports', 'predictions',
                  'county_features', 'counties'):
        if _has_table(table):
            op.drop_table(table)
