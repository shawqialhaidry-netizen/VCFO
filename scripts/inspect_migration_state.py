"""Read-only: alembic_version + groups / group_memberships / companies.group_id. No DDL."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env", override=False)

raw = (os.environ.get("DATABASE_URL") or "").strip()
if not raw:
    print("DATABASE_URL missing", file=sys.stderr)
    sys.exit(1)

# Normalize driver for SQLAlchemy
url = raw.replace("postgresql+psycopg2://", "postgresql://")
engine = create_engine(url, pool_pre_ping=True)

with engine.connect() as conn:
    # 1) alembic_version
    rev = None
    try:
        r = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        row = r.fetchone()
        rev = row[0] if row else None
    except Exception as e:
        rev = f"<error: {e}>"

    # 2) tables
    def table_exists(name: str) -> bool:
        q = text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :t
            """
        )
        return conn.execute(q, {"t": name}).fetchone() is not None

    groups_tbl = table_exists("groups")
    gm_tbl = table_exists("group_memberships")

    # 3) companies.group_id
    col = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'companies' AND column_name = 'group_id'
            """
        )
    ).fetchone()
    group_id_col = col is not None

    # FK name from 0008 (for context)
    fk = conn.execute(
        text(
            """
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'public' AND tc.table_name = 'companies'
              AND tc.constraint_type = 'FOREIGN KEY' AND kcu.column_name = 'group_id'
            LIMIT 1
            """
        )
    ).fetchone()
    fk_name = fk[0] if fk else None

print("ALEMBIC_VERSION:", rev)
print("TABLE groups:", groups_tbl)
print("TABLE group_memberships:", gm_tbl)
print("COLUMN companies.group_id:", group_id_col)
print("FK companies.group_id -> groups:", fk_name or "(none)")
