"""Phase 4 (hardened): hierarchy values mirror canonical fields only."""
from app.services.statement_hierarchy import (
    build_balance_sheet_hierarchy,
    build_cashflow_hierarchy,
    build_income_statement_hierarchy,
    build_statement_hierarchy,
)


def _sample_is():
    return {
        "revenue": {
            "items": [
                {"account_code": "4001", "account_name": "Sales", "amount": 1000.0, "mapped_type": "revenue"},
                {"account_code": "4002", "account_name": "Discounts", "amount": -100.0, "mapped_type": "revenue"},
            ],
            "total": 900.0,
        },
        "cogs": {
            "items": [
                {"account_code": "5001", "account_name": "Materials inventory", "amount": 200.0, "mapped_type": "cogs"},
                {"account_code": "5002", "account_name": "Direct labor", "amount": 100.0, "mapped_type": "cogs"},
            ],
            "total": 300.0,
        },
        "gross_profit": 600.0,
        "expenses": {
            "items": [
                {"account_code": "6001", "account_name": "Salaries", "amount": 150.0, "mapped_type": "expenses"},
                {"account_code": "6601", "account_name": "Shipping", "amount": 50.0, "mapped_type": "expenses"},
            ],
            "total": 200.0,
        },
        "unclassified_pnl_debits": {"items": [], "total": 0.0},
        "operating_profit": 400.0,
        "tax": {"items": [], "total": 40.0},
        "net_profit": 360.0,
    }


def _sample_bs():
    return {
        "assets": {
            "items": [
                {"account_code": "1100", "account_name": "Cash", "amount": 300.0, "mapped_type": "assets"},
                {"account_code": "1500", "account_name": "Equipment", "amount": 200.0, "mapped_type": "assets"},
            ],
            "total": 500.0,
        },
        "liabilities": {
            "items": [
                {"account_code": "2100", "account_name": "AP", "amount": 100.0, "mapped_type": "liabilities"},
                {"account_code": "2500", "account_name": "LT debt", "amount": 100.0, "mapped_type": "liabilities"},
            ],
            "total": 200.0,
        },
        "equity": {
            "items": [{"account_code": "3000", "account_name": "Equity", "amount": 300.0, "mapped_type": "equity"}],
            "total": 300.0,
        },
        "current_assets": 300.0,
        "noncurrent_assets": 200.0,
        "current_liabilities": 100.0,
        "noncurrent_liabilities": 100.0,
        "working_capital": 200.0,
    }


def test_income_hierarchy_canonical_totals_only():
    is_ = _sample_is()
    h = build_income_statement_hierarchy(is_)
    root = h["root"]
    assert root["key"] == "income_statement"
    assert "integrity" not in h
    rev = next(c for c in root["children"] if c["key"] == "revenue")
    total_node = next(c for c in rev["children"] if c["key"] == "revenue_total")
    assert total_node["value"] == 900.0
    line_nodes = [c for c in rev["children"] if c.get("leaf")]
    assert len(line_nodes) == 2
    cogs = next(c for c in root["children"] if c["key"] == "cogs_total")
    assert cogs["value"] == 300.0
    assert len(cogs["children"]) == 2
    opex = next(c for c in root["children"] if c["key"] == "opex_total")
    assert opex["value"] == 200.0
    assert len(opex["children"]) == 2
    gp = next(c for c in root["children"] if c["key"] == "gross_profit")
    assert gp["value"] == 600.0
    npn = next(c for c in root["children"] if c["key"] == "net_profit")
    assert npn["value"] == 360.0


def test_balance_sheet_totals_from_dict():
    bs = _sample_bs()
    h = build_balance_sheet_hierarchy(bs)
    assert "integrity" not in h
    root = h["root"]
    assets = next(c for c in root["children"] if c["key"] == "assets")
    assert assets["value"] == 500.0
    assert len(assets["children"]) == 2
    ca = next(c for c in root["children"] if c["key"] == "current_assets")
    assert ca["value"] == 300.0
    assert ca["children"] == []
    wc = next(c for c in root["children"] if c["key"] == "working_capital")
    assert wc["value"] == 200.0


def test_cashflow_no_implied_investing():
    cf_raw = {
        "operating_cashflow": 450.0,
        "free_cashflow": 400.0,
        "debug": {
            "net_profit": 360.0,
            "da_addback": 50.0,
            "delta_receivables": 10.0,
            "delta_inventory": -5.0,
            "delta_payables": 20.0,
            "wc_adjustment": 15.0,
        },
        "flags": {},
    }
    h = build_cashflow_hierarchy(cf_raw, period="2026-01")
    op = next(c for c in h["root"]["children"] if c["key"] == "cf_operating")
    assert op["value"] == 450.0
    inv = next(c for c in h["root"]["children"] if c["key"] == "cf_investing")
    assert inv["value"] is None
    assert inv["children"] == []
    assert inv.get("note") == "not_modeled"
    fcf_node = next(c for c in op["children"] if c["key"] == "cf_fcf")
    assert fcf_node["value"] == 400.0


def test_bundle_has_no_integrity_block():
    b = build_statement_hierarchy(_sample_is(), _sample_bs(), {}, period="2026-01")
    assert b["available"] is True
    assert "integrity" not in b
    assert b["income_statement"]["key"] == "income_statement"
    assert b["balance_sheet"]["key"] == "balance_sheet"
