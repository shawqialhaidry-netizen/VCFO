"""add manager_name to branches

Revision ID: 0009_add_manager_name_to_branches
Revises: 0008_add_groups_group_memberships_company_group_id
Create Date: 2026-04-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_add_manager_name_to_branches"
down_revision: Union[str, None] = "0008_add_groups_group_memberships_company_group_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("branches", schema=None) as batch_op:
        batch_op.add_column(sa.Column("manager_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("branches", schema=None) as batch_op:
        batch_op.drop_column("manager_name")
