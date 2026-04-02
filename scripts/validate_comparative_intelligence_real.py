from __future__ import annotations

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()

    # Ensure `import app` works when running as a script
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

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with SessionLocal() as db:
        # Find a company that has at least 1 active branch with ok uploads
        companies = db.query(Company).filter(Company.is_active == True).all()  # noqa: E712
        chosen = None
        chosen_branch_count = 0
        for c in companies:
            branches = (
                db.query(Branch)
                .filter(Branch.company_id == c.id, Branch.is_active == True)  # noqa: E712
                .all()
            )
            if not branches:
                continue
            ok_branches = 0
            for b in branches:
                ok = (
                    db.query(TrialBalanceUpload)
                    .filter(TrialBalanceUpload.branch_id == b.id, TrialBalanceUpload.status == "ok")
                    .count()
                )
                if ok:
                    ok_branches += 1
            if ok_branches >= 1:
                chosen = c
                chosen_branch_count = ok_branches
                break

        if not chosen:
            print("BLOCKER: no active company with branch uploads(status=ok) found")
            return 2

        company_id = chosen.id
        print(f"Using company: {chosen.name} ({company_id}) branches_with_uploads={chosen_branch_count}")

        # Branch bundles
        branches = (
            db.query(Branch)
            .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa: E712
            .order_by(Branch.name.asc())
            .all()
        )

        branch_bundles = []
        periods_union: set[str] = set()
        for b in branches:
            b_uploads = (
                db.query(TrialBalanceUpload)
                .filter(TrialBalanceUpload.branch_id == b.id, TrialBalanceUpload.status == "ok")
                .order_by(TrialBalanceUpload.uploaded_at.asc())
                .all()
            )
            if not b_uploads:
                continue
            b_stmts = _build_period_statements(company_id, b_uploads)
            if not b_stmts:
                continue
            periods_union.update([s.get("period") for s in b_stmts if s.get("period")])
            b_bundle = build_expense_intelligence_bundle(b_stmts, lang="en")
            branch_bundles.append({"branch_id": b.id, "branch_name": b.name, "expense_bundle": b_bundle})

        if not branch_bundles:
            print("BLOCKER: no branch bundles could be built (no statements)")
            return 2

        # Company denominator for branch comparisons: prefer consolidated-from-branches
        cons = _build_consolidated_statements(company_id, db) or []
        if periods_union:
            cons = [s for s in cons if s.get("period") in periods_union]
        if not cons:
            print("WARNING: could not build consolidated company statements; falling back to MAIN uploads for denominator.")
            company_uploads = (
                db.query(TrialBalanceUpload)
                .filter(
                    TrialBalanceUpload.company_id == company_id,
                    TrialBalanceUpload.status == "ok",
                    TrialBalanceUpload.branch_id.is_(None),
                )
                .order_by(TrialBalanceUpload.uploaded_at.asc())
                .all()
            )
            company_stmts = _build_period_statements(company_id, company_uploads) if company_uploads else []
        else:
            company_stmts = cons

        company_bundle = build_expense_intelligence_bundle(company_stmts, lang="en") if company_stmts else {}

        ci = build_comparative_intelligence(company_expense_bundle=company_bundle, branch_bundles=branch_bundles)

        # Print minimal real snippets for manual verification
        print("\n--- branch_rankings ---")
        print(ci.get("branch_rankings"))

        print("\n--- branch_vs_company (first 3 contributions) ---")
        contribs = (ci.get("branch_vs_company") or {}).get("branch_contributions") or []
        print(contribs[:3])

        print("\n--- cost_pressure ---")
        cp = ci.get("cost_pressure") or {}
        print(
            {
                "driving_expense_increase_mom": cp.get("driving_expense_increase_mom"),
                "driving_expense_increase_yoy": cp.get("driving_expense_increase_yoy"),
                "most_inefficient_branch": cp.get("most_inefficient_branch"),
                "most_improving_branch": cp.get("most_improving_branch"),
            }
        )

        print("\n--- efficiency_ranking (top 5 inefficient) ---")
        eff = ci.get("efficiency_ranking") or {}
        print(((eff.get("by_expense_pct_of_revenue_desc") or [])[:5]))

        print("\n--- category_comparison (top_category_per_branch first 5) ---")
        cat = ci.get("category_comparison") or {}
        print(((cat.get("top_category_per_branch") or [])[:5]))
        print("most_abnormal_category_distribution:", cat.get("most_abnormal_category_distribution"))

        # Weak/empty block detection
        weak = []
        if not ci.get("branch_rankings"):
            weak.append("branch_rankings empty")
        if not (ci.get("branch_vs_company") or {}).get("branch_contributions"):
            weak.append("branch_vs_company.branch_contributions empty")
        if not (ci.get("cost_pressure") or {}).get("all_branches"):
            weak.append("cost_pressure.all_branches empty")
        if not (ci.get("efficiency_ranking") or {}).get("by_expense_pct_of_revenue_desc"):
            weak.append("efficiency_ranking empty")
        if not (ci.get("category_comparison") or {}).get("top_category_per_branch"):
            weak.append("category_comparison.top_category_per_branch empty")

        if weak:
            print("\nWEAK/EMPTY BLOCKS:", weak)
            return 3

        print("\nVALIDATION: PASS (comparative_intelligence populated and coherent)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

