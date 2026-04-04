"""Tests for structured income statement period-over-period variance."""

from app.services.structured_income_statement_variance import (
    build_structured_income_statement_variance_bundle_from_window,
)
from tests.test_structured_income_statement import _minimal_is


def _stmt(period: str, revenue: float, cogs: float, gp: float, exp: float, uncl: float, tax: float, np_: float):
    """Build a period dict with nested IS + attach structured slice via same shape as _minimal_is."""
    op = round(gp - exp - uncl, 2)
    rev_f = revenue if revenue else None
    from app.services.metric_definitions import cogs_ratio_pct, opex_ratio_pct, total_cost_ratio_pct

    ox_r = opex_ratio_pct(exp, rev_f)
    cg_r = cogs_ratio_pct(cogs, rev_f)
    tc_r = total_cost_ratio_pct(cogs, exp, rev_f, 0.0)
    gm_pct = round(gp / revenue * 100, 2) if revenue else 0.0
    om_pct = round(op / revenue * 100, 2) if revenue else 0.0
    nm_pct = round(np_ / revenue * 100, 2) if revenue else 0.0
    row = {
        "period": period,
        "income_statement": {
            "revenue": {"total": revenue, "items": []},
            "cogs": {"total": cogs, "items": []},
            "gross_profit": gp,
            "gross_margin_pct": gm_pct,
            "expenses": {"total": exp, "items": []},
            "unclassified_pnl_debits": {"items": [], "total": uncl},
            "operating_profit": op,
            "operating_margin_pct": om_pct,
            "tax": {"total": tax, "items": []},
            "net_profit": np_,
            "net_margin_pct": nm_pct,
            "opex_ratio_pct": ox_r,
            "cogs_ratio_pct": cg_r,
            "total_cost_ratio_pct": tc_r,
            "expense_ratio_pct": tc_r,
        },
        "balance_sheet": {},
    }
    from app.services.structured_income_statement import attach_structured_income_statement

    attach_structured_income_statement(row)
    return row


def test_two_periods_revenue_delta_and_pct():
    a = _stmt("2026-01", 1000, 400, 600, 200, 50, 50, 300)
    b = _stmt("2026-02", 1100, 400, 700, 200, 50, 50, 400)
    out = build_structured_income_statement_variance_bundle_from_window([a, b])
    v = out["structured_income_statement_variance"]["revenue"]
    assert v["current"] == 1100.0
    assert v["previous"] == 1000.0
    assert v["delta"] == 100.0
    assert v["delta_pct"] == 10.0


def test_previous_zero_delta_pct_null():
    a = _stmt("2026-01", 0, 0, 0, 0, 0, 0, 0)
    b = _stmt("2026-02", 100, 50, 50, 10, 0, 0, 40)
    out = build_structured_income_statement_variance_bundle_from_window([a, b])
    rev = out["structured_income_statement_variance"]["revenue"]
    assert rev["previous"] == 0.0
    assert rev["delta"] == 100.0
    assert rev["delta_pct"] is None


def test_margin_delta_pp():
    a = _minimal_is()
    a["period"] = "2026-01"
    b = _minimal_is()
    b["period"] = "2026-02"
    b["income_statement"]["revenue"]["total"] = 2000.0
    b["income_statement"]["cogs"]["total"] = 800.0
    b["income_statement"]["gross_profit"] = 1200.0
    b["income_statement"]["gross_margin_pct"] = 60.0
    from app.services.structured_income_statement import attach_structured_income_statement

    attach_structured_income_statement(a)
    attach_structured_income_statement(b)
    out = build_structured_income_statement_variance_bundle_from_window([a, b])
    gm = out["structured_income_statement_margin_variance"]["gross_margin_pct"]
    assert gm["current"] == 60.0
    assert gm["previous"] == 60.0
    assert gm["delta_pp"] == 0.0


def test_single_period_completeness_none():
    one = _minimal_is()
    from app.services.structured_income_statement import attach_structured_income_statement

    attach_structured_income_statement(one)
    out = build_structured_income_statement_variance_bundle_from_window([one])
    assert out["structured_income_statement_variance_meta"]["completeness"] == "none"
    assert out["structured_income_statement_variance_meta"]["previous_period"] is None


def test_run_analysis_includes_variance_keys():
    from app.services.analysis_engine import run_analysis

    a = _minimal_is()
    a["period"] = "p1"
    b = _minimal_is()
    b["period"] = "p2"
    from app.services.structured_income_statement import attach_structured_income_statement

    attach_structured_income_statement(a)
    attach_structured_income_statement(b)
    r = run_analysis([a, b])
    assert "structured_income_statement_variance" in r
    assert r["structured_income_statement_variance_meta"]["completeness"] == "full"
