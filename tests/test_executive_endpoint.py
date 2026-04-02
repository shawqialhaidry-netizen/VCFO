"""
Integration-style tests for GET /api/v1/analysis/{company_id}/executive.

Requires PostgreSQL (conftest). Covers no-data / access paths and ensures no 5xx
for common client mistakes.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import pytest

from app.api.uploads import UPLOADS_DIR
from app.models.trial_balance import TrialBalanceUpload
from app.services.account_classifier import classify_dataframe

FAKE_UUID = "00000000-0000-0000-0000-000000000000"

# Fixed future period so uploads rarely collide with real data; TB pipeline requires YYYY-MM.
_EXEC_HAPPY_PERIOD = "2099-11"


def _seed_minimal_classified_upload(db, company_id: str, period: str) -> None:
    """
    Insert one company-level TrialBalanceUpload with a normalized CSV that
    `_load_df` + `build_statements` accept (same shape as the real upload path).
    """
    uid = uuid.uuid4().hex[:10]
    upload_dir = Path(UPLOADS_DIR) / company_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    raw_path = upload_dir / f"exec_contract_{uid}_raw.csv"
    norm_path = upload_dir / f"exec_contract_{uid}_normalized.csv"

    df = pd.DataFrame(
        [
            {"account_code": "1010", "account_name": "Cash", "debit": 50000, "credit": 0},
            {"account_code": "1100", "account_name": "Receivables", "debit": 30000, "credit": 0},
            {"account_code": "1200", "account_name": "Inventory", "debit": 20000, "credit": 0},
            {"account_code": "2010", "account_name": "Payables", "debit": 0, "credit": 15000},
            {"account_code": "3010", "account_name": "Capital", "debit": 0, "credit": 40000},
            {"account_code": "4010", "account_name": "Revenue", "debit": 0, "credit": 80000},
            {"account_code": "5010", "account_name": "COGS", "debit": 45000, "credit": 0},
            {"account_code": "6010", "account_name": "Salaries", "debit": 15000, "credit": 0},
        ]
    )
    classified = classify_dataframe(df)
    classified.to_csv(norm_path, index=False, encoding="utf-8-sig")
    df.to_csv(raw_path, index=False, encoding="utf-8-sig")

    td = float(df["debit"].sum())
    tc = float(df["credit"].sum())
    rec = TrialBalanceUpload(
        company_id=company_id,
        original_filename=f"exec_contract_{uid}.csv",
        raw_path=str(raw_path.resolve()),
        normalized_path=str(norm_path.resolve()),
        period=period,
        format_detected="monthly/standard",
        record_count=int(len(classified)),
        total_debit=td,
        total_credit=tc,
        is_balanced="true",
        status="ok",
        tb_type="pre_closing",
        branch_id=None,
    )
    db.add(rec)
    db.commit()


def test_executive_no_financial_data_returns_422_not_500(client, company_and_headers):
    company, headers = company_and_headers
    r = client.get(f"/api/v1/analysis/{company['id']}/executive", headers=headers)
    assert r.status_code == 422
    assert r.status_code < 500


def test_executive_unknown_company_returns_404(client, auth_headers):
    r = client.get(f"/api/v1/analysis/{FAKE_UUID}/executive", headers=auth_headers)
    assert r.status_code == 404
    assert r.status_code < 500


def test_executive_422_detail_is_client_safe_string(client, company_and_headers):
    company, headers = company_and_headers
    r = client.get(f"/api/v1/analysis/{company['id']}/executive", headers=headers)
    assert r.status_code == 422
    body = r.json()
    detail = body.get("detail")
    assert detail is not None
    assert isinstance(detail, str)


@pytest.mark.parametrize(
    "params",
    [
        {"lang": "en"},
        {"lang": "ar"},
        {"window": "ALL"},
        {"window": "6M", "lang": "tr"},
    ],
)
def test_executive_query_variants_stay_non_server_error(client, company_and_headers, params):
    company, headers = company_and_headers
    r = client.get(f"/api/v1/analysis/{company['id']}/executive", headers=headers, params=params)
    assert r.status_code < 500
    assert r.status_code == 422


def test_executive_happy_path_200_contract(client, company_and_headers, db_session):
    """Minimal classified TB on disk + DB row → executive returns 200 with stable top-level shape."""
    company, headers = company_and_headers
    _seed_minimal_classified_upload(db_session, company["id"], _EXEC_HAPPY_PERIOD)

    r = client.get(
        f"/api/v1/analysis/{company['id']}/executive",
        headers=headers,
        params={"lang": "en", "window": "ALL"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "success"
    assert body.get("company_id") == company["id"]
    for key in ("data", "meta"):
        assert key in body

    data = body["data"]
    for key in (
        "intelligence",
        "kpi_block",
        "cashflow",
        "decisions",
        "statements",
        "alerts",
        "root_causes",
        "expense_intelligence",
    ):
        assert key in data

    ei = data["expense_intelligence"]
    assert isinstance(ei, dict)
    assert ei.get("available") is True
    assert ei.get("top_category") is not None
    assert ei.get("totals") is not None

    stmts = data["statements"]
    assert isinstance(stmts, dict)
    assert stmts.get("available") is True
    assert stmts.get("income_statement")
    assert stmts.get("balance_sheet")

    meta = body["meta"]
    assert isinstance(meta.get("periods"), list)
    assert _EXEC_HAPPY_PERIOD in meta["periods"]
