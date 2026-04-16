"""
test_statements_consistency.py — Verify statements and analysis use same data.
Covers: IS net_profit = cashflow NP input, analysis ratios read from statements,
        tb_type passed consistently.
"""
import pytest
import pandas as pd


def _sample_stmts():
    """Return two period statement dicts for testing."""
    from app.services.financial_statements import build_statements, statements_to_dict
    df = pd.DataFrame([
        {"account_code": "1010", "account_name": "Cash",        "debit": 50000, "credit": 0,     "mapped_type": "assets",      "confidence": 0.95},
        {"account_code": "1100", "account_name": "Receivables", "debit": 30000, "credit": 0,     "mapped_type": "assets",      "confidence": 0.95},
        {"account_code": "1200", "account_name": "Inventory",   "debit": 20000, "credit": 0,     "mapped_type": "assets",      "confidence": 0.95},
        {"account_code": "2010", "account_name": "Payables",    "debit": 0,     "credit": 15000, "mapped_type": "liabilities", "confidence": 0.95},
        {"account_code": "3010", "account_name": "Capital",     "debit": 0,     "credit": 40000, "mapped_type": "equity",      "confidence": 0.95},
        {"account_code": "4010", "account_name": "Revenue",     "debit": 0,     "credit": 80000, "mapped_type": "revenue",     "confidence": 0.95},
        {"account_code": "5010", "account_name": "COGS",        "debit": 45000, "credit": 0,     "mapped_type": "cogs",        "confidence": 0.95},
        {"account_code": "6010", "account_name": "Salaries",    "debit": 15000, "credit": 0,     "mapped_type": "expenses",    "confidence": 0.95},
    ])
    stmts = []
    for period in ["2025-01", "2025-02"]:
        fs = build_statements(df.copy(), company_id="c1", period=period, tb_type="pre_closing")
        d = statements_to_dict(fs)
        d["period"] = period
        stmts.append(d)
    return stmts


def test_cashflow_reads_np_from_statements():
    """Cashflow OCF must use NP from statements, not recompute."""
    from app.services.cashflow_engine import build_cashflow
    stmts = _sample_stmts()
    cf = build_cashflow(stmts)
    stmt_np = stmts[-1]["income_statement"]["net_profit"]
    cf_np   = cf["debug"]["net_profit"]
    assert abs(stmt_np - cf_np) < 0.02, (
        f"Cashflow NP {cf_np} diverges from statement NP {stmt_np}"
    )


def test_analysis_working_capital_from_statements():
    """Analysis WC must equal BS working_capital from statements."""
    from app.services.analysis_engine import run_analysis
    stmts = _sample_stmts()
    analysis = run_analysis(stmts)
    stmt_wc = stmts[-1]["balance_sheet"]["working_capital"]
    ratio_wc = analysis["latest"]["liquidity"]["working_capital"]
    assert abs(stmt_wc - ratio_wc) < 0.02, (
        f"Analysis WC {ratio_wc} diverges from statement WC {stmt_wc}"
    )


def test_analysis_net_profit_not_recomputed():
    """analysis ratios.net_profit must equal IS net_profit exactly."""
    from app.services.analysis_engine import run_analysis
    stmts = _sample_stmts()
    analysis = run_analysis(stmts)
    stmt_np   = stmts[-1]["income_statement"]["net_profit"]
    ratio_np  = analysis["latest"]["profitability"]["net_profit"]
    assert abs(stmt_np - ratio_np) < 0.02, (
        f"Analysis NP {ratio_np} diverges from statement NP {stmt_np}"
    )


def test_unclassified_debit_net_reduces_profit_without_polluting_opex():
    from app.services.financial_statements import build_statements, statements_to_dict

    df = pd.DataFrame([
        {"account_code": "4010", "account_name": "Revenue", "debit": 0, "credit": 1000, "mapped_type": "revenue", "confidence": 0.95},
        {"account_code": "5010", "account_name": "COGS", "debit": 400, "credit": 0, "mapped_type": "cogs", "confidence": 0.95},
        {"account_code": "6010", "account_name": "Salaries", "debit": 100, "credit": 0, "mapped_type": "expenses", "confidence": 0.95},
        {"account_code": "9999", "account_name": "Mystery debit", "debit": 50, "credit": 0, "mapped_type": "other", "confidence": 0.0},
    ])

    d = statements_to_dict(build_statements(df, company_id="c1", period="2026-01", tb_type="pre_closing"))
    is_ = d["income_statement"]

    assert is_["expenses"]["total"] == 100.0
    assert is_["unclassified_pnl_debits"]["total"] == 50.0
    assert is_["unclassified_pnl_debits"]["excluded_from_profit"] is False
    assert is_["unclassified_pnl_debits"]["deducted_from_profit"] is True
    assert is_["operating_profit"] == 450.0
    assert is_["net_profit"] == 450.0
    assert "deducted_from_profit" in is_["income_statement_warning"]


def test_statements_endpoint_tb_type_passthrough(client, company_and_headers):
    """statements.py must not silently drop tb_type."""
    # This is a smoke test — without uploads we can't do a full end-to-end,
    # but we verify the function signature accepts tb_type correctly.
    from app.services.financial_statements import build_statements
    import inspect
    sig = inspect.signature(build_statements)
    assert "tb_type" in sig.parameters, "build_statements must accept tb_type parameter"
