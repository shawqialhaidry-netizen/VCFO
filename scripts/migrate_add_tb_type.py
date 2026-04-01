"""
migrate_add_tb_type.py
----------------------
One-time schema migration: adds tb_type column to tb_uploads table.

Cause:  Phase 2 fix (FIX-2.1) added tb_type to the TrialBalanceUpload
        SQLAlchemy model, but the live SQLite table does not have the column yet.

Safe:   ALTER TABLE ... ADD COLUMN with a NULL default — no data is modified,
        no rows are deleted, existing uploads continue to work unchanged.
        tb_type = NULL means "unknown" (same as passing no tb_type on upload).

Usage:
    cd <project_root>          # directory that contains data/vcfo.db
    python scripts/migrate_add_tb_type.py

    # or with explicit DB path:
    python scripts/migrate_add_tb_type.py --db data/vcfo.db
"""
import argparse
import sqlite3
import sys
from pathlib import Path


COLUMN_NAME = "tb_type"
TABLE_NAME  = "tb_uploads"
SQL_ALTER   = f"ALTER TABLE {TABLE_NAME} ADD COLUMN {COLUMN_NAME} VARCHAR(20)"


def column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def run_migration(db_path: str) -> None:
    path = Path(db_path)
    if not path.exists():
        print(f"ERROR: database file not found: {path.resolve()}")
        sys.exit(1)

    print(f"Database : {path.resolve()}")
    print(f"Table    : {TABLE_NAME}")
    print(f"Column   : {COLUMN_NAME}  VARCHAR(20)  NULL")
    print()

    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()

        # Check row count so we can verify nothing was lost
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        row_count_before = cur.fetchone()[0]
        print(f"Rows before migration : {row_count_before}")

        # Idempotent — skip if column already exists
        if column_exists(cur, TABLE_NAME, COLUMN_NAME):
            print(f"Column '{COLUMN_NAME}' already exists — nothing to do.")
            return

        # Apply the migration
        print(f"Applying  : {SQL_ALTER}")
        cur.execute(SQL_ALTER)
        conn.commit()
        print("Committed.")

        # Verify
        if not column_exists(cur, TABLE_NAME, COLUMN_NAME):
            print("ERROR: column not found after ALTER TABLE — check manually.")
            sys.exit(1)

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        row_count_after = cur.fetchone()[0]
        print(f"Rows after  migration : {row_count_after}")

        if row_count_before != row_count_after:
            print("WARNING: row count changed — inspect the database.")
        else:
            print()
            print("Migration successful.")
            print(f"  tb_type is NULL for all {row_count_after} existing rows.")
            print("  NULL == 'unknown' — system behaves identically to before.")
            print()
            print("Next step: restart the API server.")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add tb_type column to tb_uploads")
    parser.add_argument("--db", default="data/vcfo.db",
                        help="Path to SQLite database file (default: data/vcfo.db)")
    args = parser.parse_args()
    run_migration(args.db)
