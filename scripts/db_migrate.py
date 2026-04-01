"""
scripts/db_migrate.py - VCFO Schema Migration Manager

The application uses PostgreSQL only. The optional --db PATH mode targeting a SQLite
file is deprecated (legacy); prefer DATABASE_URL + PostgreSQL.

Usage:
  python scripts/db_migrate.py status        -- show applied / pending
  python scripts/db_migrate.py up            -- apply all pending
  python scripts/db_migrate.py up --dry-run  -- preview without applying
  python scripts/db_migrate.py history       -- full history log
  python scripts/db_migrate.py --db PATH ... -- explicit DB file (deprecated: SQLite)

HOW TO ADD A FUTURE MIGRATION:
  1. Add a new Migration entry to MIGRATIONS list below
  2. Run: python scripts/db_migrate.py up
  Done.

RULES:
  - Never edit an applied migration
  - Never remove entries from the list
  - Always use ADD COLUMN with nullable=True or a safe DEFAULT
  - Never DROP or RENAME (portability / safety)
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
#  MIGRATION REGISTRY
#  Add new entries AT THE BOTTOM. Never edit existing entries.
# ============================================================

MIGRATIONS = [
    {
        "version":     "2026_001",
        "description": "Add tb_type to tb_uploads (pre_closing / post_closing / NULL)",
        "sql": [
            "ALTER TABLE tb_uploads ADD COLUMN tb_type VARCHAR(20)",
        ],
    },

    # TEMPLATE - copy and fill in for the next migration:
    # {
    #     "version":     "2026_003",
    #     "description": "Short description here",
    #     "sql": [
    #         "ALTER TABLE some_table ADD COLUMN new_col VARCHAR(50)",
    #     ],
    # },

    {
        "version":     "2026_002",
        "description": "Add name_ar to companies (Arabic company name, nullable)",
        "sql": [
            "ALTER TABLE companies ADD COLUMN name_ar VARCHAR(255)",
        ],
    },
]

TRACKING_TABLE = "schema_migrations"

CREATE_TRACKING_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at  TEXT NOT NULL
)
"""


# ============================================================
#  INTERNAL HELPERS
# ============================================================

def _connect(db_path):
    """
    Connect to SQLite or PostgreSQL.
    PostgreSQL is detected via DATABASE_URL environment variable.
    """
    import os
    db_url = os.getenv("DATABASE_URL", "")

    if db_url.startswith("postgresql"):
        return _connect_pg(db_url)

    # SQLite path
    p = Path(db_path)
    if not p.exists():
        print("ERROR: database not found: {}".format(p.resolve()))
        sys.exit(1)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class _PGConn:
    """Minimal sqlite3-compatible wrapper around psycopg2 connection."""
    def __init__(self, conn):
        self._conn = conn
        self._is_pg = True

    def execute(self, sql, params=()):
        # Convert sqlite3 ? placeholders to psycopg2 %s
        pg_sql = sql.replace("?", "%s")
        cur = self._conn.cursor()
        cur.execute(pg_sql, params)
        self._cur = cur
        return _PGCursor(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


class _PGCursor:
    def __init__(self, cur):
        self._cur = cur

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in self._cur.description]
        return [_PGRow(dict(zip(cols, row))) for row in rows]

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in self._cur.description]
        return _PGRow(dict(zip(cols, row)))


class _PGRow(dict):
    """Dict that also supports r["key"] sqlite3.Row-style access."""
    def __getitem__(self, key):
        return super().__getitem__(key)


def _connect_pg(db_url):
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        host = db_url.split("@")[-1].split("/")[0] if "@" in db_url else db_url
        print("Connected to PostgreSQL: {}".format(host))
        return _PGConn(conn)
    except Exception as e:
        print("ERROR: Cannot connect to PostgreSQL: {}".format(e))
        sys.exit(1)


def _ensure_tracking(conn):
    conn.execute(CREATE_TRACKING_SQL)
    conn.commit()


def _applied_versions(conn):
    rows = conn.execute(
        "SELECT version FROM schema_migrations"
    ).fetchall()
    return {r["version"] for r in rows}


def _pending(conn):
    done = _applied_versions(conn)
    return [m for m in MIGRATIONS if m["version"] not in done]


def _col_exists(conn, table, col):
    """Check column existence for SQLite (PRAGMA) or PostgreSQL (information_schema)."""
    import os
    if os.getenv("DATABASE_URL", "").startswith("postgresql"):
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s",
            (table, col)
        ).fetchall()
        return len(rows) > 0
    rows = conn.execute("PRAGMA table_info({})".format(table)).fetchall()
    return any(r["name"] == col for r in rows)


def _apply(conn, migration, dry_run):
    v   = migration["version"]
    desc = migration["description"]
    print("  [{}] {}".format(v, desc))
    for sql in migration["sql"]:
        stmt = sql.strip()
        print("    SQL: {}{}".format(stmt[:80], "..." if len(stmt) > 80 else ""))
        if not dry_run:
            conn.execute(stmt)
    if not dry_run:
        import os
        if os.getenv("DATABASE_URL", "").startswith("postgresql"):
            conn.execute(
                "INSERT INTO schema_migrations (version, description, applied_at)"
                " VALUES (%s, %s, %s)",
                (v, desc, datetime.now(timezone.utc).isoformat()),
            )
        else:
            conn.execute(
                "INSERT INTO schema_migrations (version, description, applied_at)"
                " VALUES (?, ?, ?)",
                (v, desc, datetime.now(timezone.utc).isoformat()),
            )
        conn.commit()
        print("    OK - applied and recorded.")
    else:
        print("    (dry-run - not applied)")


# ============================================================
#  COMMANDS
# ============================================================

def cmd_status(db_path):
    conn = _connect(db_path)
    _ensure_tracking(conn)
    done     = _applied_versions(conn)
    pending  = _pending(conn)
    print("\nMigration status  ({} total)".format(len(MIGRATIONS)))
    print("-" * 60)
    for m in MIGRATIONS:
        state = "OK applied" if m["version"] in done else "PENDING   "
        print("  {}  {}  {}".format(state, m["version"], m["description"]))
    print()
    if pending:
        print("  {} pending - run: python scripts/db_migrate.py up".format(len(pending)))
    else:
        print("  All migrations applied. Schema is up to date.")
    print()
    conn.close()


def cmd_up(db_path, dry_run):
    conn = _connect(db_path)
    _ensure_tracking(conn)
    to_run = _pending(conn)
    if not to_run:
        print("Nothing to do - all migrations already applied.")
        conn.close()
        return
    mode = "(DRY RUN)" if dry_run else ""
    print("\nApplying {} migration(s) {}".format(len(to_run), mode))
    print("-" * 60)
    for m in to_run:
        _apply(conn, m, dry_run)
    print()
    if dry_run:
        print("Dry run complete. No changes made.")
    else:
        print("Done. Restart the API server.")
    print()
    conn.close()


def cmd_history(db_path):
    conn = _connect(db_path)
    _ensure_tracking(conn)
    rows = conn.execute(
        "SELECT version, description, applied_at"
        " FROM schema_migrations ORDER BY version"
    ).fetchall()
    if not rows:
        print("No migrations applied yet.")
        conn.close()
        return
    print("\nApplied migrations ({})".format(len(rows)))
    print("-" * 70)
    for r in rows:
        print("  {}  {}  {}".format(
            r["version"], r["applied_at"][:19], r["description"]
        ))
    print()
    conn.close()


# ============================================================
#  ENTRY POINT
# ============================================================

def main():
    ap = argparse.ArgumentParser(
        description="VCFO database migration manager"
    )
    ap.add_argument(
        "command",
        choices=["status", "up", "history"],
        help="status | up | history",
    )
    ap.add_argument(
        "--db",
        default="data/vcfo.db",
        help="Path to SQLite DB (default: data/vcfo.db)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without applying (only for 'up')",
    )
    args = ap.parse_args()

    if args.command == "status":
        cmd_status(args.db)
    elif args.command == "up":
        cmd_up(args.db, dry_run=args.dry_run)
    elif args.command == "history":
        cmd_history(args.db)


if __name__ == "__main__":
    main()
