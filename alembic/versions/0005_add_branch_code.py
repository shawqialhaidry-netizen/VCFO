"""add branches.code column

Revision ID: 0005_add_branch_code
Revises: 0004_fix_missing_columns
Create Date: 2026-03-27

WHAT
----
Adds optional `code` column to branches table.
Used as a short branch identifier (e.g. "BR-01", "RYD", "DXB").

SAFETY
------
- Nullable, no default — zero data loss for existing rows.
- Fully reversible.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005_add_branch_code"
down_revision: Union[str, None] = "0004_fix_missing_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("branches", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "code",
                sa.String(length=50),
                nullable=True,
                comment="Short branch code, e.g. BR-01 or RYD",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("branches", schema=None) as batch_op:
        batch_op.drop_column("code")
