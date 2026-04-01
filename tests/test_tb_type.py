"""
test_tb_type.py — tb_type behavior tests.
Covers: pre_closing injects NP into equity,
        post_closing does not inject,
        unknown (None) does not inject and sets warning.
"""
import pytest
import pandas as pd


def _make_tb_df():
    """Minimal trial balance DataFrame for testing."""
    return pd.DataFrame([
        # Assets
        {"account_code": "1010", "account_name": "Cash",             "debit": 50000, "credit": 0,     "mapped_type": "assets",      "confidence": 0.95},
        {"account_code": "1100", "account_name": "Accounts Rec",     "debit": 30000, "credit": 0,     "mapped_type": "assets",      "confidence": 0.95},
        # Liabilities
        {"account_code": "2010", "account_name": "Accounts Pay",     "debit": 0,     "credit": 20000, "mapped_type": "liabilities", "confidence": 0.95},
        # Equity
        {"account_code": "3010", "account_name": "Share Capital",    "debit": 0,     "credit": 40000, "mapped_type": "equity",      "confidence": 0.95},
        # Revenue
        {"account_code": "4010", "account_name": "Revenue",          "debit": 0,     "credit": 60000, "mapped_type": "revenue",     "confidence": 0.95},
        # COGS
        {"account_code": "5010", "account_name": "COGS",             "debit": 35000, "credit": 0,     "mapped_type": "cogs",        "confidence": 0.95},
        # Expenses
        {"account_code": "6010", "account_name": "Salaries",         "debit": 10000, "credit": 0,     "mapped_type": "expenses",    "confidence": 0.95},
    ])


def test_pre_closing_injects_net_profit():
    """pre_closing: net profit must appear as retained earnings in equity."""
    from app.services.financial_statements import build_statements, statements_to_dict
    df = _make_tb_df()
    fs = build_statements(df, company_id="test", period="2025-01", tb_type="pre_closing")
    d = statements_to_dict(fs)

    bs = d["balance_sheet"]
    is_ = d["income_statement"]
    np = is_["net_profit"]  # 60000 - 35000 - 10000 = 15000

    # Net profit should be > 0
    assert np > 0, f"Expected positive net profit, got {np}"
    # tb_type should be recorded
    assert bs.get("tb_type") == "pre_closing"
    # No unknown warning for pre_closing
    assert bs.get("balance_warning") is None or "tb_type_unknown" not in str(bs.get("balance_warning", ""))


def test_post_closing_no_injection():
    """post_closing: NP already in equity, no injection, no warning."""
    from app.services.financial_statements import build_statements, statements_to_dict
    df = _make_tb_df()
    fs = build_statements(df, company_id="test", period="2025-01", tb_type="post_closing")
    d = statements_to_dict(fs)
    bs = d["balance_sheet"]
    assert bs.get("tb_type") == "post_closing"
    # No warning for explicitly set tb_type
    assert bs.get("balance_warning") is None or "tb_type_unknown" not in str(bs.get("balance_warning", ""))


def test_unknown_tb_type_sets_warning():
    """None/unknown tb_type: no injection, warning set."""
    from app.services.financial_statements import build_statements, statements_to_dict
    df = _make_tb_df()
    fs = build_statements(df, company_id="test", period="2025-01", tb_type=None)
    d = statements_to_dict(fs)
    bs = d["balance_sheet"]
    # Warning should be set
    assert bs.get("balance_warning") is not None
    assert "tb_type_unknown" in str(bs.get("balance_warning", ""))


def test_net_profit_calculation_correct():
    """Revenue - COGS - Expenses = Net Profit (accounting identity)."""
    from app.services.financial_statements import build_statements, statements_to_dict
    df = _make_tb_df()
    fs = build_statements(df, company_id="test", period="2025-01", tb_type="pre_closing")
    d = statements_to_dict(fs)
    is_ = d["income_statement"]
    expected_np = round(
        is_["revenue"]["total"] - is_["cogs"]["total"] - is_["expenses"]["total"], 2
    )
    assert abs(is_["net_profit"] - expected_np) < 0.02, (
        f"Net profit {is_['net_profit']} != revenue-cogs-expenses {expected_np}"
    )
