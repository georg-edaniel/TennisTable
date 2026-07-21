"""add revoked_tokens table for persistent JWT blacklist

Revision ID: n4i5j6k7l8m9
Revises: m3h4i5j6k7l8
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa

revision = "n4i5j6k7l8m9"
down_revision = "m3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("jti", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("revoked_tokens")
