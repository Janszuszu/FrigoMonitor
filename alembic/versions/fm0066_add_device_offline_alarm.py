"""fm0066_add_device_offline_alarm

Add devices.online column and device_offline_settings table.
This migration was previously applied to production but the file was missing.
This is a stub to satisfy the alembic dependency chain.

Revision ID: fm0066_add_device_offline_alarm
Revises: fm0065_fix_missing_columns
Create Date: 2026-07-12

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fm0066_add_device_offline_alarm"
down_revision = "fm0065_fix_missing_columns"
branch_labels = None
depends_on = None


def upgrade():
    # This migration was already applied to production.
    # The stub exists only to satisfy the alembic dependency chain.
    pass


def downgrade():
    pass
