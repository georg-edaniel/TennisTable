"""add rules and AI fields (best_of, server_id, deuce, llm_coach_tip)

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "l2g3h4i5j6k7"
down_revision = "k1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("game_sessions") as batch_op:
        batch_op.add_column(sa.Column("best_of", sa.Integer(), nullable=False, server_default="3"))
        batch_op.add_column(sa.Column("server_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("server_points", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("deuce_active", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("final_set_notified", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("llm_coach_tip", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("game_sessions") as batch_op:
        batch_op.drop_column("llm_coach_tip")
        batch_op.drop_column("final_set_notified")
        batch_op.drop_column("deuce_active")
        batch_op.drop_column("server_points")
        batch_op.drop_column("server_id")
        batch_op.drop_column("best_of")
