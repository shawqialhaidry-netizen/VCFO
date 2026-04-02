"""Read-only counts for 2025 uploads and memberships (PowerShell-friendly)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.core.database import SessionLocal


def main() -> int:
    db = SessionLocal()
    try:
        tb_total = db.execute(text("select count(1) from tb_uploads")).scalar() or 0
        c2025 = (
            db.execute(
                text(
                    "select count(1) from tb_uploads where period like '2025-%' and branch_id is null"
                )
            ).scalar()
            or 0
        )
        b2025 = (
            db.execute(
                text(
                    "select count(1) from tb_uploads where period like '2025-%' and branch_id is not null"
                )
            ).scalar()
            or 0
        )
        mem = (
            db.execute(text("select count(1) from memberships where is_active = true")).scalar()
            or 0
        )
        print("tb_uploads_total", tb_total)
        print("tb_uploads_2025_company", c2025)
        print("tb_uploads_2025_branch", b2025)
        print("memberships_active", mem)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

