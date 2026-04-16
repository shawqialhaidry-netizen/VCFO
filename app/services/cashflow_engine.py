"""
cashflow_engine.py — Phase 9
Cash Flow Engine — CFO-level cash intelligence.

Operates ONLY on outputs from run_analysis() + period_statements.
Does NOT touch financial_engine, financial_statements, or DB.

Formula chain:
  OCF  = Net Profit + DA (non-cash) - ΔReceivables - ΔInventory + ΔPayables
  FCF  = OCF - CAPEX  (null if CAPEX unavailable)
  Burn = abs(NP) if NP < 0 else 0
  Runway = Cash / Burn if Burn > 0 else null

Working capital deltas are computed from period-to-period BS balance changes.
When only a single period exists, WC deltas are approximated from days ratios.

Output:
{
  "period":                 str,
  "operating_cashflow":     float,
  "free_cashflow":          float | null,
  "burn_rate":              float,
  "runway_months":          float | null,
  "working_capital_change": { receivables, inventory, payables, net },
  "da_estimate":            float,
  "quality": {
    "profit_vs_cash_gap":      float,
    "cash_conversion_ratio":   float | null,
    "cash_conversion_quality": "strong" | "moderate" | "weak",
  },
  "series": {
    "periods":            [str],
    "operating_cashflow": [float],
    "net_profit":         [float],
    "cash_balance":       [float | null],
  },
  "flags": {
    "capex_missing":   bool,
    "da_approximated": bool,
    "wc_approximated": bool,
    "single_period":   bool,
  },
  "debug": {
    "net_profit":        float,
    "da_addback":        float,
    "delta_receivables": float,
    "delta_inventory":   float,
    "delta_payables":    float,
    "wc_adjustment":     float,
    "formula":           str,
    "formula_check":     bool,
  }
}
"""
from __future__ import annotations

import math
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _r2(v) -> Optional[float]:
    return round(float(v), 2) if v is not None else None


def _div(a, b) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return round(a / b, 4)


def _get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
        if cur is None:
            return default
    return cur


def _extract_bs(stmt: dict) -> dict:
    """
    Extract balance sheet components from a single period statement.

    ARCHITECTURE: Reads granular sub-buckets (cash, receivables, inventory,
    payables) via account-code range scan. Does NOT recompute working_capital
    — that is the exclusive responsibility of financial_statements.py and is
    read directly from bs["working_capital"] wherever needed.
    """
    bs = stmt.get("balance_sheet", {})
    asset_items = _get(bs, "assets",      "items") or []
    liab_items  = _get(bs, "liabilities", "items") or []

    def _rng(items, lo, hi):
        total = 0.0
        for item in items:
            code = str(item.get("account_code", "")).strip()
            try:
                num = int(code[:4]) if len(code) >= 4 else int(code)
            except (ValueError, TypeError):
                num = -1
            if lo <= num <= hi:
                total += abs(float(item.get("amount", 0) or 0))
        return total

    return {
        "cash":             _rng(asset_items, 1000, 1099),
        "receivables":      _rng(asset_items, 1100, 1199),
        "inventory":        _rng(asset_items, 1200, 1299),
        "payables":         _rng(liab_items,  2000, 2099),
        "noncurrent_assets": _rng(asset_items, 1400, 1999),
    }


def _sum_keyword_items(items: list[dict], keywords: list[str]) -> float:
    total = 0.0
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("account_name", "")).lower()
        code = str(item.get("account_code", "")).lower()
        if any(kw in name or kw in code for kw in keywords):
            total += abs(float(item.get("amount", 0) or 0))
    return total


def _extract_financing_components(stmt: Optional[dict]) -> dict:
    if not stmt:
        return {
            "debt": 0.0,
            "equity_contrib": 0.0,
            "equity_distribution": 0.0,
        }

    bs = stmt.get("balance_sheet", {})
    liab_items = _get(bs, "liabilities", "items") or []
    eq_items = _get(bs, "equity", "items") or []

    debt_keywords = [
        "loan", "loans", "borrowing", "borrowings", "debt", "debenture",
        "note payable", "notes payable", "overdraft", "lease liability",
        "murabaha", "finance lease", "credit facility",
    ]
    equity_contrib_keywords = [
        "share capital", "paid in capital", "paid-in capital", "capital contribution",
        "owner capital", "owner's capital", "partners capital", "partner capital",
        "common stock", "ordinary share capital",
    ]
    equity_distribution_keywords = [
        "dividend", "dividends", "distribution", "distributions",
        "drawing", "drawings", "owner withdrawal", "withdrawal",
    ]

    return {
        "debt": _sum_keyword_items(liab_items, debt_keywords),
        "equity_contrib": _sum_keyword_items(eq_items, equity_contrib_keywords),
        "equity_distribution": _sum_keyword_items(eq_items, equity_distribution_keywords),
    }


def _da_estimate(bsc: dict, is_: dict) -> tuple[float, bool, str]:
    """
    Estimate Depreciation & Amortization.
    1. Scan income statement expense items for depreciation keywords.
    2. If not found: proxy = noncurrent_assets × 10% / 12 (monthly).
    Returns (da_amount, was_approximated, source).
    """
    exp_items = _get(is_, "expenses", "items") or []
    da_keywords = ["depreciation", "amortization", "استهلاك", "إهلاك",
                   "amortisman", "amortiasyon", "deprec"]
    da_identified = 0.0
    for item in exp_items:
        name = str(item.get("account_name", "")).lower()
        if any(kw in name for kw in da_keywords):
            da_identified += abs(float(item.get("amount", 0) or 0))

    if da_identified > 0:
        return _r2(da_identified), False, "explicit_expense_lines"

    # Proxy: 10% annual rate on non-current assets, monthly
    nc = bsc.get("noncurrent_assets", 0)
    proxy = nc * 0.10 / 12
    return _r2(proxy), True, "noncurrent_assets_proxy"


# ══════════════════════════════════════════════════════════════════════════════
#  Single-period OCF
# ══════════════════════════════════════════════════════════════════════════════

def _compute_ocf_single(
    stmt:       dict,
    prev_stmt:  Optional[dict],
    latest_ratios: dict,
) -> dict:
    """
    Compute OCF for a single period.
    If prev_stmt available: use actual WC deltas.
    Else: approximate WC changes from days ratios.
    """
    is_  = stmt.get("income_statement", {})
    bsc  = _extract_bs(stmt)

    np_  = float(_get(is_, "net_profit") or 0)
    rev  = float(_get(is_, "revenue", "total") or 0)
    cogs = float(_get(is_, "cogs",    "total") or 0)

    # D&A
    da, da_approx, da_source = _da_estimate(bsc, is_)
    da = da or 0.0

    # WC deltas
    wc_unavailable = False
    if prev_stmt:
        prev_bsc = _extract_bs(prev_stmt)
        delta_rec = bsc["receivables"] - prev_bsc["receivables"]
        delta_inv = bsc["inventory"]   - prev_bsc["inventory"]
        delta_pay = bsc["payables"]    - prev_bsc["payables"]
        wc_adj = -delta_rec - delta_inv + delta_pay
        ocf = _r2(np_ + da + wc_adj)
        ocf_basis = "net_profit_plus_da_plus_working_capital"
    else:
        # Without prior-period balances, WC movement is unavailable.
        # Keep OCF present for compatibility, but mark it as partial:
        # OCF_partial = NP + DA only (no WC adjustment).
        delta_rec = None
        delta_inv = None
        delta_pay = None
        wc_adj = None
        wc_unavailable = True
        ocf = _r2(np_ + da)
        ocf_basis = "net_profit_plus_da_only"

    # Debug / formula check
    formula_check = abs((np_ + da + (wc_adj or 0.0)) - ocf) < 0.02

    return {
        "net_profit":        _r2(np_),
        "da_addback":        _r2(da),
        "da_approximated":   da_approx,
        "da_source":         da_source,
        "delta_receivables": _r2(delta_rec),
        "delta_inventory":   _r2(delta_inv),
        "delta_payables":    _r2(delta_pay),
        "wc_adjustment":     _r2(wc_adj),
        "ocf":               ocf,
        "wc_approximated":   False,
        "wc_unavailable":    wc_unavailable,
        "ocf_partial":       wc_unavailable,
        "ocf_basis":         ocf_basis,
        "cash":              _r2(bsc["cash"]),
        "formula":           "OCF = NP + DA - ΔReceivables - ΔInventory + ΔPayables",
        "formula_check":     formula_check,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Cash quality
# ══════════════════════════════════════════════════════════════════════════════

def _cash_quality(net_profit: float, ocf: float) -> dict:
    """
    Classify how well profit converts to cash.
    Strong:   OCF >= NP * 0.9  (cash matches or exceeds profit)
    Moderate: OCF >= NP * 0.5
    Weak:     OCF < NP * 0.5   (profit not converting to cash)
    """
    gap   = _r2(net_profit - ocf)
    ratio = _div(ocf, net_profit) if net_profit != 0 else None

    if ratio is None:
        quality = "indeterminate"
    elif ratio >= 0.9:
        quality = "strong"
    elif ratio >= 0.5:
        quality = "moderate"
    else:
        quality = "weak"

    return {
        "profit_vs_cash_gap":      gap,
        "cash_conversion_ratio":   _r2(ratio),
        "cash_conversion_quality": quality,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Burn rate & runway
# ══════════════════════════════════════════════════════════════════════════════

def _burn_runway(net_profit: float, cash: Optional[float]) -> tuple[float, Optional[float]]:
    burn = _r2(abs(net_profit)) if net_profit < 0 else 0.0
    runway = None
    if burn and burn > 0 and cash and cash > 0:
        runway = _r2(cash / burn)
    return burn, runway


# ══════════════════════════════════════════════════════════════════════════════
#  Series builder — multi-period cashflow
# ══════════════════════════════════════════════════════════════════════════════

def _build_cashflow_series(period_statements: list[dict]) -> dict:
    """
    Compute OCF for every period in sequence.
    Returns parallel arrays for charting.
    """
    periods_out     = []
    ocf_series      = []
    np_series       = []
    cash_series     = []
    wc_adj_series   = []

    for i, stmt in enumerate(period_statements):
        p    = stmt.get("period", "")
        is_  = stmt.get("income_statement", {})
        bsc  = _extract_bs(stmt)
        np_  = float(_get(is_, "net_profit") or 0)
        da, _, _ = _da_estimate(bsc, is_)
        da = da or 0.0

        prev = period_statements[i - 1] if i > 0 else None
        if prev:
            pb = _extract_bs(prev)
            dr = bsc["receivables"] - pb["receivables"]
            di = bsc["inventory"]   - pb["inventory"]
            dp = bsc["payables"]    - pb["payables"]
            wc_adj = -dr - di + dp
        else:
            wc_adj = None

        ocf = _r2(np_ + da + (wc_adj or 0.0))
        periods_out.append(p)
        ocf_series.append(ocf)
        np_series.append(_r2(np_))
        cash_series.append(_r2(bsc["cash"]) if bsc["cash"] else None)
        wc_adj_series.append(_r2(wc_adj))

    return {
        "periods":            periods_out,
        "operating_cashflow": ocf_series,
        "net_profit":         np_series,
        "cash_balance":       cash_series,
        "wc_adjustment":      wc_adj_series,
    }


def _build_operating_section(ocf_detail: dict) -> dict:
    """
    Build a structured indirect operating cash flow section using the
    currently implemented OCF derivation chain.
    """
    lines = [
        {"id": "net_profit", "label": "net_profit", "amount": ocf_detail["net_profit"]},
        {"id": "da_addback", "label": "depreciation_amortization", "amount": ocf_detail["da_addback"]},
        {
            "id": "delta_receivables",
            "label": "change_in_receivables",
            "amount": None if ocf_detail.get("delta_receivables") is None else _r2(-float(ocf_detail["delta_receivables"])),
        },
        {
            "id": "delta_inventory",
            "label": "change_in_inventory",
            "amount": None if ocf_detail.get("delta_inventory") is None else _r2(-float(ocf_detail["delta_inventory"])),
        },
        {
            "id": "delta_payables",
            "label": "change_in_payables",
            "amount": None if ocf_detail.get("delta_payables") is None else _r2(float(ocf_detail["delta_payables"])),
        },
    ]
    return {
        "method": "indirect",
        "lines": lines,
        "subtotal": ocf_detail["ocf"],
        "flags": {
            "da_approximated": bool(ocf_detail.get("da_approximated")),
            "wc_approximated": bool(ocf_detail.get("wc_approximated")),
            "wc_unavailable": bool(ocf_detail.get("wc_unavailable")),
            "ocf_partial": bool(ocf_detail.get("ocf_partial")),
        },
        "note": "working_capital_unavailable" if ocf_detail.get("wc_unavailable") else None,
    }


def _build_investing_section(
    latest_stmt: dict,
    prev_stmt: Optional[dict],
    da_addback: Optional[float],
) -> dict:
    if not prev_stmt:
        return _empty_section("investing", "opening_balance_unavailable")

    latest_bs = _extract_bs(latest_stmt)
    prev_bs = _extract_bs(prev_stmt)
    da = float(da_addback or 0.0)
    delta_nca = float(latest_bs["noncurrent_assets"] - prev_bs["noncurrent_assets"])

    gross_capex_est = max(delta_nca + da, 0.0)
    disposal_est = max(-(delta_nca + da), 0.0)

    lines = []
    if gross_capex_est > 0.005:
        lines.append({
            "id": "capital_expenditure_estimated",
            "label": "capital_expenditure_estimated",
            "amount": _r2(-gross_capex_est),
        })
    if disposal_est > 0.005:
        lines.append({
            "id": "asset_disposals_estimated",
            "label": "asset_disposals_estimated",
            "amount": _r2(disposal_est),
        })

    subtotal = _r2(sum(float(x["amount"] or 0) for x in lines)) if lines else 0.0
    return {
        "id": "investing",
        "lines": lines,
        "subtotal": subtotal,
        "available": True,
        "reason": None,
        "flags": {
            "capex_estimated_from_nca_and_da": True,
            "asset_disposals_estimated": disposal_est > 0.005,
            "other_investing_unavailable": True,
        },
    }


def _build_financing_section(
    latest_stmt: dict,
    prev_stmt: Optional[dict],
) -> dict:
    if not prev_stmt:
        return _empty_section("financing", "opening_balance_unavailable")

    latest = _extract_financing_components(latest_stmt)
    prev = _extract_financing_components(prev_stmt)

    debt_delta = float(latest["debt"] - prev["debt"])
    contrib_delta = float(latest["equity_contrib"] - prev["equity_contrib"])
    dist_delta = float(latest["equity_distribution"] - prev["equity_distribution"])

    lines = []
    if debt_delta > 0.005:
        lines.append({
            "id": "debt_increase",
            "label": "debt_increase",
            "amount": _r2(debt_delta),
        })
    elif debt_delta < -0.005:
        lines.append({
            "id": "debt_repayment",
            "label": "debt_repayment",
            "amount": _r2(debt_delta),
        })

    if contrib_delta > 0.005:
        lines.append({
            "id": "equity_injection_estimated",
            "label": "equity_injection_estimated",
            "amount": _r2(contrib_delta),
        })
    elif contrib_delta < -0.005:
        lines.append({
            "id": "equity_reduction_estimated",
            "label": "equity_reduction_estimated",
            "amount": _r2(contrib_delta),
        })

    if dist_delta > 0.005:
        lines.append({
            "id": "owner_distributions_estimated",
            "label": "owner_distributions_estimated",
            "amount": _r2(-dist_delta),
        })

    if not lines and latest["debt"] <= 0.005 and latest["equity_contrib"] <= 0.005 and latest["equity_distribution"] <= 0.005:
        return _empty_section("financing", "no_classifiable_financing_accounts")

    subtotal = _r2(sum(float(x["amount"] or 0) for x in lines)) if lines else 0.0
    return {
        "id": "financing",
        "lines": lines,
        "subtotal": subtotal,
        "available": True,
        "reason": None,
        "flags": {
            "debt_derived_from_explicit_accounts": True,
            "equity_flows_estimated_from_explicit_accounts": bool(
                abs(contrib_delta) > 0.005 or dist_delta > 0.005
            ),
            "other_financing_unavailable": True,
        },
    }


def _empty_section(section_id: str, reason: str) -> dict:
    return {
        "id": section_id,
        "lines": [],
        "subtotal": None,
        "available": False,
        "reason": reason,
    }


def _reconcile_cash_movement(
    opening_cash: Optional[float],
    net_change_in_cash: Optional[float],
    ending_cash: Optional[float],
    tolerance: float = 0.02,
) -> tuple[Optional[bool], Optional[float]]:
    if opening_cash is None or net_change_in_cash is None or ending_cash is None:
        return None, None
    expected_ending = _r2(opening_cash + net_change_in_cash)
    delta = _r2((ending_cash or 0) - (expected_ending or 0))
    return abs(delta or 0) <= tolerance, delta


# ══════════════════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def build_cashflow(
    period_statements: list[dict],
    capex: Optional[float] = None,
) -> dict:
    """
    Phase 9 Cash Flow Engine.

    Input:
      period_statements — list of statement dicts (same as analysis pipeline)
      capex             — optional capital expenditure for FCF calculation

    Output: complete cashflow dict (see module docstring)
    """
    if not period_statements:
        return {
            "error": "no data",
            "opening_cash": None,
            "operating": _empty_section("operating", "no_data"),
            "investing": _empty_section("investing", "not_modeled"),
            "financing": _empty_section("financing", "not_modeled"),
            "net_change_in_cash": None,
            "ending_cash": None,
            "reconciles": None,
            "statement_meta": {
                "method": "indirect_partial_foundation",
                "reconciliation_tolerance": 0.02,
                "statement_foundation_available": False,
            },
            "flags": {
                "capex_missing": True,
                "da_approximated": True,
                "wc_approximated": False,
                "wc_unavailable": True,
                "single_period": True,
                "operating_partial": True,
                "investing_partial": True,
                "financing_partial": True,
                "reconciliation_unavailable": True,
            },
        }

    latest_stmt  = period_statements[-1]
    prev_stmt    = period_statements[-2] if len(period_statements) >= 2 else None
    single       = prev_stmt is None

    is_  = latest_stmt.get("income_statement", {})
    bsc  = _extract_bs(latest_stmt)

    np_  = float(_get(is_, "net_profit") or 0)

    # ── OCF for latest period ─────────────────────────────────────────────────
    ocf_detail = _compute_ocf_single(latest_stmt, prev_stmt, {})
    ocf = ocf_detail["ocf"]
    da  = ocf_detail["da_addback"]

    # ── FCF ───────────────────────────────────────────────────────────────────
    fcf          = _r2(ocf - capex) if capex is not None else None
    capex_missing = capex is None

    # ── Burn & Runway ─────────────────────────────────────────────────────────
    cash   = ocf_detail["cash"]
    burn, runway = _burn_runway(np_, cash)
    opening_cash = _r2(_extract_bs(prev_stmt)["cash"]) if prev_stmt else None
    ending_cash = cash

    operating_section = _build_operating_section(ocf_detail)
    investing_section = _build_investing_section(latest_stmt, prev_stmt, da)
    financing_section = _build_financing_section(latest_stmt, prev_stmt)

    investing_subtotal = investing_section.get("subtotal")
    financing_subtotal = financing_section.get("subtotal")
    derived_net_change = None
    if ocf is not None and investing_subtotal is not None and financing_subtotal is not None:
        derived_net_change = _r2(float(ocf) + float(investing_subtotal) + float(financing_subtotal))

    net_change_in_cash = _r2(ending_cash - opening_cash) if opening_cash is not None and ending_cash is not None else None
    reconciles, reconciliation_delta = _reconcile_cash_movement(
        opening_cash,
        derived_net_change if derived_net_change is not None else net_change_in_cash,
        ending_cash,
    )

    # ── Working capital change summary ────────────────────────────────────────
    wc_change = {
        "receivables": ocf_detail["delta_receivables"],
        "inventory":   ocf_detail["delta_inventory"],
        "payables":    ocf_detail["delta_payables"],
        "net":         ocf_detail["wc_adjustment"],
    }

    # ── Quality ───────────────────────────────────────────────────────────────
    quality = _cash_quality(np_, ocf)

    # ── Multi-period series (for charts) ─────────────────────────────────────
    series = _build_cashflow_series(period_statements)

    # ── MoM OCF change ───────────────────────────────────────────────────────
    ocf_mom = None
    if len(series["operating_cashflow"]) >= 2:
        prev_ocf = series["operating_cashflow"][-2]
        if prev_ocf and prev_ocf != 0:
            ocf_mom = _r2((ocf - prev_ocf) / abs(prev_ocf) * 100)

    return {
        "period":                 latest_stmt.get("period", ""),
        "opening_cash":           opening_cash,
        "operating":              operating_section,
        "investing":              investing_section,
        "financing":              financing_section,
        "net_change_in_cash":     net_change_in_cash,
        "ending_cash":            ending_cash,
        "reconciles":             reconciles,
        "operating_cashflow":     ocf,
        "operating_cashflow_mom": ocf_mom,
        "free_cashflow":          fcf,
        "cash_balance":           cash,
        "burn_rate":              burn,
        "runway_months":          runway,
        "da_estimate":            da,
        "working_capital_change": wc_change,
        "quality":                quality,
        "series":                 series,
        "flags": {
            "capex_missing":   capex_missing,
            "da_approximated": ocf_detail["da_approximated"],
            "wc_approximated": ocf_detail["wc_approximated"],
            "wc_unavailable":  ocf_detail["wc_unavailable"],
            "single_period":   single,
            "operating_partial": ocf_detail["ocf_partial"],
            "investing_partial": bool(investing_section.get("flags", {}).get("other_investing_unavailable", False)),
            "financing_partial": bool(financing_section.get("flags", {}).get("other_financing_unavailable", False)),
            "reconciliation_unavailable": reconciles is None,
        },
        "statement_meta": {
            "method": "indirect_partial_foundation",
            "operating_method": "indirect",
            "investing_modeled": bool(investing_section.get("available")),
            "financing_modeled": bool(financing_section.get("available")),
            "da_source": ocf_detail["da_source"],
            "working_capital_basis": "actual_period_deltas" if not ocf_detail["wc_unavailable"] else "unavailable_no_prior_period",
            "operating_cashflow_basis": ocf_detail["ocf_basis"],
            "reconciliation_tolerance": 0.02,
            "reconciliation_delta": reconciliation_delta,
            "derived_net_change_in_cash": derived_net_change,
            "statement_foundation_available": True,
        },
        "debug": {
            "net_profit":        ocf_detail["net_profit"],
            "da_addback":        ocf_detail["da_addback"],
            "delta_receivables": ocf_detail["delta_receivables"],
            "delta_inventory":   ocf_detail["delta_inventory"],
            "delta_payables":    ocf_detail["delta_payables"],
            "wc_adjustment":     ocf_detail["wc_adjustment"],
            "wc_unavailable":    ocf_detail["wc_unavailable"],
            "ocf_basis":         ocf_detail["ocf_basis"],
            "da_source":         ocf_detail["da_source"],
            "formula":           ocf_detail["formula"],
            "formula_check":     ocf_detail["formula_check"],
        },
    }
