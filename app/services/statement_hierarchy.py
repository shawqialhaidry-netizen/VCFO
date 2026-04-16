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
PROV_DIRECT_SOURCE_LEAF = "direct_source_leaf"
PROV_MERGED_SOURCE_LEAF = "merged_source_leaf"
PROV_DERIVED_SUBTOTAL = "derived_subtotal"
PROV_DERIVED_METRIC = "derived_metric"
PROV_SYNTHETIC_INJECTED = "synthetic_injected"
PROV_STRUCTURAL_CONTAINER = "structural_container"


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
        provenance=item.get("provenance") or PROV_DIRECT_SOURCE_LEAF,
        source_row_count=int(item.get("source_row_count") or 1),
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
            provenance=PROV_DERIVED_SUBTOTAL,
        )
    ]
    revenue_block = _node(
        "revenue",
        "Revenue",
        1,
        value=None,
        children=revenue_children,
        label_key="stmt_hier_revenue",
        provenance=PROV_STRUCTURAL_CONTAINER,
    )

    cogs_subtotal = _node(
        "cogs_total",
        "Total COGS",
        1,
        value=total_cogs,
        children=[_line_leaf("cogs", i, x, 2) for i, x in enumerate(cogs_items)],
        label_key="stmt_hier_total_cogs",
        provenance=PROV_DERIVED_SUBTOTAL,
    )

    opex_subtotal = _node(
        "opex_total",
        "Total operating expenses",
        1,
        value=total_exp,
        children=[_line_leaf("opex", i, x, 2) for i, x in enumerate(exp_items)],
        label_key="stmt_hier_total_opex",
        provenance=PROV_DERIVED_SUBTOTAL,
    )

    unc_children = [_line_leaf("unc", i, x, 3) for i, x in enumerate(unc_items)]
    unc_block = _node(
        "unclassified_pnl",
        "Unclassified P&L debits",
        1,
        value=total_unc if total_unc else None,
        children=unc_children,
        label_key="stmt_hier_unclassified_pnl",
        provenance=PROV_STRUCTURAL_CONTAINER,
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
        provenance=PROV_STRUCTURAL_CONTAINER,
    )

    gp_node = _node(
        "gross_profit",
        "Gross profit",
        1,
        value=gp,
        children=[],
        label_key="stmt_hier_gross_profit",
        provenance=PROV_DERIVED_METRIC,
    )
    op_node = _node(
        "operating_profit",
        "Operating profit",
        1,
        value=op_profit,
        children=[],
        label_key="stmt_hier_operating_profit",
        provenance=PROV_DERIVED_METRIC,
    )
    np_node = _node(
        "net_profit",
        "Net profit",
        1,
        value=np_,
        children=[],
        label_key="stmt_hier_net_profit",
        provenance=PROV_DERIVED_METRIC,
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
            provenance=PROV_STRUCTURAL_CONTAINER,
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
    has_data = bool(asset_lines or liab_lines or eq_lines)

    assets_node = _node(
        "assets",
        "Assets",
        1,
        value=ta,
        children=asset_lines,
        label_key="stmt_hier_assets",
        provenance=PROV_DERIVED_SUBTOTAL,
    )

    ca_node = _node(
        "current_assets",
        "Current assets (total)",
        1,
        value=ca,
        children=[],
        label_key="stmt_hier_current_assets",
        provenance=PROV_DERIVED_METRIC,
    )
    nca_node = _node(
        "noncurrent_assets",
        "Non-current assets (total)",
        1,
        value=nca,
        children=[],
        label_key="stmt_hier_noncurrent_assets",
        provenance=PROV_DERIVED_METRIC,
    )

    liab_node = _node(
        "liabilities",
        "Liabilities",
        1,
        value=tl,
        children=liab_lines,
        label_key="stmt_hier_liabilities",
        provenance=PROV_DERIVED_SUBTOTAL,
    )

    cl_node = _node(
        "current_liabilities",
        "Current liabilities (total)",
        1,
        value=cl,
        children=[],
        label_key="stmt_hier_current_liabilities",
        provenance=PROV_DERIVED_METRIC,
    )
    ncl_node = _node(
        "noncurrent_liabilities",
        "Non-current liabilities (total)",
        1,
        value=ncl,
        children=[],
        label_key="stmt_hier_noncurrent_liabilities",
        provenance=PROV_DERIVED_METRIC,
    )

    eq_node = _node(
        "equity",
        "Equity",
        1,
        value=te,
        children=eq_lines,
        label_key="stmt_hier_equity",
        provenance=PROV_DERIVED_SUBTOTAL,
    )

    wc_node = _node(
        "working_capital",
        "Working capital (current assets − current liabilities)",
        1,
        value=wc,
        children=[],
        label_key="stmt_hier_working_capital",
        provenance=PROV_DERIVED_METRIC,
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
            has_data=has_data,
            provenance=PROV_STRUCTURAL_CONTAINER,
        ),
    }


def build_cashflow_hierarchy(cashflow_raw: dict, period: str = "") -> dict:
    """
    Project additive cashflow_engine output into statement hierarchy form.
    Sections are rendered only from explicit engine fields; unavailable sections
    remain explicit and flagged.
    """
    op = cashflow_raw.get("operating") if isinstance(cashflow_raw.get("operating"), dict) else {}
    inv = cashflow_raw.get("investing") if isinstance(cashflow_raw.get("investing"), dict) else {}
    fin = cashflow_raw.get("financing") if isinstance(cashflow_raw.get("financing"), dict) else {}
    stmt_meta = cashflow_raw.get("statement_meta") if isinstance(cashflow_raw.get("statement_meta"), dict) else {}

    def _cf_line(line: dict, idx: int, prefix: str) -> dict:
        line_id = str(line.get("id") or f"{prefix}_{idx}")
        return _node(
            f"{prefix}_{line_id}",
            str(line.get("label") or line_id),
            2,
            value=line.get("amount"),
            label_key=None,
            provenance=PROV_DERIVED_METRIC,
            line_id=line_id,
        )

    def _cf_section(
        key: str,
        label: str,
        label_key: str,
        section: dict,
        subtotal_fallback: Any = None,
    ) -> dict:
        lines = section.get("lines") if isinstance(section.get("lines"), list) else []
        children = [_cf_line(line, i, key) for i, line in enumerate(lines) if isinstance(line, dict)]
        extra = {}
        if section.get("available") is False:
            extra["availability"] = "partial"
            extra["note"] = section.get("reason") or "not_modeled"
        if isinstance(section.get("flags"), dict) and section.get("flags"):
            extra["section_flags"] = section.get("flags")
        return _node(
            key,
            label,
            1,
            value=section.get("subtotal", subtotal_fallback),
            children=children,
            label_key=label_key,
            provenance=PROV_STRUCTURAL_CONTAINER,
            **extra,
        )

    opening = _node(
        "cf_opening_cash",
        "Opening cash",
        1,
        value=cashflow_raw.get("opening_cash"),
        children=[],
        label_key="stmt_hier_cf_opening_cash",
        provenance=PROV_DERIVED_METRIC,
    )

    operating = _cf_section(
        "cf_operating",
        "Operating activities",
        "stmt_hier_cf_operating",
        op,
        subtotal_fallback=cashflow_raw.get("operating_cashflow"),
    )

    if cashflow_raw.get("free_cashflow") is not None:
        operating["children"].append(
            _node(
                "cf_fcf",
                "Free cash flow (as reported)",
                2,
                value=cashflow_raw.get("free_cashflow"),
                label_key="stmt_hier_cf_fcf",
                provenance=PROV_DERIVED_METRIC,
            )
        )

    investing = _cf_section(
        "cf_investing",
        "Investing activities",
        "stmt_hier_cf_investing",
        inv,
    )

    financing = _cf_section(
        "cf_financing",
        "Financing activities",
        "stmt_hier_cf_financing",
        fin,
    )

    net_change = _node(
        "cf_net_change",
        "Net change in cash",
        1,
        value=cashflow_raw.get("net_change_in_cash"),
        children=[],
        label_key="stmt_hier_cf_net_change",
        provenance=PROV_DERIVED_METRIC,
    )

    ending = _node(
        "cf_ending_cash",
        "Ending cash",
        1,
        value=cashflow_raw.get("ending_cash", cashflow_raw.get("cash_balance")),
        children=[],
        label_key="stmt_hier_cf_ending_cash",
        provenance=PROV_DERIVED_METRIC,
    )

    return {
        "root": _node(
            "cashflow_statement",
            "Cash flow statement",
            0,
            value=None,
            children=[opening, operating, investing, financing, net_change, ending],
            label_key="stmt_hier_cashflow_root",
            reconciliation=cashflow_raw.get("reconciles"),
            statement_meta=stmt_meta,
            provenance=PROV_STRUCTURAL_CONTAINER,
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
