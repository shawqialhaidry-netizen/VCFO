"""baseline: stamp existing schema

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-03-25

PURPOSE
-------
This is the BASELINE migration. It does NOT create any tables.
The tables already exist because the app used init_db() / create_all()
before Alembic was introduced.

This revision simply marks the existing schema as the starting point
so that future migrations know what to build on.

Running `alembic upgrade head` on a fresh database will execute all
migrations in sequence - baseline does nothing (tables already exist
from create_all in init_db), and subsequent migrations add columns.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline: tables already exist from init_db() / create_all().
    # Nothing to create here - this revision just stamps the starting point.
    pass


def downgrade() -> None:
    # Cannot roll back to "before the app existed".
    pass
