from __future__ import annotations

import json
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

    from app.models.branch import Branch
    from app.models.company import Company
    from app.models.trial_balance import TrialBalanceUpload

    from app.api.analysis import _build_consolidated_statements, _build_period_statements
    from app.services.comparative_intelligence import build_comparative_intelligence
    from app.services.expense_decisions_upgrade import build_company_expense_decisions_v2
    from app.services.expense_intelligence_engine import build_expense_intelligence_bundle
    from app.services.financial_brain import build_financial_brain_company

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("BLOCKER: DATABASE_URL not set")
        return 2

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with SessionLocal() as db:
        companies = db.query(Company).filter(Company.is_active == True).all()  # noqa: E712
        chosen = None
        for c in companies:
            if (
                db.query(TrialBalanceUpload)
                .filter(TrialBalanceUpload.company_id == c.id, TrialBalanceUpload.status == "ok")
                .count()
                > 0
            ):
                chosen = c
                break
        if not chosen:
            print("BLOCKER: no active company with ok uploads")
            return 2

        company_id = chosen.id
        print(f"Using company: {chosen.name} ({company_id})")

        cons = _build_consolidated_statements(company_id, db) or []
        if not cons:
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
            branch_bundles.append(
                {
                    "branch_id": b.id,
                    "branch_name": b.name,
                    "expense_bundle": build_expense_intelligence_bundle(stmts, lang="en"),
                }
            )

        comparative = (
            build_comparative_intelligence(
                company_expense_bundle=company_bundle,
                branch_bundles=branch_bundles,
            )
            if company_bundle and branch_bundles
            else {}
        )

        expense_decisions_v2 = build_company_expense_decisions_v2(
            company_id=company_id,
            company_name=chosen.name,
            currency=(chosen.currency or ""),
            company_bundle=company_bundle,
            comparative_intelligence=comparative,
            lang="en",
        )

        fb = build_financial_brain_company(
            company_id=company_id,
            company_name=chosen.name,
            currency=(chosen.currency or ""),
            expense_bundle=company_bundle,
            comparative_intelligence=comparative,
            expense_decisions_v2=expense_decisions_v2,
            anomalies=company_bundle.get("expense_anomalies") or [],
            lang="en",
        )

        print("\n=== financial_brain (subset) ===")
        snippet = {
            "available": fb.get("available"),
            "what_changed": fb.get("what_changed"),
            "why": fb.get("why"),
            "root_causes": fb.get("root_causes"),
            "linked_drivers": fb.get("linked_drivers"),
            "causal_chain": fb.get("causal_chain"),
        }
        print(json.dumps(snippet, indent=2, default=str))

        weak = []
        if not fb.get("available"):
            weak.append("not available")
        if not fb.get("causal_chain"):
            weak.append("empty causal_chain")
        wc = fb.get("what_changed") or {}
        if not wc.get("latest") or wc.get("period") is None:
            weak.append("what_changed missing latest/period")
        why = (fb.get("why") or {}).get("links") or {}
        if not any([why.get("category_driver_mom"), why.get("branch_driver"), why.get("expense_vs_revenue")]):
            weak.append("why.links sparse")
        ld = fb.get("linked_drivers") or {}
        if not ld.get("decision_ids") and expense_decisions_v2:
            weak.append("decision_ids empty despite expense_decisions_v2")
        cc = fb.get("causal_chain") or []
        if cc and all(len(str(s)) < 40 for s in cc):
            weak.append("causal_chain very short (may feel thin)")

        if weak:
            print("\nWEAK / NOTES:", weak)
        else:
            print("\nVALIDATION: PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
