"""Tests for canonical structured income statement projection."""

from app.services.structured_income_statement import (
    attach_structured_income_statement,
    build_structured_income_statement,
    build_structured_income_statement_bundle,
)


def _minimal_is(**kw):
    base = {
        "period": "2026-01",
        "income_statement": {
            "revenue": {"total": 1000.0, "items": []},
            "cogs": {"total": 400.0, "items": []},
            "gross_profit": 600.0,
            "gross_margin_pct": 60.0,
            "expenses": {"total": 200.0, "items": []},
            "unclassified_pnl_debits": {"items": [], "total": 50.0},
            "operating_profit": 350.0,
            "operating_margin_pct": 35.0,
            "tax": {"total": 50.0, "items": []},
            "net_profit": 300.0,
            "net_margin_pct": 30.0,
        },
    }
    base.update(kw)
    return base


def test_full_trial_balance_shape_matches_formulas():
    stmt = _minimal_is()
    s = build_structured_income_statement(stmt)
    assert s["revenue"] == 1000.0
    assert s["cogs"] == 400.0
    assert s["gross_profit"] == 600.0  # 1000 - 400
    assert s["gross_margin_pct"] == 60.0
    assert s["opex"] == 250.0  # 200 + 50
    assert s["operating_profit"] == 350.0  # 600 - 250
    assert s["operating_margin_pct"] == 35.0
    assert s["net_profit"] == 300.0  # 350 - 50 tax
    assert s["net_margin_pct"] == 30.0


def test_no_tax_block_net_equals_operating():
    stmt = _minimal_is()
    del stmt["income_statement"]["tax"]
    s = build_structured_income_statement(stmt)
    assert s["operating_profit"] == 350.0
    assert s["net_profit"] == 350.0


def test_missing_unclassified_opex_null_no_silent_zero():
    stmt = _minimal_is()
    del stmt["income_statement"]["unclassified_pnl_debits"]
    s = build_structured_income_statement(stmt)
    assert s["opex"] is None
    # Published operating profit still readable
    assert s["operating_profit"] == 350.0


def test_missing_income_statement_all_null():
    s = build_structured_income_statement({"period": "2026-01"})
    assert s["revenue"] is None
    assert s["net_profit"] is None


def test_attach_mutates_period_dict():
    stmt = _minimal_is()
    attach_structured_income_statement(stmt)
    assert "structured_income_statement" in stmt
    assert stmt["structured_income_statement"]["revenue"] == 1000.0
    meta = stmt["structured_income_statement_meta"]
    assert meta["net_profit_rule"] == "operating_minus_tax"
    assert "income_statement.revenue.total" not in meta["missing_inputs"]


def test_bundle_shape():
    b = build_structured_income_statement_bundle(_minimal_is())
    assert set(b.keys()) == {"structured_income_statement", "structured_income_statement_meta"}


def test_zero_revenue_margins_none():
    stmt = _minimal_is()
    stmt["income_statement"]["revenue"]["total"] = 0.0
    stmt["income_statement"]["cogs"]["total"] = 0.0
    s = build_structured_income_statement(stmt)
    assert s["revenue"] == 0.0
    assert s["gross_margin_pct"] is None
    assert s["operating_margin_pct"] is None
    assert s["net_margin_pct"] is None


def test_analysis_engine_run_analysis_includes_structured():
    """run_analysis attaches structured IS for latest period."""
    from app.services.analysis_engine import run_analysis

    stmts = [_minimal_is()]
    out = run_analysis(stmts)
    assert out["structured_income_statement"]["revenue"] == 1000.0
    assert out["structured_income_statement_meta"]["completeness"] == "full"
