"""
tests/test_analysis_engine.py — Unit tests for analysis_engine (pure functions, no DB).
"""
from __future__ import annotations

import pytest

from app.services import analysis_engine as ae


def _stmt(
    period: str,
    *,
    revenue: float = 100_000.0,
    cogs: float = 40_000.0,
    expenses: float = 30_000.0,
    gross_profit: float = 60_000.0,
    operating_profit: float = 30_000.0,
    net_profit: float = 25_000.0,
    gross_margin_pct: float = 60.0,
    net_margin_pct: float = 25.0,
    ca: float = 50_000.0,
    cl: float = 25_000.0,
    wc: float = 25_000.0,
    total_assets: float = 200_000.0,
    total_liab: float = 80_000.0,
    total_eq: float = 120_000.0,
) -> dict:
    return {
        "period": period,
        "income_statement": {
            "revenue": {"total": revenue},
            "cogs": {"total": cogs},
            "expenses": {"total": expenses},
            "gross_profit": gross_profit,
            "operating_profit": operating_profit,
            "net_profit": net_profit,
            "gross_margin_pct": gross_margin_pct,
            "net_margin_pct": net_margin_pct,
        },
        "balance_sheet": {
            "assets": {"total": total_assets, "items": []},
            "liabilities": {"total": total_liab, "items": []},
            "equity": {"total": total_eq, "items": []},
            "current_assets": ca,
            "current_liabilities": cl,
            "noncurrent_assets": total_assets - ca,
            "noncurrent_liabilities": total_liab - cl,
            "working_capital": wc,
        },
    }


def test_safe_div_and_pct_none_on_bad_inputs():
    assert ae._safe_div(10.0, 2.0) == 5.0
    assert ae._safe_div(10.0, 0) is None
    assert ae._safe_div(None, 5.0) is None
    assert ae._pct(1.0, 4.0) == 25.0
    assert ae._pct(1.0, 0) is None


def test_mom_change_helper():
    assert ae._mom_change(110.0, 100.0) == pytest.approx(10.0)
    assert ae._mom_change(100.0, None) is None
    assert ae._mom_change(100.0, 0) is None


def test_run_analysis_empty():
    out = ae.run_analysis([])
    assert out["period_count"] == 0
    assert out["latest"] is None
    assert out["ratios"] == {}
    assert out["trends"] == {}
    assert out["periods"] == []


def test_compute_ratios_reads_statement_net_profit_and_working_capital():
    stmt = _stmt("2025-04", net_profit=12_345.67, wc=9_999.5)
    r = ae.compute_ratios(stmt, "2025-04")
    assert r["profitability"]["net_profit"] == pytest.approx(12345.67, rel=0, abs=0.01)
    assert r["liquidity"]["working_capital"] == pytest.approx(9999.5, rel=0, abs=0.01)


def test_compute_ratios_current_ratio():
    stmt = _stmt("2025-01", ca=40_000.0, cl=16_000.0)
    r = ae.compute_ratios(stmt)
    assert r["liquidity"]["current_ratio"] == pytest.approx(2.5)


def test_compute_ratios_liquidity_none_when_approximated():
    stmt = _stmt("2025-01")
    stmt["balance_sheet"]["current_assets_approximated"] = True
    r = ae.compute_ratios(stmt)
    assert r["liquidity"]["current_ratio"] is None
    assert r["liquidity"]["quick_ratio"] is None
    assert r["liquidity"]["liquidity_approximated"] is True


def test_compute_trends_mom_two_periods():
    stmts = [
        _stmt("2025-01", revenue=100_000.0, net_profit=10_000.0),
        _stmt("2025-02", revenue=110_000.0, net_profit=11_000.0),
    ]
    t = ae.compute_trends(stmts)
    assert t["periods"] == ["2025-01", "2025-02"]
    assert t["revenue_mom_pct"][0] is None
    assert t["revenue_mom_pct"][1] == pytest.approx(10.0)
    assert t["net_profit_mom_pct"][1] == pytest.approx(10.0)


def test_compute_trends_yoy_thirteen_periods():
    stmts = [_stmt(f"2024-{i:02d}", revenue=100_000.0, net_profit=5_000.0) for i in range(1, 13)]
    stmts.append(_stmt("2025-01", revenue=130_000.0, net_profit=6_500.0))
    assert len(stmts) == 13
    t = ae.compute_trends(stmts)
    assert t["yoy_revenue_pct"] == pytest.approx(30.0)
    assert t["yoy_net_profit_pct"] == pytest.approx(30.0)


def test_run_analysis_latest_matches_last_period_ratios():
    stmts = [_stmt("2025-01"), _stmt("2025-02", net_profit=99.0)]
    out = ae.run_analysis(stmts)
    assert out["period_count"] == 2
    assert out["latest"] == out["ratios"]["2025-02"]
    assert out["latest"]["profitability"]["net_profit"] == 99.0


def test_consecutive_decline_and_trend_direction():
    assert ae._consecutive_decline([100.0, 90.0, 80.0]) == 2
    assert ae._consecutive_decline([100.0, 110.0]) == 0
    assert ae._trend_direction([None, 2.0, 3.0]) == "improving"
    assert ae._trend_direction([None, -2.0, -3.0]) == "declining"
    assert ae._trend_direction([1.0]) == "stable"


def test_extract_bs_components_totals():
    bs = _stmt("x")["balance_sheet"]
    c = ae._extract_bs_components(bs)
    assert c["total_assets"] == 200_000.0
    assert c["total_liabilities"] == 80_000.0
    assert c["total_equity"] == 120_000.0
    assert c["current_assets"] == 50_000.0


def test_profitability_reads_margins_and_profit_from_statement():
    stmt = _stmt(
        "2025-06",
        gross_margin_pct=44.4,
        net_margin_pct=12.2,
        net_profit=12_200.0,
        gross_profit=44_400.0,
    )
    r = ae.compute_ratios(stmt)
    assert r["profitability"]["gross_margin_pct"] == 44.4
    assert r["profitability"]["net_margin_pct"] == 12.2
    assert r["profitability"]["net_profit"] == 12_200.0
    assert r["profitability"]["gross_profit"] == 44_400.0


def test_liquidity_working_capital_and_quick_ratio():
    stmt = _stmt("2025-01", ca=100_000.0, cl=40_000.0, wc=60_000.0)
    stmt["balance_sheet"]["assets"] = {"total": 200_000.0, "items": [{"account_code": "1250", "amount": 25_000.0}]}
    r = ae.compute_ratios(stmt)
    assert r["liquidity"]["working_capital"] == 60_000.0
    assert r["liquidity"]["quick_ratio"] == pytest.approx((100_000.0 - 25_000.0) / 40_000.0)


def test_leverage_debt_to_equity_none_when_equity_nonpositive():
    stmt = _stmt("2025-01", total_eq=0.0)
    r = ae.compute_ratios(stmt)
    assert r["leverage"]["debt_to_equity"] is None
    stmt2 = _stmt("2025-01", total_eq=-10_000.0)
    assert ae.compute_ratios(stmt2)["leverage"]["debt_to_equity"] is None


def test_compute_trends_single_period_yields_empty_mom():
    t = ae.compute_trends([_stmt("2025-01")])
    assert t["revenue_mom_pct"] == [None]
    assert t["yoy_revenue_pct"] is None


def test_compute_trends_consecutive_decline_streak():
    stmts = [
        _stmt("2025-01", revenue=300.0),
        _stmt("2025-02", revenue=200.0),
        _stmt("2025-03", revenue=100.0),
    ]
    t = ae.compute_trends(stmts)
    assert t["revenue_decline_streak"] == 2


def test_run_analysis_ratios_keyed_by_period():
    stmts = [_stmt("2025-01", net_profit=1.0), _stmt("2025-02", net_profit=2.0)]
    out = ae.run_analysis(stmts)
    assert set(out["ratios"].keys()) == {"2025-01", "2025-02"}
    assert out["latest"]["profitability"]["net_profit"] == 2.0
