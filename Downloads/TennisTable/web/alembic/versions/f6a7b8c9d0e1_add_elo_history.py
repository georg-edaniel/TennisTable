"""add elo history table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'elo_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.Integer(),
                  sa.ForeignKey('game_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('elo_before', sa.Float(), nullable=False),
        sa.Column('elo_after', sa.Float(), nullable=False),
        sa.Column('delta', sa.Float(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_elo_history_user_id', 'elo_history', ['user_id'])


def downgrade():
    op.drop_index('ix_elo_history_user_id', 'elo_history')
    op.drop_table('elo_history')
