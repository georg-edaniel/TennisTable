"""add badges and streaks

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "i9d0e1f2g3h4"
down_revision = "h8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade():
    # user_badges table
    op.create_table(
        "user_badges",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("badge_key", sa.String(64), nullable=False),
        sa.Column("earned_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])
    op.create_unique_constraint("uq_user_badge", "user_badges", ["user_id", "badge_key"])

    # streak fields on users
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("current_streak", sa.Integer, server_default="0", nullable=False))
        batch.add_column(sa.Column("max_streak", sa.Integer, server_default="0", nullable=False))
        batch.add_column(sa.Column("last_activity_date", sa.Date, nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("last_activity_date")
        batch.drop_column("max_streak")
        batch.drop_column("current_streak")
    op.drop_table("user_badges")
