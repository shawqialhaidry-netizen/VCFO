"""
statement_hierarchy.py — Phase 4 (hardened)

Presentation-only projection of canonical financial outputs.

Rules:
  - Numeric node values are copied from financial_statements / cashflow_engine fields
    or from per-line amounts already present on canonical line-item dicts.
  - No name/code-keyword inference, no expense_engine classification, no implied figures.
  - No integrity validation — that belongs to the financial truth layer.
"""
from __future__ import annotations

from typing import Any, Optional

_SCHEMA_VERSION = 2


def _r2(v: Any) -> Optional[float]:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _item_amount(item: dict) -> float:
    try:
        return round(float(item.get("amount") or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _node(
    key: str,
    label: str,
    depth: int,
    value: Any = None,
    children: Optional[list] = None,
    label_key: Optional[str] = None,
    **extra: Any,
) -> dict:
    out = {
        "key": key,
        "label": label,
        "label_key": label_key,
        "value": _r2(value) if value is not None and value != "" else None,
        "children": children if children is not None else [],
        "depth": depth,
    }
    out.update(extra)
    return out


def _line_leaf(prefix: str, idx: int, item: dict, depth: int) -> dict:
    code = str(item.get("account_code") or "").strip()
    safe = code.replace(".", "_").replace("/", "_") if code else "x"
    key = f"{prefix}_line_{safe}_{idx}"
    amt = _item_amount(item)
    return _node(
        key,
        str(item.get("account_name") or code or "Account"),
        depth,
        value=amt,
        label_key=None,
        account_code=code or None,
        account_name=item.get("account_name"),
        mapped_type=item.get("mapped_type"),
        leaf=True,
    )


def build_income_statement_hierarchy(is_: dict) -> dict:
    """
    Project canonical period ``income_statement`` (nested sections from statements_to_dict).

    Grouping: section boundaries only (revenue / cogs / expenses / tax / unclassified).
    Line values: ``amount`` on each item dict. Section totals: ``total`` or scalar fields
    from the same dict — never sums of UI buckets used as authoritative totals.
    """
    rev_sec = is_.get("revenue") or {}
    cogs_sec = is_.get("cogs") or {}
    exp_sec = is_.get("expenses") or {}
    tax_sec = is_.get("tax") or {}
    unc_sec = is_.get("unclassified_pnl_debits") or {}

    rev_items = [x for x in (rev_sec.get("items") or []) if isinstance(x, dict)]
    total_rev = _r2(rev_sec.get("total"))

    cogs_items = [x for x in (cogs_sec.get("items") or []) if isinstance(x, dict)]
    total_cogs = _r2(cogs_sec.get("total"))

    exp_items = [x for x in (exp_sec.get("items") or []) if isinstance(x, dict)]
    total_exp = _r2(exp_sec.get("total"))

    unc_items = [x for x in (unc_sec.get("items") or []) if isinstance(x, dict)]
    total_unc = _r2(unc_sec.get("total"))

    gp = _r2(is_.get("gross_profit"))
    op_profit = _r2(is_.get("operating_profit"))
    total_tax = _r2(tax_sec.get("total"))
    np_ = _r2(is_.get("net_profit"))

    rev_line_nodes = [_line_leaf("rev", i, x, 2) for i, x in enumerate(rev_items)]
    revenue_children = rev_line_nodes + [
        _node(
            "revenue_total",
            "Net revenue (total)",
            2,
            value=total_rev,
            children=[],
            label_key="stmt_hier_net_revenue",
        )
    ]
    revenue_block = _node(
        "revenue",
        "Revenue",
        1,
        value=None,
        children=revenue_children,
        label_key="stmt_hier_revenue",
    )

    cogs_subtotal = _node(
        "cogs_total",
        "Total COGS",
        2,
        value=total_cogs,
        children=[_line_leaf("cogs", i, x, 3) for i, x in enumerate(cogs_items)],
        label_key="stmt_hier_total_cogs",
    )

    opex_subtotal = _node(
        "opex_total",
        "Total operating expenses",
        2,
        value=total_exp,
        children=[_line_leaf("opex", i, x, 3) for i, x in enumerate(exp_items)],
        label_key="stmt_hier_total_opex",
    )

    unc_children = [_line_leaf("unc", i, x, 3) for i, x in enumerate(unc_items)]
    unc_block = _node(
        "unclassified_pnl",
        "Unclassified P&L debits",
        1,
        value=total_unc if total_unc else None,
        children=unc_children,
        label_key="stmt_hier_unclassified_pnl",
    )

    tax_children = [
        _line_leaf("tax", i, x, 3)
        for i, x in enumerate(tax_sec.get("items") or [])
        if isinstance(x, dict)
    ]
    tax_block = _node(
        "tax",
        "Tax",
        1,
        value=total_tax,
        children=tax_children,
        label_key="stmt_hier_tax",
    )

    gp_node = _node(
        "gross_profit",
        "Gross profit",
        1,
        value=gp,
        children=[],
        label_key="stmt_hier_gross_profit",
    )
    op_node = _node(
        "operating_profit",
        "Operating profit",
        1,
        value=op_profit,
        children=[],
        label_key="stmt_hier_operating_profit",
    )
    np_node = _node(
        "net_profit",
        "Net profit",
        1,
        value=np_,
        children=[],
        label_key="stmt_hier_net_profit",
    )

    children = [
        revenue_block,
        cogs_subtotal,
        gp_node,
        opex_subtotal,
    ]
    if unc_children or (total_unc and abs(float(total_unc)) > 0.005):
        children.append(unc_block)
    children.extend([op_node, tax_block, np_node])

    return {
        "root": _node(
            "income_statement",
            "Income statement",
            0,
            value=None,
            children=children,
            label_key="stmt_section_is",
        ),
    }


def build_balance_sheet_hierarchy(bs: dict) -> dict:
    """
    Canonical balance_sheet dict only.

    Line items are listed under their statement section (assets / liabilities / equity).
    Current vs non-current totals appear as separate nodes with values taken directly from
    the balance_sheet dict (``current_assets``, ``noncurrent_assets``, etc.) — no line
    allocation into those buckets (avoids any non-truth-layer assignment rule).
    """
    assets = bs.get("assets") or {}
    liab = bs.get("liabilities") or {}
    eq = bs.get("equity") or {}

    ca = _r2(bs.get("current_assets"))
    nca = _r2(bs.get("noncurrent_assets"))
    cl = _r2(bs.get("current_liabilities"))
    ncl = _r2(bs.get("noncurrent_liabilities"))
    ta = _r2(assets.get("total"))
    tl = _r2(liab.get("total"))
    te = _r2(eq.get("total"))
    wc = _r2(bs.get("working_capital"))

    asset_lines = [
        _line_leaf("asset", i, item, 3)
        for i, item in enumerate(assets.get("items") or [])
        if isinstance(item, dict)
    ]
    liab_lines = [
        _line_leaf("liab", i, item, 3)
        for i, item in enumerate(liab.get("items") or [])
        if isinstance(item, dict)
    ]
    eq_lines = [
        _line_leaf("eq", i, item, 3)
        for i, item in enumerate(eq.get("items") or [])
        if isinstance(item, dict)
    ]

    assets_node = _node(
        "assets",
        "Assets",
        1,
        value=ta,
        children=asset_lines,
        label_key="stmt_hier_assets",
    )

    ca_node = _node(
        "current_assets",
        "Current assets (total)",
        1,
        value=ca,
        children=[],
        label_key="stmt_hier_current_assets",
    )
    nca_node = _node(
        "noncurrent_assets",
        "Non-current assets (total)",
        1,
        value=nca,
        children=[],
        label_key="stmt_hier_noncurrent_assets",
    )

    liab_node = _node(
        "liabilities",
        "Liabilities",
        1,
        value=tl,
        children=liab_lines,
        label_key="stmt_hier_liabilities",
    )

    cl_node = _node(
        "current_liabilities",
        "Current liabilities (total)",
        1,
        value=cl,
        children=[],
        label_key="stmt_hier_current_liabilities",
    )
    ncl_node = _node(
        "noncurrent_liabilities",
        "Non-current liabilities (total)",
        1,
        value=ncl,
        children=[],
        label_key="stmt_hier_noncurrent_liabilities",
    )

    eq_node = _node(
        "equity",
        "Equity",
        1,
        value=te,
        children=eq_lines,
        label_key="stmt_hier_equity",
    )

    wc_node = _node(
        "working_capital",
        "Working capital (current assets − current liabilities)",
        1,
        value=wc,
        children=[],
        label_key="stmt_hier_working_capital",
    )

    children = [
        assets_node,
        ca_node,
        nca_node,
        liab_node,
        cl_node,
        ncl_node,
        eq_node,
        wc_node,
    ]

    return {
        "root": _node(
            "balance_sheet",
            "Balance sheet",
            0,
            value=None,
            children=children,
            label_key="stmt_section_bs",
        ),
    }


def build_cashflow_hierarchy(cashflow_raw: dict, period: str = "") -> dict:
    """
    Pass-through of cashflow_engine top-level and ``debug`` fields only.
    Investing / financing: explicitly unavailable (no engine lines — never inferred).
    """
    dbg = cashflow_raw.get("debug") if isinstance(cashflow_raw.get("debug"), dict) else {}

    ocf = _r2(cashflow_raw.get("operating_cashflow"))
    fcf = _r2(cashflow_raw.get("free_cashflow"))
    np_ = _r2(dbg.get("net_profit"))
    da = _r2(dbg.get("da_addback"))
    dr = _r2(dbg.get("delta_receivables"))
    di = _r2(dbg.get("delta_inventory"))
    dp = _r2(dbg.get("delta_payables"))
    wc_adj = _r2(dbg.get("wc_adjustment"))

    op_children = [
        _node("cf_np", "Net profit (from statements)", 2, value=np_, label_key="stmt_hier_cf_np"),
        _node("cf_da", "Depreciation & amortization (add-back)", 2, value=da, label_key="stmt_hier_cf_da"),
        _node(
            "cf_d_ar",
            "Change in receivables",
            2,
            value=dr,
            label_key="stmt_hier_cf_d_ar",
        ),
        _node(
            "cf_d_inv",
            "Change in inventory",
            2,
            value=di,
            label_key="stmt_hier_cf_d_inv",
        ),
        _node(
            "cf_d_ap",
            "Change in payables",
            2,
            value=dp,
            label_key="stmt_hier_cf_d_ap",
        ),
        _node(
            "cf_wc_adj",
            "Working capital adjustment (as reported)",
            2,
            value=wc_adj,
            label_key="stmt_hier_cf_wc_adj",
        ),
    ]
    if fcf is not None or cashflow_raw.get("free_cashflow") is not None:
        op_children.append(
            _node(
                "cf_fcf",
                "Free cash flow (as reported)",
                2,
                value=fcf,
                label_key="stmt_hier_cf_fcf",
            )
        )

    operating = _node(
        "cf_operating",
        "Operating activities",
        1,
        value=ocf,
        children=op_children,
        label_key="stmt_hier_cf_operating",
    )

    investing = _node(
        "cf_investing",
        "Investing activities",
        1,
        value=None,
        children=[],
        label_key="stmt_hier_cf_investing",
        availability="unavailable",
        note="not_modeled",
    )

    financing = _node(
        "cf_financing",
        "Financing activities",
        1,
        value=None,
        children=[],
        label_key="stmt_hier_cf_financing",
        availability="unavailable",
        note="not_modeled",
    )

    return {
        "root": _node(
            "cashflow_statement",
            "Cash flow (indirect operating view)",
            0,
            value=None,
            children=[operating, investing, financing],
            label_key="stmt_hier_cashflow_root",
        ),
        "period": period or str(cashflow_raw.get("period") or ""),
        "flags": cashflow_raw.get("flags") or {},
    }


def build_statement_hierarchy(
    income_statement_dict: dict,
    balance_sheet_dict: dict,
    cashflow_raw: dict,
    period: str = "",
) -> dict:
    if not income_statement_dict and not balance_sheet_dict:
        return {
            "schema_version": _SCHEMA_VERSION,
            "available": False,
            "period": period,
        }

    is_h = build_income_statement_hierarchy(income_statement_dict or {})
    bs_h = build_balance_sheet_hierarchy(balance_sheet_dict or {})
    cf_h = build_cashflow_hierarchy(cashflow_raw or {}, period=period)

    return {
        "schema_version": _SCHEMA_VERSION,
        "available": True,
        "period": period,
        "income_statement": is_h["root"],
        "balance_sheet": bs_h["root"],
        "cashflow": cf_h["root"],
        "cashflow_meta": {
            "period": cf_h.get("period"),
            "flags": cf_h.get("flags"),
        },
    }
