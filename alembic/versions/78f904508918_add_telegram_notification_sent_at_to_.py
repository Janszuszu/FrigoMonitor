"""add telegram_notification_sent_at to alarm_events

Revision ID: 78f904508918
Revises: '88545778ee64'
Create Date: 2026-07-11 03:33:14.201127

This migration was already applied to production via Base.metadata.create_all.
This is a stub to satisfy the alembic dependency chain.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '78f904508918'
down_revision = '88545778ee64'
branch_labels = None
depends_on = None


def upgrade():
    # telegram_notification_sent_at column already exists in production
    pass


def downgrade():
    pass
