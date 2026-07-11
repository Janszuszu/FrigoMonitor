"""add telegram_notification_sent_at to alarm_events

Revision ID: 78f904508918
Revises: '88545778ee64'
Create Date: 2026-07-11 03:33:14.201127
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '78f904508918'
down_revision = '88545778ee64'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'alarm_events',
        sa.Column('telegram_notification_sent_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column('alarm_events', 'telegram_notification_sent_at')
