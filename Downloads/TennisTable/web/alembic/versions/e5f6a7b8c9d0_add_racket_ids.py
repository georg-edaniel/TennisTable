"""add racket_ids to game_sessions

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'game_sessions',
        sa.Column('racket_ids', sa.Text, nullable=True, server_default='[]'),
    )


def downgrade():
    op.drop_column('game_sessions', 'racket_ids')
