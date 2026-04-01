"""add groups, group_memberships, companies.group_id

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-01

WHAT
----
- `groups`: portfolio / holding entity (id, name, optional name_ar, description, is_active, timestamps).
- `group_memberships`: direct user↔group access (same role vocabulary as company memberships).
- `companies.group_id`: optional FK to groups (NULL = standalone company; all existing rows NULL).

MEMBERSHIP RULE (Phase 1)
-------------------------
Group-scoped access uses **group_memberships** only. Company membership does **not**
imply group membership. See app.models.group module docstring.

SAFETY
------
- No engine or API changes.
- Nullable group_id — backward compatible; no data loss.
- ON DELETE SET NULL on companies.group_id when a group is removed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_add_groups_group_memberships_company_group_id"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("name_ar", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "group_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("group_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="owner"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "group_id", name="uq_group_membership_user_group"),
    )
    op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"], unique=False)
    op.create_index("ix_group_memberships_group_id", "group_memberships", ["group_id"], unique=False)

    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("group_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_companies_group_id_groups",
            "groups",
            ["group_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_companies_group_id", "companies", ["group_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_companies_group_id", table_name="companies")
    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.drop_constraint("fk_companies_group_id_groups", type_="foreignkey")
        batch_op.drop_column("group_id")

    op.drop_index("ix_group_memberships_group_id", table_name="group_memberships")
    op.drop_index("ix_group_memberships_user_id", table_name="group_memberships")
    op.drop_table("group_memberships")
    op.drop_table("groups")
