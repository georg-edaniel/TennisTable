"""add points_log and set_initial_server_id for proper undo replay

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "m3h4i5j6k7l8"
down_revision = "l2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("game_sessions") as batch_op:
        batch_op.add_column(sa.Column("points_log", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("set_initial_server_id", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("game_sessions") as batch_op:
        batch_op.drop_column("set_initial_server_id")
        batch_op.drop_column("points_log")
