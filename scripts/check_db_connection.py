"""Load repo-root .env and verify PostgreSQL with psycopg2 (diagnostic only)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine.url import make_url

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env", override=False)

import psycopg2  # noqa: E402

db_url = (os.environ.get("DATABASE_URL") or "").strip()
if not db_url:
    print("DATABASE_URL not loaded from .env")
    sys.exit(1)

print("DATABASE_URL loaded")

try:
    u = make_url(db_url)
    conn = psycopg2.connect(
        host=u.host,
        port=u.port or 5432,
        user=u.username,
        password=u.password or "",
        dbname=u.database,
    )
    conn.close()
except Exception as e:
    print("PostgreSQL connection failed:", e)
    sys.exit(1)

print("CONNECTED OK")
