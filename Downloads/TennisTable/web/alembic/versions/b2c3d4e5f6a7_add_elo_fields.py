"""add elo fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-27 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('elo_rating',      sa.Float(),   nullable=False, server_default='1500.0'))
    op.add_column('users', sa.Column('elo_matches',     sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('elo_wins',        sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('elo_last_change', sa.Float(),   nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('users', 'elo_last_change')
    op.drop_column('users', 'elo_wins')
    op.drop_column('users', 'elo_matches')
    op.drop_column('users', 'elo_rating')
