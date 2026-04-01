#!/usr/bin/env python3
"""
Runtime proof for resolve_financial_scope (Phase 2).

Uses the same DB URL resolution as pytest:
  TEST_DATABASE_URL, else optional repo-root .env.test, else DATABASE_URL.

Run after DB is up and schema exists (e.g. after pytest session create_all, or migrations):
  python scripts/prove_scope_resolver.py
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_env_test = _REPO / ".env.test"
try:
    from dotenv import load_dotenv

    if _env_test.is_file():
        load_dotenv(_env_test, override=False)
except ImportError:
    pass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.core.security import hash_password
from app.models.branch import Branch
from app.models.company import Company
from app.models.group import Group, GroupMembership
from app.models.membership import Membership
from app.models.user import User
from app.services.scope_resolver import resolve_financial_scope


def _uid() -> str:
    return str(uuid.uuid4())


def main() -> int:
    url = (os.environ.get("TEST_DATABASE_URL") or settings.DATABASE_URL).strip()
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=2,
        pool_recycle=300,
    )
    try:
        conn = engine.connect()
        conn.close()
    except Exception as e:
        print(
            "FATAL: cannot connect to PostgreSQL.\n"
            "  Set TEST_DATABASE_URL or add .env.test (see .env.example).\n"
            "  Disposable DB: docker compose -f docker-compose.test.yml up -d\n"
            f"  Underlying error: {e}",
            file=sys.stderr,
        )
        return 1

    import app.models.group  # noqa: F401
    from app.models import company, trial_balance, branch, user, membership  # noqa: F401

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()

    user = User(
        id=_uid(),
        email=f"prove-{_uid()}@scope.local",
        password_hash=hash_password("prove-pass"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)

    g = Group(id=_uid(), name="Prove Group", is_active=True)
    db.add(g)

    c = Company(
        id=_uid(),
        group_id=g.id,
        name="Prove Co",
        currency="USD",
        is_active=True,
    )
    db.add(c)
    db.add(
        GroupMembership(
            id=_uid(),
            user_id=user.id,
            group_id=g.id,
            role="owner",
            is_active=True,
        )
    )
    db.add(
        Membership(
            id=_uid(),
            user_id=user.id,
            company_id=c.id,
            role="owner",
            is_active=True,
        )
    )
    b = Branch(
        id=_uid(),
        company_id=c.id,
        name="Prove Branch",
        is_active=True,
    )
    db.add(b)
    db.commit()

    # --- company scope ---
    rs_c = resolve_financial_scope(db, user, "company", c.id)
    print("COMPANY scope:", rs_c)

    # --- branch scope ---
    rs_b = resolve_financial_scope(db, user, "branch", b.id)
    print("BRANCH scope:", rs_b)

    # --- group scope ---
    rs_g = resolve_financial_scope(db, user, "group", g.id)
    print("GROUP scope:", rs_g)

    Base.metadata.drop_all(bind=engine)
    db.close()
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
