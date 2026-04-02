"""
tests/test_statement_engine.py — Unit tests for statement_engine.build_statement_bundle
and small helpers (pure aggregation / insight rules, no DB).
"""
from __future__ import annotations

import pytest

from app.services import statement_engine as se


def _period(
    period: str,
    *,
    rev: float = 100_000.0,
    np_: float = 10_000.0,
    gm_pct: float = 40.0,
    nm_pct: float = 10.0,
    ca: float | None = 50_000.0,
    cl: float | None = 30_000.0,
    wc: float | None = 20_000.0,
    total_assets: float = 200_000.0,
    total_liab: float = 80_000.0,
    total_eq: float = 120_000.0,
    is_balanced: bool = True,
) -> dict:
    return {
        "period": period,
        "income_statement": {
            "revenue": {"total": rev, "items": []},
            "cogs": {"total": rev * 0.5, "items": []},
            "gross_profit": rev * 0.5,
            "gross_margin_pct": gm_pct,
            "expenses": {"total": 10_000.0, "items": []},
            "operating_profit": rev * 0.5 - 10_000.0,
            "tax": {"total": 0.0, "items": []},
            "net_profit": np_,
            "net_margin_pct": nm_pct,
        },
        "balance_sheet": {
            "assets": {"total": total_assets, "items": []},
            "liabilities": {"total": total_liab, "items": []},
            "equity": {"total": total_eq, "items": []},
            "working_capital": wc,
            "current_assets": ca,
            "current_liabilities": cl,
            "noncurrent_assets": total_assets - (ca or 0),
            "noncurrent_liabilities": total_liab - (cl or 0),
            "is_balanced": is_balanced,
        },
    }


def _cashflow(**overrides) -> dict:
    base = {
        "operating_cashflow": 15_000.0,
        "operating_cashflow_mom": 5.0,
        "quality": {"cash_conversion_quality": "strong"},
        "series": {"operating_cashflow": [1, 2, 3, 4, 5, 6, 7]},
        "working_capital_change": {},
        "flags": {},
    }
    base.update(overrides)
    return base


def _intelligence(**overrides) -> dict:
    base = {"ratios": {"profitability": {}, "liquidity": {}}}
    base.update(overrides)
    return base


def _period_accounting_consistent(
    period: str,
    *,
    revenue: float = 200_000.0,
    cogs: float = 120_000.0,
    operating_expenses: float = 45_000.0,
    tax: float = 5_000.0,
    total_liab: float = 90_000.0,
    total_eq: float = 160_000.0,
    ca: float = 70_000.0,
    cl: float = 40_000.0,
) -> dict:
    """
    Period dict with a coherent simplified P&L and BS equation A = L + E.
    gross_profit = revenue - cogs; operating_profit = gp - opex; net = op - tax.
    working_capital = current_assets - current_liabilities.
    """
    gross_profit = revenue - cogs
    operating_profit = gross_profit - operating_expenses
    net_profit = operating_profit - tax
    total_assets = total_liab + total_eq
    wc = ca - cl
    noncurrent_assets = total_assets - ca
    noncurrent_liabilities = total_liab - cl
    gm_pct = (gross_profit / revenue * 100) if revenue else 0.0
    nm_pct = (net_profit / revenue * 100) if revenue else 0.0
    return {
        "period": period,
        "income_statement": {
            "revenue": {"total": revenue, "items": []},
            "cogs": {"total": cogs, "items": []},
            "gross_profit": gross_profit,
            "gross_margin_pct": gm_pct,
            "expenses": {"total": operating_expenses, "items": []},
            "operating_profit": operating_profit,
            "tax": {"total": tax, "items": []},
            "net_profit": net_profit,
            "net_margin_pct": nm_pct,
        },
        "balance_sheet": {
            "assets": {"total": total_assets, "items": []},
            "liabilities": {"total": total_liab, "items": []},
            "equity": {"total": total_eq, "items": []},
            "working_capital": wc,
            "current_assets": ca,
            "current_liabilities": cl,
            "noncurrent_assets": noncurrent_assets,
            "noncurrent_liabilities": noncurrent_liabilities,
            "is_balanced": True,
        },
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def test_r2_rounds_and_none_on_bad_input():
    assert se._r2(3.14159) == 3.14
    assert se._r2("2.5") == 2.5
    assert se._r2(None) is None
    assert se._r2("x") is None


def test_get_nested_keys():
    d = {"a": {"b": {"c": 1}}}
    assert se._get(d, "a", "b", "c") == 1
    assert se._get(d, "a", "missing", "c", default=0) == 0


def test_fmt_currency():
    assert se._fmt_currency(None) == "—"
    assert se._fmt_currency(1_500_000) == "+1.5M"
    assert se._fmt_currency(-2500) == "-2K"
    assert se._fmt_currency(99) == "+99"


def test_build_series_truncates_to_six_tail():
    w = [_period(f"2024-{i:02d}", rev=1000.0 * i, np_=100.0 * i, gm_pct=30.0) for i in range(1, 9)]
    s = se._build_series(w)
    assert len(s["periods"]) == 6
    assert s["periods"][-1] == "2024-08"
    assert s["revenue"][-1] == 8000.0


def test_mom_change_requires_two_numeric_points():
    assert se._mom_change([100.0, 110.0]) == pytest.approx(10.0)
    assert se._mom_change([100.0]) is None
    assert se._mom_change([100.0, None]) is None


# ── build_statement_bundle ────────────────────────────────────────────────────


def test_empty_windowed_unavailable():
    out = se.build_statement_bundle([], _cashflow(), _intelligence())
    assert out == {"available": False, "reason": "No period data"}


def test_invalid_lang_defaults_to_en():
    w = [_period("2025-01")]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence(), lang="xx")
    assert out["available"] is True
    assert isinstance(out["insights"], list)


def test_bundle_shape_and_latest_period():
    w = [_period("2025-03", rev=50_000.0, np_=5_000.0)]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert out["available"] is True
    assert out["period"] == "2025-03"
    assert set(out) >= {
        "income_statement",
        "balance_sheet",
        "cashflow",
        "series",
        "summary",
        "insights",
    }
    assert out["income_statement"]["revenue"] == 50_000.0
    assert out["balance_sheet"]["working_capital"] == 20_000.0


def test_mom_revenue_and_np_with_two_months():
    w = [
        _period("2025-01", rev=100_000.0, np_=10_000.0),
        _period("2025-02", rev=120_000.0, np_=12_000.0),
    ]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert out["income_statement"]["mom_change_rev"] == pytest.approx(20.0)
    assert out["income_statement"]["mom_change_np"] == pytest.approx(20.0)


def test_yoy_revenue_change_with_thirteen_months():
    # windowed[-13] is index 0 when len == 13; latest is windowed[-1].
    w = [_period(f"2024-{i:02d}", rev=100_000.0, np_=10_000.0) for i in range(1, 13)]
    w.append(_period("2025-01", rev=130_000.0, np_=10_000.0))
    assert len(w) == 13
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert out["income_statement"]["yoy_change_rev"] == pytest.approx(30.0)


def test_current_ratio_from_balance_sheet_when_ca_cl_present():
    w = [_period("2025-01", ca=40_000.0, cl=20_000.0)]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert out["balance_sheet"]["ratios"]["current_ratio"] == 2.0


def test_current_ratio_fallback_from_intelligence():
    w = [
        _period(
            "2025-01",
            ca=None,
            cl=None,
            wc=0.0,
        )
    ]
    intel = _intelligence(
        ratios={
            "profitability": {},
            "liquidity": {"current_ratio": {"value": 1.55}},
        }
    )
    out = se.build_statement_bundle(w, _cashflow(), intel)
    assert out["balance_sheet"]["ratios"]["current_ratio"] == 1.55


def test_debt_ratio_pct():
    w = [_period("2025-01", total_assets=100_000.0, total_liab=25_000.0)]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert out["balance_sheet"]["ratios"]["debt_ratio_pct"] == 25.0


def test_cashflow_quality_dict_and_reliability_flag():
    w = [_period("2025-01")]
    for quality, expected in (
        ("strong", "good"),
        ("moderate", "warning"),
        ("weak", "risk"),
    ):
        cf = _cashflow(quality={"cash_conversion_quality": quality})
        out = se.build_statement_bundle(w, cf, _intelligence())
        assert out["cashflow"]["reliability"] == expected


def test_cashflow_quality_legacy_string():
    w = [_period("2025-01")]
    cf = _cashflow(quality="strong")
    out = se.build_statement_bundle(w, cf, _intelligence())
    assert out["cashflow"]["reliability"] == "good"


def test_cashflow_negative_ocf_maps_to_risk():
    w = [_period("2025-01")]
    cf = _cashflow(operating_cashflow=-1000.0, quality={"cash_conversion_quality": "unknown"})
    out = se.build_statement_bundle(w, cf, _intelligence())
    assert out["cashflow"]["reliability"] == "risk"


def test_summary_window_totals_two_periods():
    w = [
        _period("2025-01", rev=100_000.0, np_=10_000.0, nm_pct=10.0),
        _period("2025-02", rev=50_000.0, np_=5_000.0, nm_pct=10.0),
    ]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert out["summary"]["window_revenue_total"] == 150_000.0
    assert out["summary"]["window_net_profit_total"] == 15_000.0
    assert out["summary"]["latest_revenue"] == 50_000.0


def test_insight_low_net_margin():
    w = [_period("2025-01", nm_pct=4.0)]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    keys = {i["key"] for i in out["insights"]}
    assert "low_net_margin" in keys
    low = next(i for i in out["insights"] if i["key"] == "low_net_margin")
    assert low["severity"] == "high"
    assert low["linked_decision"] == "profitability"


def test_insight_negative_working_capital():
    w = [_period("2025-01", wc=-5000.0)]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert any(i["key"] == "negative_working_capital" for i in out["insights"])


def test_insight_cashflow_below_profit():
    w = [_period("2025-01", np_=10_000.0)]
    cf = _cashflow(operating_cashflow=5000.0)  # 5000 < 7000
    out = se.build_statement_bundle(w, cf, _intelligence())
    assert any(i["key"] == "cashflow_below_profit" for i in out["insights"])


def test_insight_low_current_ratio_from_bs():
    w = [_period("2025-01", ca=10_000.0, cl=10_000.0)]  # ratio 1.0
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert any(i["key"] == "low_current_ratio" for i in out["insights"])


def test_insights_sorted_high_before_medium_before_info():
    w = [
        _period(
            "2025-01",
            nm_pct=4.0,
            gm_pct=40.0,
            ca=10_000.0,
            cl=10_000.0,
            wc=-1000.0,
        )
    ]
    cf = _cashflow(operating_cashflow=1000.0)
    out = se.build_statement_bundle(w, cf, _intelligence())
    severities = [i["severity"] for i in out["insights"]]
    rank = {"high": 0, "medium": 1, "info": 2}
    assert severities == sorted(severities, key=lambda s: rank.get(s, 3))


def test_cashflow_trend_last_six_of_series():
    w = [_period("2025-01")]
    series_vals = list(range(20))
    cf = _cashflow(series={"operating_cashflow": series_vals})
    out = se.build_statement_bundle(w, cf, _intelligence())
    assert out["cashflow"]["trend"] == series_vals[-6:]


# ── Accounting correctness & internal consistency ─────────────────────────────


def test_bundle_preserves_balance_sheet_equation():
    w = [_period_accounting_consistent("2025-06")]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    bs = out["balance_sheet"]
    lhs = bs["total_assets"]
    rhs = bs["total_liabilities"] + bs["total_equity"]
    assert lhs == pytest.approx(rhs, rel=0, abs=0.02)


def test_bundle_preserves_income_statement_flow():
    p = _period_accounting_consistent("2025-06")
    is_in = p["income_statement"]
    out = se.build_statement_bundle([p], _cashflow(), _intelligence())
    is_out = out["income_statement"]
    assert is_out["revenue"] - is_out["cogs"] == pytest.approx(is_out["gross_profit"], rel=0, abs=0.02)
    assert is_out["gross_profit"] - is_out["operating_expenses"] == pytest.approx(
        is_out["operating_profit"], rel=0, abs=0.02
    )
    assert is_out["operating_profit"] - is_out["tax"] == pytest.approx(is_out["net_profit"], rel=0, abs=0.02)
    assert is_in["net_profit"] == pytest.approx(is_out["net_profit"], rel=0, abs=0.02)


def test_summary_matches_latest_income_statement_snapshot():
    w = [
        _period_accounting_consistent("2025-01", revenue=100_000.0, cogs=50_000.0, operating_expenses=20_000.0, tax=2_000.0),
        _period_accounting_consistent("2025-02", revenue=110_000.0, cogs=55_000.0, operating_expenses=22_000.0, tax=2_500.0),
    ]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    is_ = out["income_statement"]
    summ = out["summary"]
    assert summ["period"] == is_["period"] == "2025-02"
    assert summ["latest_revenue"] == is_["revenue"]
    assert summ["latest_net_profit"] == is_["net_profit"]
    assert summ["latest_net_margin_pct"] == is_["net_margin_pct"]
    assert summ["latest_gross_margin_pct"] == is_["gross_margin_pct"]
    assert summ["window_revenue_total"] == pytest.approx(210_000.0)
    assert summ["revenue"] == summ["window_revenue_total"]
    assert summ["net_profit"] == summ["window_net_profit_total"]
    bs = out["balance_sheet"]
    cf_out = out["cashflow"]
    assert summ["working_capital"] == bs["working_capital"]
    assert summ["operating_cashflow"] == cf_out["operating_cashflow"]


def test_insight_values_match_bundle_metrics():
    # Single scenario: low nm, negative WC, OCF < 70% of NP, current ratio < 1.2, OCF > 0
    w = [_period("2025-03", rev=100_000.0, np_=3_000.0, nm_pct=3.0, gm_pct=35.0, ca=8_000.0, cl=10_000.0, wc=-2_000.0)]
    cf = _cashflow(operating_cashflow=2_000.0)
    out = se.build_statement_bundle(w, cf, _intelligence())
    is_ = out["income_statement"]
    bs = out["balance_sheet"]
    cf_out = out["cashflow"]

    low = next(i for i in out["insights"] if i["key"] == "low_net_margin")
    assert low["value"] == is_["net_margin_pct"]

    neg = next(i for i in out["insights"] if i["key"] == "negative_working_capital")
    assert neg["value"] == bs["working_capital"]

    below = next(i for i in out["insights"] if i["key"] == "cashflow_below_profit")
    assert below["value"] == cf_out["operating_cashflow"]

    low_cr = next(i for i in out["insights"] if i["key"] == "low_current_ratio")
    assert low_cr["value"] == bs["ratios"]["current_ratio"]

    pos = next(i for i in out["insights"] if i["key"] == "cashflow_positive")
    assert pos["value"] == cf_out["operating_cashflow"]


def test_net_income_matches_revenue_minus_cogs_opex_and_tax():
    """Single-period P&L: NP = revenue − COGS − operating expenses − tax (bundle preserves it)."""
    p = _period_accounting_consistent(
        "2025-04",
        revenue=80_000.0,
        cogs=30_000.0,
        operating_expenses=25_000.0,
        tax=3_000.0,
    )
    out = se.build_statement_bundle([p], _cashflow(), _intelligence())
    is_ = out["income_statement"]
    implied_np = is_["revenue"] - is_["cogs"] - is_["operating_expenses"] - is_["tax"]
    assert implied_np == pytest.approx(is_["net_profit"], rel=0, abs=0.02)


def test_latest_snapshot_is_last_list_element_not_chronological_sort():
    """Callers must pass windowed oldest→newest; engine does not re-sort by period string."""
    w = [_period("2025-02", rev=200_000.0, np_=20_000.0), _period("2025-01", rev=100_000.0, np_=10_000.0)]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert out["period"] == "2025-01"
    assert out["income_statement"]["revenue"] == 100_000.0
    assert out["summary"]["latest_revenue"] == 100_000.0


def test_zero_revenue_bundle_does_not_raise_and_skips_yoy_when_denominator_zero():
    zeros = [_period(f"2025-{i:02d}", rev=0.0, np_=0.0, nm_pct=0.0, gm_pct=0.0) for i in range(1, 14)]
    out = se.build_statement_bundle(zeros, _cashflow(), _intelligence())
    assert out["available"] is True
    assert out["income_statement"]["yoy_change_rev"] is None
    assert out["income_statement"]["revenue"] == 0.0


def test_missing_optional_balance_sheet_keys():
    w = [
        {
            "period": "2025-01",
            "income_statement": {
                "revenue": {"total": 10_000.0, "items": []},
                "cogs": {"total": 0.0, "items": []},
                "gross_profit": 10_000.0,
                "gross_margin_pct": 100.0,
                "expenses": {"total": 5_000.0, "items": []},
                "operating_profit": 5_000.0,
                "tax": {"total": 0.0, "items": []},
                "net_profit": 5_000.0,
                "net_margin_pct": 50.0,
            },
        }
    ]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert out["balance_sheet"]["total_assets"] is None
    assert out["balance_sheet"]["ratios"]["debt_ratio_pct"] is None


def test_current_liabilities_zero_falls_back_to_intelligence_for_current_ratio():
    intel = _intelligence(
        ratios={"profitability": {}, "liquidity": {"current_ratio": {"value": 1.1}}}
    )
    w = [_period("2025-01", ca=50_000.0, cl=0.0)]
    out = se.build_statement_bundle(w, _cashflow(), intel)
    assert out["balance_sheet"]["ratios"]["current_ratio"] == 1.1


def test_total_assets_zero_skips_debt_ratio():
    w = [_period("2025-01", total_assets=0.0, total_liab=0.0, total_eq=0.0, ca=0.0, cl=0.0, wc=0.0)]
    out = se.build_statement_bundle(w, _cashflow(), _intelligence())
    assert out["balance_sheet"]["ratios"]["debt_ratio_pct"] is None


def test_zero_net_profit_skips_cashflow_below_profit_insight():
    w = [_period("2025-01", np_=0.0, nm_pct=0.0)]
    cf = _cashflow(operating_cashflow=-500.0)
    out = se.build_statement_bundle(w, cf, _intelligence())
    assert not any(i["key"] == "cashflow_below_profit" for i in out["insights"])
