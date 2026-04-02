from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.company import Company
    from app.models.branch import Branch
    from app.models.trial_balance import TrialBalanceUpload

    from app.api.analysis import _build_period_statements, _build_consolidated_statements
    from app.services.expense_intelligence_engine import build_expense_intelligence_bundle
    from app.services.comparative_intelligence import build_comparative_intelligence
    from app.services.expense_decisions_upgrade import (
        build_company_expense_decisions_v2,
        build_branch_expense_decisions_v2,
    )

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("BLOCKER: DATABASE_URL not set")
        return 2

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with SessionLocal() as db:
        # Pick a company with at least 1 active branch
        companies = db.query(Company).filter(Company.is_active == True).all()  # noqa: E712
        chosen = None
        for c in companies:
            br = (
                db.query(Branch)
                .filter(Branch.company_id == c.id, Branch.is_active == True)  # noqa: E712
                .count()
            )
            if br:
                chosen = c
                break
        if not chosen:
            print("BLOCKER: no active company with branches found")
            return 2

        company_id = chosen.id
        print(f"Using company: {chosen.name} ({company_id})")

        # Company denominator: consolidated-from-branches (matches comparative)
        cons = _build_consolidated_statements(company_id, db) or []
        if not cons:
            print("WARNING: no consolidated statements; falling back to MAIN uploads for company bundle.")
            main_uploads = (
                db.query(TrialBalanceUpload)
                .filter(
                    TrialBalanceUpload.company_id == company_id,
                    TrialBalanceUpload.status == "ok",
                    TrialBalanceUpload.branch_id.is_(None),
                )
                .order_by(TrialBalanceUpload.uploaded_at.asc())
                .all()
            )
            cons = _build_period_statements(company_id, main_uploads) if main_uploads else []

        company_bundle = build_expense_intelligence_bundle(cons, lang="en") if cons else {}

        # Build branch bundles using branch uploads where available
        branches = (
            db.query(Branch)
            .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa: E712
            .order_by(Branch.name.asc())
            .all()
        )
        branch_bundles = []
        for b in branches:
            uploads = (
                db.query(TrialBalanceUpload)
                .filter(TrialBalanceUpload.branch_id == b.id, TrialBalanceUpload.status == "ok")
                .order_by(TrialBalanceUpload.uploaded_at.asc())
                .all()
            )
            if not uploads:
                continue
            stmts = _build_period_statements(company_id, uploads)
            if not stmts:
                continue
            bun = build_expense_intelligence_bundle(stmts, lang="en")
            branch_bundles.append({"branch_id": b.id, "branch_name": b.name, "expense_bundle": bun})

        comparative = build_comparative_intelligence(
            company_expense_bundle=company_bundle,
            branch_bundles=branch_bundles,
        ) if company_bundle and branch_bundles else {}

        print("\n--- company expense_decisions_v2 (top 2) ---")
        cd = build_company_expense_decisions_v2(
            company_id=company_id,
            company_name=chosen.name,
            currency=(chosen.currency or ""),
            company_bundle=company_bundle,
            comparative_intelligence=comparative,
            lang="en",
        )
        print(cd[:2])

        if branch_bundles:
            b0 = branch_bundles[0]
            print(f"\n--- branch expense_decisions_v2 ({b0['branch_name']}) (top 2) ---")
            bd = build_branch_expense_decisions_v2(
                branch_id=str(b0["branch_id"]),
                branch_name=str(b0["branch_name"]),
                company_id=company_id,
                company_name=chosen.name,
                currency=(chosen.currency or ""),
                branch_bundle=b0["expense_bundle"],
                comparative_intelligence=comparative,
                lang="en",
            )
            print(bd[:2])

        return 0


if __name__ == "__main__":
    raise SystemExit(main())

