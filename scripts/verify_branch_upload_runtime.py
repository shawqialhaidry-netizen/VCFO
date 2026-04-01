"""
Runtime verification: branch TB upload -> TrialBalanceUpload + BranchFinancial -> read APIs.

Uses in-memory SQLite + TestClient (same pattern as tests/conftest.py).
Run: python scripts/verify_branch_upload_runtime.py
"""
from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.branch import BranchFinancial

# Stable JWT for this script only
settings.JWT_SECRET_KEY = "verify-branch-upload-runtime-secret-key-32b!"
settings.ENFORCE_MEMBERSHIP = True  # production-like; we send real Bearer tokens

# StaticPool: in-memory SQLite must share one connection across TestClient threads
TEST_DATABASE_URL = "sqlite:///:memory:"
engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def main() -> None:
    # Register all ORM tables on Base.metadata (must import every mapped module)
    from app.models import (  # noqa: F401
        branch,
        company,
        membership,
        trial_balance,
        user,
    )

    Base.metadata.create_all(bind=engine_test)
    app.dependency_overrides[get_db] = override_get_db

    email = f"verify_{uuid.uuid4().hex[:12]}@example.com"
    password = "TestPass123!"

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Runtime Verify"},
        )
        assert r.status_code == 201, r.text

        r = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = client.post(
            "/api/v1/companies",
            json={"name": "Verify Co Runtime", "currency": "USD"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        company_id = r.json()["id"]

        r = client.post(
            "/api/v1/branches",
            json={"company_id": company_id, "name": "Runtime Branch", "currency": "USD"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        branch_id = r.json()["id"]

        # Standard TB: debit/credit columns; P&amp;L accounts per account_rules
        csv_content = """account_code,account_name,debit,credit
4000,Sales Revenue,0,100000
5000,Cost of Sales,30000,0
6000,Operating Expense,40000,0
"""

        r = client.post(
            "/api/v1/uploads",
            headers=headers,
            files={"file": ("tb_branch_verify.csv", csv_content.encode("utf-8"), "text/csv")},
            data={
                "company_id": company_id,
                "upload_mode": "monthly",
                "period": "2026-01",
                "branch_id": branch_id,
            },
        )

        upload_status = r.status_code
        upload_json: dict = {}
        try:
            upload_json = r.json()
        except Exception:
            upload_json = {"raw": r.text[:500]}

        print("=== A) UPLOAD RESPONSE (subset) ===")
        print(json.dumps(
            {
                "http_status": upload_status,
                "branch_id": upload_json.get("branch_id"),
                "status_field": upload_json.get("status"),
                "branch_financial_periods_written": upload_json.get("branch_financial_periods_written"),
                "period": upload_json.get("period"),
                "upload_mode": upload_json.get("upload_mode"),
            },
            indent=2,
        ))

        bf_rows: list = []
        db = TestingSessionLocal()
        try:
            bf_rows = (
                db.query(BranchFinancial)
                .filter(
                    BranchFinancial.company_id == company_id,
                    BranchFinancial.branch_id == branch_id,
                )
                .order_by(BranchFinancial.period)
                .all()
            )
            print("\n=== B) BranchFinancial rows ===")
            print(f"count={len(bf_rows)}")
            for row in bf_rows:
                print(
                    f"  period={row.period!r} revenue={row.revenue} net_profit={row.net_profit} "
                    f"cogs={row.cogs} expenses={row.expenses}"
                )
        finally:
            db.close()

        # Read APIs (what the UI uses)
        print("\n=== C) API reads ===")
        r_list = client.get(
            f"/api/v1/branches?company_id={company_id}",
            headers=headers,
        )
        print(f"GET /branches?company_id=... -> {r_list.status_code}")

        r_an = client.get(f"/api/v1/branches/{branch_id}/analysis", headers=headers)
        print(f"GET /branches/{{id}}/analysis -> {r_an.status_code}")
        if r_an.status_code == 200:
            ja = r_an.json()
            print(f"  has_data={ja.get('has_data')} period_count={ja.get('period_count')}")
            if ja.get("latest"):
                print(f"  latest.revenue={ja['latest'].get('revenue')} latest.net_margin_pct={ja['latest'].get('net_margin_pct')}")

        r_cons = client.get(f"/api/v1/analysis/{company_id}/consolidated", headers=headers)
        print(f"GET /analysis/{{id}}/consolidated -> {r_cons.status_code}")
        if r_cons.status_code == 200:
            jc = r_cons.json()
            print(f"  data_source={jc.get('data_source')} period_count={jc.get('period_count')} periods={jc.get('periods')}")

        r_cmp = client.get(
            f"/api/v1/companies/{company_id}/branch-comparison",
            headers=headers,
        )
        print(f"GET /companies/{{id}}/branch-comparison -> {r_cmp.status_code}")
        if r_cmp.status_code == 200:
            jm = r_cmp.json()
            print(f"  has_data={jm.get('has_data')} branches_with_data={jm.get('branches_with_data')}")
            for b in (jm.get("ranking") or [])[:3]:
                print(f"  ranking row: {b.get('branch_name')} revenue={b.get('revenue')} net_margin={b.get('net_margin')}")

        # PASS/FAIL summary
        print("\n=== SUMMARY ===")
        ok_upload = upload_status == 200 and upload_json.get("status") == "ok"
        ok_periods = bool(upload_json.get("branch_financial_periods_written"))
        ok_bf = len(bf_rows) > 0
        ok_analysis = r_an.status_code == 200 and r_an.json().get("has_data") is True
        ok_cons = r_cons.status_code == 200 and (r_cons.json().get("period_count") or 0) > 0
        ok_cmp = r_cmp.status_code == 200 and r_cmp.json().get("branches_with_data", 0) > 0

        print(f"upload_ok={ok_upload} periods_in_response={ok_periods} branchfinancial_rows={ok_bf}")
        _pc = r_cons.json().get("period_count") if r_cons.status_code == 200 else None
        print(f"branch_analysis_has_data={ok_analysis} consolidated_period_count={_pc}")
        print(f"branch_comparison_with_data={ok_cmp}")

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine_test)


if __name__ == "__main__":
    main()
