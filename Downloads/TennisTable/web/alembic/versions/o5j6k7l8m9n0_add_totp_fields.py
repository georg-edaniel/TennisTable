"""add totp fields

Revision ID: o5j6k7l8m9n0
Revises: n4i5j6k7l8m9
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa

revision = 'o5j6k7l8m9n0'
down_revision = 'n4i5j6k7l8m9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('totp_secret', sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('totp_enabled', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('totp_backup_codes', sa.String(), nullable=False, server_default='[]'))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('totp_backup_codes')
        batch_op.drop_column('totp_enabled')
        batch_op.drop_column('totp_secret')
