"""add tournaments

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-28 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tournaments',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('max_players', sa.Integer(), nullable=False, server_default='8'),
    )
    op.create_table(
        'tournament_participants',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('tournament_id', sa.Integer(), sa.ForeignKey('tournaments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('player_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('seed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('registered_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('tournament_id', 'player_id', name='uq_tp_tournament_player'),
    )
    op.create_table(
        'tournament_matches',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('tournament_id', sa.Integer(), sa.ForeignKey('tournaments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('match_position', sa.Integer(), nullable=False),
        sa.Column('player1_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('player2_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('winner_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('score_p1', sa.Integer(), nullable=True),
        sa.Column('score_p2', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
    )


def downgrade() -> None:
    op.drop_table('tournament_matches')
    op.drop_table('tournament_participants')
    op.drop_table('tournaments')
