"""add_telegram_settings_table

Revision ID: 88545778ee64
Revises: 'fm0065_fix_missing_columns'
Create Date: 2026-07-11 03:08:33.754739

This migration was already applied to production via Base.metadata.create_all.
This is a stub to satisfy the alembic dependency chain.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '88545778ee64'
down_revision = 'fm0065_fix_missing_columns'
branch_labels = None
depends_on = None


def upgrade():
    # telegram_settings table already exists in production
    pass


def downgrade():
    pass
