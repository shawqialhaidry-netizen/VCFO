"""Tests for expense_intelligence_engine (Phase 1)."""
from app.services.expense_intelligence_engine import build_expense_intelligence_bundle


def _stmt(period: str, rev: float, cogs: float, opex: float, payroll_amt: float = 0.0):
    items_opex = []
    if payroll_amt > 0:
        items_opex.append(
            {
                "account_code": "6010",
                "account_name": "Salaries",
                "amount": payroll_amt,
                "mapped_type": "expenses",
            }
        )
    return {
        "period": period,
        "income_statement": {
            "revenue": {"items": [], "total": rev},
            "cogs": {"items": [], "total": cogs},
            "expenses": {"items": items_opex, "total": opex},
            "unclassified_pnl_debits": {"items": [], "total": 0},
            "gross_profit": rev - cogs,
            "net_profit": rev - cogs - opex,
            "net_margin_pct": None,
        },
    }


def test_bundle_keys_and_trends():
    stmts = [
        _stmt("2024-01", 100_000, 40_000, 25_000, payroll_amt=15_000),
        _stmt("2024-02", 105_000, 41_000, 26_000, payroll_amt=16_000),
        _stmt("2025-01", 110_000, 42_000, 45_000, payroll_amt=35_000),
    ]
    out = build_expense_intelligence_bundle(stmts, lang="en")
    assert set(out.keys()) == {
        "expense_analysis",
        "expense_anomalies",
        "expense_decisions",
        "expense_explanation",
    }
    ea = out["expense_analysis"]
    assert len(ea["by_period"]) == 3
    assert ea["trends"]["yoy"] is not None
    assert ea["trends"]["yoy"]["from_period"] == "2024-01"
    assert ea["trends"]["yoy"]["to_period"] == "2025-01"
    assert len(ea["by_year"]) == 2
    assert any(a.get("signal") == "unusual_increase_vs_baseline" for a in out["expense_anomalies"])


def test_empty_statements():
    out = build_expense_intelligence_bundle([], lang="en")
    assert out["expense_analysis"]["meta"].get("error") == "no_statements"
    assert out["expense_anomalies"] == []


def test_branch_section():
    company = [_stmt("2025-03", 200_000, 80_000, 50_000, payroll_amt=30_000)]
    branch = {
        "br1": [_stmt("2025-03", 50_000, 20_000, 15_000, payroll_amt=10_000)],
    }
    out = build_expense_intelligence_bundle(
        company,
        branch_period_statements=branch,
        branch_labels={"br1": "Branch One"},
        lang="en",
    )
    bb = out["expense_analysis"]["by_branch"]
    assert len(bb) == 1
    assert bb[0]["branch_name"] == "Branch One"
    assert bb[0]["revenue"] == 50_000.0
