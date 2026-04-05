"""Tests for structured profit story mapping."""

from app.services.structured_profit_story import (
    build_structured_profit_story_from_analysis,
    build_structured_profit_story_from_window,
)
from tests.test_structured_income_statement_variance import _stmt


def _analysis_like(
    *,
    paradox_up_down: bool = False,
    net_result: str | None = "profit_up",
    primary: str | None = "revenue",
    nm: float | None = 12.0,
    completeness: str = "full",
):
    a = _stmt("2026-01", 1000, 400, 600, 200, 50, 50, 300)
    b = _stmt("2026-02", 1100, 400, 700, 250, 50, 50, 350)
    from app.services.structured_income_statement import attach_structured_income_statement
    from app.services.structured_income_statement_variance import (
        build_structured_income_statement_variance_bundle_from_window,
    )
    from app.services.structured_profit_bridge import (
        build_structured_profit_bridge_bundle_from_window,
    )

    attach_structured_income_statement(a)
    attach_structured_income_statement(b)
    if paradox_up_down:
        b["income_statement"]["revenue"]["total"] = 1200.0
        b["income_statement"]["net_profit"] = 250.0
        attach_structured_income_statement(b)
    var = build_structured_income_statement_variance_bundle_from_window([a, b])
    bridge = build_structured_profit_bridge_bundle_from_window([a, b])
    interp = dict(bridge["structured_profit_bridge_interpretation"])
    if paradox_up_down:
        interp["paradox_flags"] = {"revenue_up_profit_down": True, "revenue_down_profit_up": False}
        interp["net_result"] = "profit_down"
    else:
        interp["net_result"] = net_result
        interp["primary_driver"] = primary
    pack = {
        **bridge,
        "structured_profit_bridge_interpretation": interp,
        "structured_profit_bridge_meta": {**bridge["structured_profit_bridge_meta"], "completeness": completeness},
        "latest": {"profitability": {"net_margin_pct": nm}},
    }
    return pack


def test_paradox_summary_type():
    al = _analysis_like(paradox_up_down=True)
    s = build_structured_profit_story_from_analysis(al)
    assert s["summary_type"] == "paradox_growth_loss"
    assert s["what_changed_key"] == "profit_story.paradox_growth_loss.what_changed"
    assert "delta_rev_fmt" in s["what_changed_params"]


def test_cost_pressure():
    al = _analysis_like(net_result="profit_down", primary="opex")
    s = build_structured_profit_story_from_analysis(al)
    assert s["summary_type"] == "cost_pressure"


def test_margin_compression():
    al = _analysis_like(net_result="profit_down", primary="cogs")
    s = build_structured_profit_story_from_analysis(al)
    assert s["summary_type"] == "margin_compression"


def test_healthy_growth_high_nm():
    al = _analysis_like(net_result="profit_up", primary="revenue", nm=15.0)
    s = build_structured_profit_story_from_analysis(al)
    assert s["summary_type"] == "healthy_growth"


def test_nm_pct_in_all_story_param_bags_for_templates():
    """healthy_growth.why (and similar) reference {nm_pct}; all param bags must include it."""
    al = _analysis_like(net_result="profit_up", primary="revenue", nm=15.0)
    s = build_structured_profit_story_from_analysis(al)
    assert s["what_changed_params"].get("nm_pct") == "15.0"
    assert s["why_params"].get("nm_pct") == "15.0"
    assert s["action_params"].get("nm_pct") == "15.0"


def test_profit_recovery_low_nm():
    al = _analysis_like(net_result="profit_up", primary="revenue", nm=5.0)
    s = build_structured_profit_story_from_analysis(al)
    assert s["summary_type"] == "profit_recovery"


def test_mixed_driver():
    al = _analysis_like(net_result="profit_up", primary="mixed")
    s = build_structured_profit_story_from_analysis(al)
    assert s["summary_type"] == "mixed"


def test_from_window_matches_analysis():
    a = _stmt("2026-01", 1000, 400, 600, 200, 50, 50, 300)
    b = _stmt("2026-02", 1100, 400, 700, 200, 50, 50, 400)
    from app.services.structured_income_statement import attach_structured_income_statement

    attach_structured_income_statement(a)
    attach_structured_income_statement(b)
    sw = build_structured_profit_story_from_window(
        [a, b], latest_profitability={"net_margin_pct": 14.0}
    )
    from app.services.analysis_engine import run_analysis

    ra = run_analysis([a, b])
    assert sw["latest_period"] == ra["structured_profit_story"]["latest_period"]
    assert sw["summary_type"] == ra["structured_profit_story"]["summary_type"]
