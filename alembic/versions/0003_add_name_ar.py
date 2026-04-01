"""add name_ar to companies

Revision ID: 0003_add_name_ar
Revises: 0002_add_tb_type
Create Date: 2026-03-27

WHAT
----
Adds name_ar VARCHAR(255) NULL to companies table.

WHY
---
The Company ORM model defines name_ar (Arabic company name) but the
PostgreSQL database table was created before this column was added,
causing:
  psycopg2.errors.UndefinedColumn: column companies.name_ar does not exist

This migration adds the missing column so the ORM and DB schema are aligned.

SAFETY
------
- Column is nullable with no default -> all existing rows become NULL
- NULL means company has no Arabic name (normal for non-Arabic companies)
- No data is modified, no rows are deleted
- Fully reversible via downgrade()
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_add_name_ar"
down_revision: Union[str, None] = "0002_add_tb_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "name_ar",
                sa.String(length=255),
                nullable=True,
                comment="Arabic name of the company (optional)",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.drop_column("name_ar")
