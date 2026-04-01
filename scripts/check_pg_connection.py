#!/usr/bin/env python3
"""
scripts/check_pg_connection.py
-------------------------------
Quick test to verify PostgreSQL connection works.

Usage:
    python scripts/check_pg_connection.py
    python scripts/check_pg_connection.py --url postgresql://user:pass@host/db
"""
import argparse, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_env():
    env = ROOT / ".env"
    if not env.exists():
        print(f"WARNING: .env not found at {env}")
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v


def check(url: str) -> None:
    print(f"\nTesting PostgreSQL connection...")

    # Hide password in display
    display = url
    if "@" in url:
        creds = url.split("//")[-1].split("@")[0]
        if ":" in creds:
            user = creds.split(":")[0]
            display = url.replace(creds, f"{user}:****")
    print(f"  URL: {display}")

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    try:
        conn = psycopg2.connect(url, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT version()")
        ver = cur.fetchone()[0][:60]
        conn.close()
        print(f"  OK: Connected!")
        print(f"  PG: {ver}")
        print()
        print("Connection works. You can now run:")
        print("  python scripts/migrate_sqlite_to_pg.py --dry-run")
        print("  python scripts/migrate_sqlite_to_pg.py")

    except Exception as e:
        err = str(e)
        print(f"  FAILED: {e}")
        print()
        if "password authentication failed" in err:
            print("FIX: Wrong password in DATABASE_URL.")
            print()
            print("To reset the PostgreSQL password:")
            print('  1. Open psql as admin:')
            print('       psql -U postgres')
            print("  2. Run SQL:")
            print("       ALTER USER vcfo_user WITH PASSWORD 'your_new_password';")
            print()
            print("  3. Update .env:")
            print("       DATABASE_URL=postgresql://vcfo_user:your_new_password@localhost:5432/vcfo_db")
            print()
            print("  4. Re-run: python scripts/check_pg_connection.py")

        elif "role" in err and "does not exist" in err:
            print("FIX: User does not exist. Create it:")
            print('  psql -U postgres')
            print("  CREATE USER vcfo_user WITH ENCRYPTED PASSWORD 'your_password';")
            print("  GRANT ALL PRIVILEGES ON DATABASE vcfo_db TO vcfo_user;")

        elif "database" in err and "does not exist" in err:
            print("FIX: Database does not exist. Create it:")
            print('  psql -U postgres')
            print("  CREATE DATABASE vcfo_db;")
            print("  GRANT ALL PRIVILEGES ON DATABASE vcfo_db TO vcfo_user;")

        elif "Connection refused" in err or "could not connect" in err:
            print("FIX: PostgreSQL is not running or wrong host/port.")
            print("  Check that PostgreSQL service is started.")
            print("  Default: host=localhost, port=5432")
        sys.exit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="", help="PostgreSQL URL (default: reads from .env)")
    a = ap.parse_args()

    if a.url:
        os.environ["DATABASE_URL"] = a.url
    else:
        _load_env()

    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        print(f"ERROR: DATABASE_URL is not PostgreSQL: {url[:60]}")
        print("Set DATABASE_URL=postgresql://... in .env")
        sys.exit(1)

    check(url)
