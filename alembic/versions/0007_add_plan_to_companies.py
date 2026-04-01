"""add plan and trial_ends_at to companies

Revision ID: 0007
Revises: 0006_add_branch_id_to_tb_uploads
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006_add_branch_id_to_tb_uploads'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('companies') as batch_op:
        batch_op.add_column(
            sa.Column('plan', sa.String(20), nullable=False, server_default='trial')
        )
        batch_op.add_column(
            sa.Column('trial_ends_at', sa.DateTime, nullable=True)
        )


def downgrade():
    with op.batch_alter_table('companies') as batch_op:
        batch_op.drop_column('trial_ends_at')
        batch_op.drop_column('plan')
