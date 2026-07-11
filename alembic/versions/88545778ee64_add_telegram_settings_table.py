"""add_telegram_settings_table

Revision ID: 88545778ee64
Revises: 'fm0065_fix_missing_columns'
Create Date: 2026-07-11 03:08:33.754739
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '88545778ee64'
down_revision = 'fm0065_fix_missing_columns'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'telegram_settings',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('bot_token', sa.String(length=255), nullable=False, default=''),
        sa.Column('chat_id', sa.String(length=100), nullable=False, default=''),
    )


def downgrade():
    op.drop_table('telegram_settings')
