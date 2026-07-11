"""add missing no_data columns and alarm_events table

Revision ID: fm0065_fix_missing_columns
Revises: fm0064_add_alarm_events_table_and_no_data_columns
Create Date: 2026-07-11 02:07:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'fm0065_fix_missing_columns'
down_revision = 'fm0064_add_alarm_events_table_and_no_data_columns'
branch_labels = None
depends_on = None


def upgrade():
    # Add no_data alarm columns to sensors
    with op.batch_alter_table("sensors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("alarm_no_data_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("alarm_no_data_timeout", sa.Integer(), nullable=False, server_default=sa.text("15")))
        batch_op.add_column(sa.Column("alarm_no_data_since", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("alarm_no_data_state", sa.String(20), nullable=False, server_default=sa.text("'NORMAL'")))

    # Create alarm_events table for alarm history
    op.create_table(
        "alarm_events",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("sensor_id", sa.Integer(), sa.ForeignKey("sensors.id"), nullable=False, index=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=True, index=True),
        sa.Column("alarm_type", sa.String(20), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("pending_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("alarm_events")
    with op.batch_alter_table("sensors", schema=None) as batch_op:
        batch_op.drop_column("alarm_no_data_state")
        batch_op.drop_column("alarm_no_data_since")
        batch_op.drop_column("alarm_no_data_timeout")
        batch_op.drop_column("alarm_no_data_enabled")
