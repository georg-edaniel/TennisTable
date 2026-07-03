"""add weekly_goals, challenges, clubs

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "j0e1f2g3h4i5"
down_revision = "i9d0e1f2g3h4"
branch_labels = None
depends_on = None


def upgrade():
    # ── weekly_goals ─────────────────────────────────────────────────────────
    op.create_table(
        "weekly_goals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("target_sessions", sa.Integer, server_default="0"),
        sa.Column("target_strokes", sa.Integer, server_default="0"),
        sa.Column("target_matches", sa.Integer, server_default="0"),
        sa.Column("done_sessions", sa.Integer, server_default="0"),
        sa.Column("done_strokes", sa.Integer, server_default="0"),
        sa.Column("done_matches", sa.Integer, server_default="0"),
    )
    op.create_index("ix_weekly_goals_user_id", "weekly_goals", ["user_id"])
    op.create_unique_constraint("uq_user_week", "weekly_goals", ["user_id", "year", "week"])

    # ── challenges ───────────────────────────────────────────────────────────
    op.create_table(
        "challenges",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("challenger_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("challenged_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.String(255), server_default=""),
        sa.Column("status", sa.String(16), server_default="pending"),   # pending|accepted|declined|expired
        sa.Column("session_id", sa.Integer, sa.ForeignKey("game_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("responded_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_challenges_challenged_id", "challenges", ["challenged_id"])
    op.create_index("ix_challenges_challenger_id", "challenges", ["challenger_id"])

    # ── clubs ─────────────────────────────────────────────────────────────────
    op.create_table(
        "clubs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), server_default=""),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("invite_code", sa.String(16), unique=True, nullable=True),
    )
    op.create_table(
        "club_members",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("club_id", sa.Integer, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), server_default="member"),   # owner|coach|member
        sa.Column("joined_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_club_members_club_id", "club_members", ["club_id"])
    op.create_index("ix_club_members_user_id", "club_members", ["user_id"])
    op.create_unique_constraint("uq_club_member", "club_members", ["club_id", "user_id"])


def downgrade():
    op.drop_table("club_members")
    op.drop_table("clubs")
    op.drop_table("challenges")
    op.drop_table("weekly_goals")
