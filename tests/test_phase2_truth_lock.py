"""
Phase 2 — canonical TB→statements path, KPI/bundle alignment, integrity assessment (no DB).
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import pytest

from app.api.analysis import _assess_financial_integrity
from app.services.account_classifier import classify_dataframe
from app.services.analysis_engine import run_analysis
from app.services.canonical_period_statements import build_period_statements_from_uploads
from app.services.cashflow_engine import build_cashflow
from app.services.statement_engine import build_statement_bundle
from app.services.time_intelligence import build_kpi_block


def _minimal_classified_csv(path: Path) -> None:
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
    classify_dataframe(df).to_csv(path, index=False, encoding="utf-8-sig")


def test_canonical_statements_match_analysis_np(tmp_path):
    company_id = uuid.uuid4().hex
    norm = tmp_path / "one.csv"
    _minimal_classified_csv(norm)

    class _Rec:
        normalized_path = str(norm)
        period = "2099-06"
        tb_type = "post_closing"

    stmts = build_period_statements_from_uploads(company_id, [_Rec()])
    assert len(stmts) == 1
    analysis = run_analysis(stmts)
    stmt_np = float(stmts[-1]["income_statement"]["net_profit"])
    ana_np = float((analysis.get("latest") or {}).get("profitability", {}).get("net_profit", 0) or 0)
    assert abs(stmt_np - ana_np) <= 0.05


def test_kpi_block_matches_statement_bundle_flow_totals(tmp_path):
    company_id = uuid.uuid4().hex
    norm = tmp_path / "one.csv"
    _minimal_classified_csv(norm)

    class _Rec:
        normalized_path = str(norm)
        period = "2099-06"
        tb_type = "post_closing"

    stmts = build_period_statements_from_uploads(company_id, [_Rec()])
    kpi = build_kpi_block(stmts, "ALL")
    cf = build_cashflow(stmts)
    bundle = build_statement_bundle(stmts, cf, {"ratios": {}})
    assert kpi["kpis"]["revenue"]["value"] == bundle["summary"]["revenue"]
    assert kpi["kpis"]["net_profit"]["value"] == bundle["summary"]["net_profit"]
    assert bundle["summary"]["operating_cashflow"] == pytest.approx(cf.get("operating_cashflow"))


def test_assess_financial_integrity_blocking():
    blocked = _assess_financial_integrity(
        {"consistent": False, "has_errors": True, "error_codes": ["net_profit_mismatch"], "info_codes": []}
    )
    assert blocked["blocking"] is True
    assert blocked["suppress_governance_outputs"] is True

    ok = _assess_financial_integrity(
        {"consistent": True, "has_errors": False, "error_codes": [], "info_codes": ["tb_type_unknown"]}
    )
    assert ok["blocking"] is False
    assert ok["status"] in ("ok", "warning")
