"""
bootstrap_admin.py — First admin user + company membership setup.

Run from the project root (C:/VCFO/CFO/):
    python scripts/bootstrap_admin.py

What it does:
  1. Connects via DATABASE_URL (PostgreSQL only)
  2. Creates the admin user (skips if email already exists)
  3. Finds the first active company (or accepts company_id as argument)
  4. Creates membership with role = owner (skips if already exists)
  5. Prints a summary

Does NOT:
  - Create a new company
  - Touch financial data
  - Modify any existing records
"""

import sys
import uuid
from datetime import datetime
from pathlib import Path

# ── Allow running from project root without installing the package ─────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.company import Company
from app.models.membership import Membership
from app.models.user import User


def run(email: str, password: str, full_name: str, company_id: str | None = None):
    # Ensure all tables exist (safe — no-op if already there)
    from app.models import company, trial_balance, branch, user, membership  # noqa
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # ── 1. Find company ───────────────────────────────────────────────────
        if company_id:
            co = db.query(Company).filter(
                Company.id == company_id,
                Company.is_active == True,  # noqa
            ).first()
            if not co:
                print(f"[ERROR] Company '{company_id}' not found or inactive.")
                return
        else:
            co = db.query(Company).filter(Company.is_active == True).first()  # noqa
            if not co:
                print("[ERROR] No active company found in database. Create a company first.")
                return

        print(f"[INFO]  Company   : {co.name} ({co.id})")

        # ── 2. Create user (skip if exists) ───────────────────────────────────
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"[INFO]  User      : already exists — {email}")
            admin = existing_user
        else:
            admin = User(
                id=str(uuid.uuid4()),
                email=email,
                full_name=full_name,
                password_hash=hash_password(password),
                is_active=True,
                is_superuser=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(admin)
            db.flush()
            print(f"[OK]    User      : created — {email} (id: {admin.id})")

        # ── 3. Create membership (skip if exists) ─────────────────────────────
        existing_mem = db.query(Membership).filter(
            Membership.user_id == admin.id,
            Membership.company_id == co.id,
        ).first()
        if existing_mem:
            print(f"[INFO]  Membership: already exists — role={existing_mem.role}")
        else:
            mem = Membership(
                id=str(uuid.uuid4()),
                user_id=admin.id,
                company_id=co.id,
                role="owner",
                is_active=True,
                created_at=datetime.utcnow(),
            )
            db.add(mem)
            print(f"[OK]    Membership: created — role=owner")

        db.commit()

        print()
        print("=" * 50)
        print("  Bootstrap complete. You can now log in:")
        print(f"  Email    : {email}")
        print(f"  Password : {password}")
        print(f"  Company  : {co.name}")
        print("=" * 50)

    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bootstrap first admin user for VCFO")
    parser.add_argument("--email",      default="admin@vcfo.com",  help="Admin email")
    parser.add_argument("--password",   default="Admin1234",        help="Admin password")
    parser.add_argument("--name",       default="Admin",            help="Full name")
    parser.add_argument("--company-id", default=None,               help="Company ID (optional — uses first company if omitted)")
    args = parser.parse_args()

    run(
        email=args.email,
        password=args.password,
        full_name=args.name,
        company_id=args.company_id,
    )
