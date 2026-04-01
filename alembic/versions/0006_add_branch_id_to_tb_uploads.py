"""add branch_id to tb_uploads

Revision ID: 0006_add_branch_id_to_tb_uploads
Revises: 0005_add_branch_code
Create Date: 2026-03-27

WHAT
----
Adds nullable branch_id column to tb_uploads table.
Links a Trial Balance upload to a specific branch (optional).

NULL  = company-level upload (existing behaviour unchanged)
value = branch-level upload linked to branches.id

SAFETY
------
- Uses ADD COLUMN IF NOT EXISTS → safe to run even if column already exists
- Nullable — all existing rows remain valid (branch_id = NULL)
- No foreign key constraint enforced at DB level (avoids cascade complexity)
- Fully reversible
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision: str = "0006_add_branch_id_to_tb_uploads"
down_revision: Union[str, None] = "0005_add_branch_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists — safe for PostgreSQL and SQLite."""
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if _column_exists("tb_uploads", "branch_id"):
        # Column already present — nothing to do (idempotent)
        return

    with op.batch_alter_table("tb_uploads", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "branch_id",
                sa.String(length=36),
                nullable=True,
                comment="Optional: branch this upload belongs to (NULL = company-level)",
            )
        )


def downgrade() -> None:
    if not _column_exists("tb_uploads", "branch_id"):
        return

    with op.batch_alter_table("tb_uploads", schema=None) as batch_op:
        batch_op.drop_column("branch_id")
