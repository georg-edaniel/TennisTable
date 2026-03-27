"""add onboarding_completed

Revision ID: a1b2c3d4e5f6
Revises: 9daa2d4213a7
Create Date: 2026-03-27 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9daa2d4213a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users',
        sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='1')
    )


def downgrade() -> None:
    op.drop_column('users', 'onboarding_completed')
