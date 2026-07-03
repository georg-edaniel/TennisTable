"""add subscription and password reset

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-28 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token', sa.String(), nullable=False, unique=True, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'users',
        sa.Column('subscription_tier', sa.String(), nullable=False, server_default='free'),
    )


def downgrade() -> None:
    op.drop_column('users', 'subscription_tier')
    op.drop_table('password_reset_tokens')
