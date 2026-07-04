"""add last_value and last_measurement to sensors

Revision ID: fm0061_add_sensor_last_fields
Revises: 
Create Date: 2026-07-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fm0061_add_sensor_last_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = bind.execute(sa.text("PRAGMA table_info('sensors')")).fetchall()
    cols = [row[1] for row in insp]
    # Add columns only if they don't exist yet
    if 'last_value' not in cols or 'last_measurement' not in cols:
        with op.batch_alter_table("sensors", schema=None) as batch_op:
            if 'last_value' not in cols:
                batch_op.add_column(sa.Column('last_value', sa.Float(), nullable=True))
            if 'last_measurement' not in cols:
                batch_op.add_column(sa.Column('last_measurement', sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = bind.execute(sa.text("PRAGMA table_info('sensors')")).fetchall()
    cols = [row[1] for row in insp]
    # Drop columns only if present
    if 'last_value' in cols or 'last_measurement' in cols:
        with op.batch_alter_table("sensors", schema=None) as batch_op:
            if 'last_measurement' in cols:
                batch_op.drop_column('last_measurement')
            if 'last_value' in cols:
                batch_op.drop_column('last_value')
