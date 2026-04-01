#!/usr/bin/env python3
"""
scripts/migrate_sqlite_to_pg.py
--------------------------------
Legacy one-off: copies data from a SQLite file into PostgreSQL.

The application never opens SQLite at runtime; this script is for migration only.

Pre-requisites:
  1. alembic upgrade head  (run first)
  2. DATABASE_URL in .env points to PostgreSQL
  3. python scripts/check_pg_connection.py  (verify connection)

Usage:
    python scripts/migrate_sqlite_to_pg.py --dry-run
    python scripts/migrate_sqlite_to_pg.py
    python scripts/migrate_sqlite_to_pg.py --pg-url postgresql://user:pass@host/db
"""
import argparse, os, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Boolean columns per table (SQLite stores as 0/1, PG needs True/False) ─────
BOOL_COLS = {
    "users":        {"is_active", "is_superuser"},
    "companies":    {"is_active"},
    "memberships":  {"is_active"},
    "branches":     {"is_active"},
    "tb_uploads":   set(),
    "branch_financials": set(),
}


def _load_env():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v


def _pg_url():
    _load_env()
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        print("ERROR: DATABASE_URL must be a PostgreSQL URL.")
        print(f"  Got: {url[:80] or '(empty)'}")
        print("  Fix: set DATABASE_URL=postgresql://user:pass@host:5432/db in .env")
        sys.exit(1)
    return url


def _pg_cols(cur, table):
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name=%s",
        (table,)
    )
    return {r[0]: r[1] for r in cur.fetchall()}


def _cast_value(val, col_name, table, pg_col_types):
    """Cast SQLite value to correct Python type for PostgreSQL."""
    if val is None:
        return None

    # Boolean cast: SQLite stores 0/1 as integers
    if col_name in BOOL_COLS.get(table, set()):
        return bool(val)

    # Check PG column type for additional casts
    pg_type = pg_col_types.get(col_name, "")
    if "bool" in pg_type.lower() and isinstance(val, int):
        return bool(val)

    return val


def migrate(sqlite_path, dry_run):
    label = " (DRY RUN)" if dry_run else ""
    print(f"\nVCFO: SQLite -> PostgreSQL{label}")
    print("=" * 58)

    sq_path = Path(sqlite_path)
    if not sq_path.exists():
        print(f"ERROR: SQLite not found: {sq_path.resolve()}")
        sys.exit(1)

    sq = sqlite3.connect(str(sq_path))
    sq.row_factory = sqlite3.Row
    print(f"Source  : {sq_path.resolve()}")

    url = _pg_url()
    try:
        import psycopg2
    except ImportError:
        print("ERROR: pip install psycopg2-binary")
        sys.exit(1)

    try:
        pg = psycopg2.connect(url)
        pg.autocommit = False
        pgc = pg.cursor()
        display = url.replace(url.split("//")[-1].split("@")[0],
                              url.split("//")[-1].split("@")[0].split(":")[0] + ":****") \
                  if "@" in url else url
        host = url.split("@")[-1].split("/")[0] if "@" in url else "unknown"
        print(f"Target  : PostgreSQL @ {host}\n")
    except Exception as e:
        print(f"ERROR connecting: {e}")
        if "password authentication" in str(e):
            print("\n  Fix: update DATABASE_URL in .env with correct password")
            print("  Then run: python scripts/check_pg_connection.py")
        sys.exit(1)

    # Pre-flight count
    print("Current state in PostgreSQL:")
    for t in ("users","companies","memberships","tb_uploads","branches"):
        try:
            pgc.execute(f"SELECT COUNT(*) FROM {t}")
            n = pgc.fetchone()[0]
            print(f"  {t:25}: {n} rows")
        except Exception as ex:
            print(f"  {t:25}: ERROR - {ex}")
            pg.rollback()
    print()

    TABLES = [
        ("users",             "id"),
        ("companies",         "id"),
        ("memberships",       "id"),
        ("branches",          "id"),
        ("tb_uploads",        "id"),
        ("branch_financials", "id"),
    ]

    total = 0

    for table, pk in TABLES:
        # Table exists in SQLite?
        exists = sq.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            print(f"  SKIP   {table:25} not in SQLite")
            continue

        sqc = sq.execute(f"SELECT * FROM {table}")
        rows = sqc.fetchall()
        if not rows:
            print(f"  SKIP   {table:25} 0 rows")
            continue

        sq_cols = [d[0] for d in sqc.description]

        try:
            pg_col_types = _pg_cols(pgc, table)
        except Exception as e:
            print(f"  ERROR  {table:25} reading PG cols: {e}")
            pg.rollback()
            continue

        # Only columns present in BOTH
        shared  = [c for c in sq_cols if c in pg_col_types]
        skipped = [c for c in sq_cols if c not in pg_col_types]

        if skipped:
            print(f"  NOTE   {table:25} PG missing cols (skipped): {skipped}")
        if not shared:
            print(f"  SKIP   {table:25} no shared columns")
            continue

        col_str = ", ".join(shared)
        ph_str  = ", ".join(["%s"] * len(shared))
        sql = (
            f"INSERT INTO {table} ({col_str})"
            f" VALUES ({ph_str})"
            f" ON CONFLICT ({pk}) DO NOTHING"
        )

        if dry_run:
            print(f"  DRY    {table:25} {len(rows)} rows")
            print(f"         cols: {col_str[:70]}")
            continue

        inserted = dup = errors = 0
        for row in rows:
            # Cast values: booleans, etc.
            vals = [
                _cast_value(row[c], c, table, pg_col_types)
                for c in shared
            ]
            try:
                pgc.execute(sql, vals)
                if pgc.rowcount > 0:
                    inserted += 1
                else:
                    dup += 1
            except Exception as e:
                errors += 1
                pg.rollback()
                print(f"  WARN   {table} row {row[pk]}: {e}")
                # Reconnect after error
                pg = psycopg2.connect(url)
                pg.autocommit = False
                pgc = pg.cursor()

        pg.commit()
        total += inserted
        print(f"  OK     {table:25} inserted={inserted}  dup_skip={dup}  err={errors}")

    sq.close()
    if not dry_run:
        pg.close()

    print()
    print("=" * 58)
    if dry_run:
        print("DRY RUN complete - nothing written.")
    else:
        print(f"Done. {total} rows inserted into PostgreSQL.")
        print()
        print("Next steps:")
        print("  1. Restart uvicorn")
        print("  2. Open: http://localhost:8000/api/v1/health/full")
        print("  3. Login at: http://localhost:5173")
    print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Migrate VCFO data from SQLite to PostgreSQL"
    )
    ap.add_argument("--sqlite",  default="data/vcfo.db")
    ap.add_argument("--pg-url",  default="",
                    help="Override DATABASE_URL (reads from .env by default)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.pg_url:
        os.environ["DATABASE_URL"] = a.pg_url

    migrate(a.sqlite, a.dry_run)
