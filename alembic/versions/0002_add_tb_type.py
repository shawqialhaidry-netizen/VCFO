"""add tb_type to tb_uploads

Revision ID: 0002_add_tb_type
Revises: 0001_baseline
Create Date: 2026-03-25

WHAT
----
Adds tb_type VARCHAR(20) NULL to tb_uploads table.

WHY
---
FIX-2.1 (Phase 2 stabilization): The system now requires knowing whether
an uploaded Trial Balance is pre-closing or post-closing, because the two
types produce different Balance Sheet structures:

  pre_closing  -> Net Profit is NOT yet in equity; system injects it
  post_closing -> Closing entries already moved NP to retained earnings;
                 system does NOT inject it (would double-count)
  NULL         -> Unknown; system defaults to safe behavior (no injection)
                 and sets balance_warning flag

SAFETY
------
- Column is nullable with no default -> all existing rows become NULL
- NULL == "unknown" -> backward-compatible behavior (same as before)
- No data is modified, no rows are deleted
- Fully reversible via downgrade()
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_tb_type"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # render_as_batch=True is set in env.py, so Alembic handles SQLite's
    # limited ALTER TABLE support automatically via table reconstruction.
    with op.batch_alter_table("tb_uploads", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "tb_type",
                sa.String(length=20),
                nullable=True,   # NULL = unknown - backward compatible
                comment="pre_closing | post_closing | NULL(unknown)",
            )
        )


def downgrade() -> None:
    # Remove the column (batch mode required for SQLite DROP COLUMN)
    with op.batch_alter_table("tb_uploads", schema=None) as batch_op:
        batch_op.drop_column("tb_type")
