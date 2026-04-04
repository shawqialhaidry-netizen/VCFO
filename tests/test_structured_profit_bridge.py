"""Tests for structured profit bridge + interpretation."""

from app.services.structured_income_statement import attach_structured_income_statement
from app.services.structured_profit_bridge import (
    build_structured_profit_bridge_bundle_from_window,
)
from tests.test_structured_income_statement_variance import _stmt


def _two_periods():
    a = _stmt("2026-01", 1000, 400, 600, 200, 50, 50, 300)
    b = _stmt("2026-02", 1200, 500, 700, 200, 50, 50, 350)
    return [a, b]


def test_bridge_deltas_match_variance():
    w = _two_periods()
    pack = build_structured_profit_bridge_bundle_from_window(w)
    bridge = pack["structured_profit_bridge"]
    assert bridge["latest_period"] == "2026-02"
    assert bridge["previous_period"] == "2026-01"
    assert bridge["revenue_change"]["delta"] == 200.0
    assert bridge["cogs_change"]["delta"] == 100.0


def test_revenue_effect_positive_cogs_negative():
    w = _two_periods()
    interp = build_structured_profit_bridge_bundle_from_window(w)[
        "structured_profit_bridge_interpretation"
    ]
    assert interp["revenue_effect"] == "positive"
    assert interp["cogs_effect"] == "negative"
    assert interp["opex_effect"] == "neutral"


def test_primary_driver_largest_abs_delta():
    w = _two_periods()
    interp = build_structured_profit_bridge_bundle_from_window(w)[
        "structured_profit_bridge_interpretation"
    ]
    assert interp["primary_driver"] == "revenue"


def test_paradox_revenue_up_profit_down():
    a = _stmt("2026-01", 1000, 400, 600, 200, 50, 50, 300)
    b = _stmt("2026-02", 1100, 700, 400, 200, 50, 50, 100)
    attach_structured_income_statement(a)
    attach_structured_income_statement(b)
    interp = build_structured_profit_bridge_bundle_from_window([a, b])[
        "structured_profit_bridge_interpretation"
    ]
    assert interp["paradox_flags"]["revenue_up_profit_down"] is True
    assert interp["net_result"] == "profit_down"


def test_tie_mixed_driver():
    a = _stmt("2026-01", 1000, 400, 600, 200, 50, 50, 300)
    b = _stmt("2026-02", 1100, 500, 600, 200, 50, 50, 300)
    attach_structured_income_statement(a)
    attach_structured_income_statement(b)
    interp = build_structured_profit_bridge_bundle_from_window([a, b])[
        "structured_profit_bridge_interpretation"
    ]
    assert interp["primary_driver"] == "mixed"


def test_insufficient_periods_meta():
    one = _stmt("2026-01", 1000, 400, 600, 200, 50, 50, 300)
    attach_structured_income_statement(one)
    pack = build_structured_profit_bridge_bundle_from_window([one])
    assert pack["structured_profit_bridge_meta"]["completeness"] == "none"
    assert pack["structured_profit_bridge_meta"]["missing_components"] == [
        "insufficient_periods"
    ]


def test_run_analysis_includes_bridge():
    from app.services.analysis_engine import run_analysis

    a, b = _two_periods()
    r = run_analysis([a, b])
    assert "structured_profit_bridge" in r
    assert r["structured_profit_bridge_interpretation"]["primary_driver"] == "revenue"
