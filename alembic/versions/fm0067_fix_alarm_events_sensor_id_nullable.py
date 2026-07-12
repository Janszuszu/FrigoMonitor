"""fm0067_fix_alarm_events_sensor_id_nullable

Make alarm_events.sensor_id nullable to support device-level alarms (DEVICE_OFFLINE).
Merge heads: fm0066_add_device_offline_alarm and 78f904508918.

Revision ID: fm0067_fix_alarm_events_sensor_id_nullable
Revises: fm0066_add_device_offline_alarm, 78f904508918
Create Date: 2026-07-12

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fm0067_fix_alarm_events_sensor_id_nullable"
down_revision = ("fm0066_add_device_offline_alarm", "78f904508918")
branch_labels = None
depends_on = None


def upgrade():
    # SQLite does not support ALTER COLUMN.
    # We need to recreate the alarm_events table with sensor_id nullable.
    # Use batch mode for SQLite compatibility.
    with op.batch_alter_table("alarm_events") as batch_op:
        batch_op.alter_column("sensor_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    with op.batch_alter_table("alarm_events") as batch_op:
        batch_op.alter_column("sensor_id", existing_type=sa.Integer(), nullable=False)
