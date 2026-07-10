"""add display_name to devices

Revision ID: 4d254808861d
Revises: fm0063_dedupe_sensors_and_add_sensor_uid_uniques
Create Date: 2026-07-11 01:12:42.237484
"""

from alembic import op
import sqlalchemy as sa


revision = '4d254808861d'
down_revision = 'fm0063_dedupe_sensors_and_add_sensor_uid_uniques'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(100), nullable=True))


def downgrade():
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_column("display_name")
