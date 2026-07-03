"""add coach_id to users

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'g7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users',
        sa.Column('coach_id', sa.Integer(),
                  sa.ForeignKey('users.id'), nullable=True))
    op.create_index('ix_users_coach_id', 'users', ['coach_id'])


def downgrade():
    op.drop_index('ix_users_coach_id', 'users')
    op.drop_column('users', 'coach_id')
