"""add security fields (failed_login_attempts, locked_until)

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "k1f2g3h4i5j6"
down_revision = "j0e1f2g3h4i5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("locked_until", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_login_attempts")
