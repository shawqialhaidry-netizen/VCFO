"""add account mapping overrides

Revision ID: 0010_add_account_mapping_overrides
Revises: 0009_add_manager_name_to_branches
Create Date: 2026-04-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_add_account_mapping_overrides"
down_revision: Union[str, None] = "0009_add_manager_name_to_branches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_mapping_overrides",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("account_code", sa.String(length=255), nullable=False),
        sa.Column("account_name_hint", sa.String(length=255), nullable=True),
        sa.Column("mapped_type", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "account_code",
            name="uq_account_mapping_overrides_company_account_code",
        ),
    )
    op.create_index(
        "ix_account_mapping_overrides_company_id",
        "account_mapping_overrides",
        ["company_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_account_mapping_overrides_company_id", table_name="account_mapping_overrides")
    op.drop_table("account_mapping_overrides")
