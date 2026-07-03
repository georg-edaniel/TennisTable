"""add push_subscriptions table

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'h8c9d0e1f2g3'
down_revision = 'g7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'push_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False, unique=True),
        sa.Column('p256dh', sa.Text(), nullable=False),
        sa.Column('auth', sa.Text(), nullable=False),
        sa.Column('user_agent', sa.String(255), server_default=''),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
    )
    op.create_index('ix_push_subscriptions_user_id', 'push_subscriptions', ['user_id'])


def downgrade():
    op.drop_index('ix_push_subscriptions_user_id', 'push_subscriptions')
    op.drop_table('push_subscriptions')
