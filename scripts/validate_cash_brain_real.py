"""Build executive-equivalent payload from DB and run JS Cash Brain validation."""
from __future__ import annotations

import json
import os
import subprocess
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
    from app.models.trial_balance import TrialBalanceUpload
    from app.api.analysis import _build_period_statements
    from app.services.analysis_engine import run_analysis
    from app.services.cashflow_engine import build_cashflow
    from app.services.comparative_intelligence import build_comparative_intelligence
    from app.services.expense_decisions_upgrade import build_company_expense_decisions_v2
    from app.models.branch import Branch
    from app.api.analysis import _build_consolidated_statements
    from app.services.expense_intelligence_engine import build_expense_intelligence_bundle
    from app.services.fin_intelligence import build_intelligence
    from app.services.financial_brain import build_financial_brain_company
    from app.services.period_aggregation import build_annual_layer
    from app.services.statement_engine import build_statement_bundle as _build_statements
    from app.services.time_intelligence import build_kpi_block, filter_periods

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("BLOCKER: DATABASE_URL not set — cannot load real company data.")
        return 2

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with SessionLocal() as db:
        chosen = None
        for c in db.query(Company).filter(Company.is_active == True).all():  # noqa: E712
            n = (
                db.query(TrialBalanceUpload)
                .filter(TrialBalanceUpload.company_id == c.id, TrialBalanceUpload.status == "ok")
                .count()
            )
            if n > 0:
                chosen = c
                break
        if not chosen:
            print("BLOCKER: no active company with ok uploads")
            return 2

        company_id = chosen.id
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None),
            )
            .order_by(TrialBalanceUpload.uploaded_at.asc())
            .all()
        )
        if not uploads:
            cons = _build_consolidated_statements(company_id, db) or []
            windowed = filter_periods(cons, "ALL") if cons else []
            all_stmts = cons
        else:
            all_stmts = _build_period_statements(company_id, uploads)
            windowed = filter_periods(all_stmts, "ALL")

        if not windowed:
            print("BLOCKER: empty windowed statements")
            return 2

        analysis = run_analysis(windowed)
        annual = build_annual_layer(windowed)
        cashflow_raw = build_cashflow(windowed)
        intelligence = build_intelligence(
            analysis=analysis,
            annual_layer=annual,
            currency=chosen.currency or "",
        )
        kpi_block = build_kpi_block(all_stmts, "ALL")
        statement_bundle = _build_statements(windowed, cashflow_raw, intelligence, lang="en")

        branches = (
            db.query(Branch)
            .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa: E712
            .order_by(Branch.name.asc())
            .all()
        )
        branch_bundles = []
        for b in branches:
            b_uploads = (
                db.query(TrialBalanceUpload)
                .filter(TrialBalanceUpload.branch_id == b.id, TrialBalanceUpload.status == "ok")
                .order_by(TrialBalanceUpload.uploaded_at.asc())
                .all()
            )
            if not b_uploads:
                continue
            stmts = _build_period_statements(company_id, b_uploads)
            if not stmts:
                continue
            branch_bundles.append(
                {
                    "branch_id": b.id,
                    "branch_name": b.name,
                    "expense_bundle": build_expense_intelligence_bundle(stmts, lang="en"),
                }
            )

        company_bundle = build_expense_intelligence_bundle(windowed, lang="en")
        comparative = (
            build_comparative_intelligence(
                company_expense_bundle=company_bundle,
                branch_bundles=branch_bundles,
            )
            if branch_bundles
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
        financial_brain = build_financial_brain_company(
            company_id=company_id,
            company_name=chosen.name,
            currency=(chosen.currency or ""),
            expense_bundle=company_bundle,
            comparative_intelligence=comparative,
            expense_decisions_v2=expense_decisions_v2,
            anomalies=company_bundle.get("expense_anomalies") or [],
            lang="en",
        )

        payload = {
            "cashflow": cashflow_raw,
            "statements": statement_bundle,
            "intelligence": intelligence,
            "kpi_block": kpi_block,
            "financial_brain": financial_brain,
            "comparative_intelligence": comparative,
            "root_causes": [],
            "expense_decisions_v2": expense_decisions_v2,
        }

        out_path = root / "tmp_cash_brain_payload.json"
        out_path.write_text(json.dumps(payload, default=str), encoding="utf8")
        print(f"Wrote {out_path} for company {chosen.name!r} ({company_id})")
        print("Running node buildCashBrainSnapshot...")
        r = subprocess.run(
            ["node", str(root / "scripts" / "run_cash_brain_snapshot.mjs"), str(out_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        result_path = root / "tmp_cash_brain_result.json"
        result_path.write_text(r.stdout or "{}", encoding="utf-8")
        print(f"Wrote validation report: {result_path}")
        if r.stderr:
            print("STDERR:", r.stderr, file=sys.stderr)
        try:
            rep = json.loads(r.stdout or "{}")
            print("verdict:", rep.get("verdict"))
            print("dupes vs narrative:", len(rep.get("duplicateFactsVsNarrative") or []))
            print("weakCards:", rep.get("weakCards"))
        except json.JSONDecodeError:
            print("(could not parse node JSON stdout)")
        return r.returncode if r.returncode else 0


if __name__ == "__main__":
    raise SystemExit(main())
