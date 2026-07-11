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
    conn = op.get_bind()

    # Check if columns already exist in sensors table
    existing_columns = [row[1] for row in conn.execute("PRAGMA table_info('sensors')").fetchall()]

    # Add no_data alarm columns to sensors using direct SQL (avoid batch_alter_table which creates temp tables)
    if "alarm_no_data_enabled" not in existing_columns:
        conn.execute(sa.text("ALTER TABLE sensors ADD COLUMN alarm_no_data_enabled BOOLEAN NOT NULL DEFAULT 0"))
    if "alarm_no_data_timeout" not in existing_columns:
        conn.execute(sa.text("ALTER TABLE sensors ADD COLUMN alarm_no_data_timeout INTEGER NOT NULL DEFAULT 15"))
    if "alarm_no_data_since" not in existing_columns:
        conn.execute(sa.text("ALTER TABLE sensors ADD COLUMN alarm_no_data_since DATETIME"))
    if "alarm_no_data_state" not in existing_columns:
        conn.execute(sa.text("ALTER TABLE sensors ADD COLUMN alarm_no_data_state VARCHAR(20) NOT NULL DEFAULT 'NORMAL'"))

    # Create alarm_events table if not exists
    existing_tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if "alarm_events" not in existing_tables:
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
    conn = op.get_bind()
    existing_columns = [row[1] for row in conn.execute("PRAGMA table_info('sensors')").fetchall()]
    if "alarm_no_data_state" in existing_columns:
        # SQLite doesn't support DROP COLUMN in older versions, but newer ones do
        conn.execute(sa.text("ALTER TABLE sensors DROP COLUMN alarm_no_data_state"))
    if "alarm_no_data_since" in existing_columns:
        conn.execute(sa.text("ALTER TABLE sensors DROP COLUMN alarm_no_data_since"))
    if "alarm_no_data_timeout" in existing_columns:
        conn.execute(sa.text("ALTER TABLE sensors DROP COLUMN alarm_no_data_timeout"))
    if "alarm_no_data_enabled" in existing_columns:
        conn.execute(sa.text("ALTER TABLE sensors DROP COLUMN alarm_no_data_enabled"))
