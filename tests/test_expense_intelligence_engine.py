"""Tests for expense_intelligence_engine (Phase 1)."""
import pytest

from app.services.expense_intelligence_engine import (
    build_expense_intelligence_bundle,
    build_expense_intelligence_executive_view,
)


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
    assert any(a.get("signal") in ("category_spike_vs_median", "expense_ratio_above_threshold", "total_expense_outpaced_revenue")
               for a in out["expense_anomalies"])


def test_executive_view_empty_bundle():
    view = build_expense_intelligence_executive_view(
        {"expense_analysis": {"meta": {"error": "no_statements"}, "by_period": []}}
    )
    assert view["available"] is False


def test_executive_view_maps_latest_and_top_category():
    bundle = build_expense_intelligence_bundle(
        [
            _stmt("2025-01", 100_000, 40_000, 25_000, payroll_amt=10_000),
            _stmt("2025-02", 100_000, 40_000, 30_000, payroll_amt=12_000),
        ],
        lang="en",
    )
    view = build_expense_intelligence_executive_view(bundle)
    assert view["available"] is True
    assert view["period"] == "2025-02"
    assert view["top_category"] is not None
    # Share is vs latest total_expense (COGS + OpEx here ≈ 70k; payroll 12k → ~17%)
    assert view["top_category"].get("share_of_cost_pct") == pytest.approx(17.14, rel=0.02)
    assert view["top_category"].get("amount_mom_pct") == pytest.approx(20.0, rel=0.02)
    assert view["expense_ratio"] is not None
    assert isinstance(view["anomalies"], list)
    assert isinstance(view["decisions"], list)


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


def test_invalid_lang_defaults_to_en_meta():
    out = build_expense_intelligence_bundle([_stmt("2025-01", 50_000, 10_000, 5_000)], lang="de")
    assert out["expense_analysis"]["meta"]["lang"] == "en"


def test_explanation_populated_for_multi_period():
    stmts = [
        _stmt("2025-01", 100_000, 40_000, 25_000, payroll_amt=10_000),
        _stmt("2025-02", 100_000, 40_000, 25_000, payroll_amt=10_000),
    ]
    out = build_expense_intelligence_bundle(stmts, lang="en")
    exp = out["expense_explanation"]
    assert "2025-02" in exp["headline"]
    assert "Total expense" in exp["narrative"]
    assert exp["comparison_basis"] != "none"


def test_category_totals_reconcile_to_total_expense():
    stmt = _stmt("2025-05", 120_000, 50_000, 35_000, payroll_amt=20_000)
    out = build_expense_intelligence_bundle([stmt], lang="en")
    row = out["expense_analysis"]["by_period"][0]
    cat_sum = sum(row["categories"].values())
    assert cat_sum == pytest.approx(row["total_expense"], rel=0, abs=1.0)


def test_weak_data_single_period_no_mom_in_trends():
    out = build_expense_intelligence_bundle([_stmt("2026-01", 10_000, 1_000, 2_000)], lang="en")
    assert out["expense_analysis"]["trends"]["mom"] is None
    assert out["expense_decisions"] == []


def test_total_expense_outpaced_revenue_yields_decision():
    stmts = [
        _stmt("2025-01", 100_000, 40_000, 20_000),
        _stmt("2025-02", 100_000, 40_000, 35_000),
    ]
    out = build_expense_intelligence_bundle(stmts, lang="en")
    signals = {a["signal"] for a in out["expense_anomalies"]}
    if "total_expense_outpaced_revenue" in signals:
        titles = [d["title"] for d in out["expense_decisions"]]
        assert any("total expense" in t.lower() for t in titles)
        assert all("linked_anomaly_ids" in d for d in out["expense_decisions"])
