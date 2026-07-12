"""add device offline alarm settings and device.online column

Revision ID: fm0066_add_device_offline_alarm
Revises: fm0065_fix_missing_columns
Create Date: 2026-07-12 09:57:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'fm0066_add_device_offline_alarm'
down_revision = '78f904508918'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Add online column to devices table
    existing_device_columns = [row[1] for row in conn.execute(sa.text("PRAGMA table_info('devices')")).fetchall()]
    if "online" not in existing_device_columns:
        conn.execute(sa.text("ALTER TABLE devices ADD COLUMN online BOOLEAN NOT NULL DEFAULT 1"))

    # Create device_offline_settings table
    existing_tables = [row[0] for row in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
    if "device_offline_settings" not in existing_tables:
        op.create_table(
            "device_offline_settings",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
            sa.Column("offline_timeout_minutes", sa.Integer(), nullable=False, default=5),
            sa.Column("severity", sa.String(20), nullable=False, default="CRITICAL"),
            sa.Column("notifications_enabled", sa.Boolean(), nullable=False, default=True),
        )


def downgrade():
    op.drop_table("device_offline_settings")
    conn = op.get_bind()
    existing_device_columns = [row[1] for row in conn.execute(sa.text("PRAGMA table_info('devices')")).fetchall()]
    if "online" in existing_device_columns:
        conn.execute(sa.text("ALTER TABLE devices DROP COLUMN online"))
