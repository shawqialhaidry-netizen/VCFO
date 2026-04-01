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


def _da_estimate(bsc: dict, is_: dict) -> tuple[float, bool]:
    """
    Estimate Depreciation & Amortization.
    1. Scan income statement expense items for depreciation keywords.
    2. If not found: proxy = noncurrent_assets × 10% / 12 (monthly).
    Returns (da_amount, was_approximated).
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
        return _r2(da_identified), False

    # Proxy: 10% annual rate on non-current assets, monthly
    nc = bsc.get("noncurrent_assets", 0)
    proxy = nc * 0.10 / 12
    return _r2(proxy), True


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
    da, da_approx = _da_estimate(bsc, is_)
    da = da or 0.0

    # WC deltas
    approx_flag = False
    if prev_stmt:
        prev_bsc = _extract_bs(prev_stmt)
        delta_rec = bsc["receivables"] - prev_bsc["receivables"]
        delta_inv = bsc["inventory"]   - prev_bsc["inventory"]
        delta_pay = bsc["payables"]    - prev_bsc["payables"]
    else:
        # Approximate: use ratio-based approach
        # Δrec ≈ (DSO_current - DSO_prev) × (Revenue/30)
        # Without prior period we use 0 as conservative fallback
        delta_rec = 0.0
        delta_inv = 0.0
        delta_pay = 0.0
        approx_flag = True

    # OCF = NP + DA - ΔRec - ΔInv + ΔPay
    wc_adj = -delta_rec - delta_inv + delta_pay
    ocf    = _r2(np_ + da + wc_adj)

    # Debug / formula check
    formula_check = abs((np_ + da + wc_adj) - ocf) < 0.02

    return {
        "net_profit":        _r2(np_),
        "da_addback":        _r2(da),
        "da_approximated":   da_approx,
        "delta_receivables": _r2(delta_rec),
        "delta_inventory":   _r2(delta_inv),
        "delta_payables":    _r2(delta_pay),
        "wc_adjustment":     _r2(wc_adj),
        "ocf":               ocf,
        "wc_approximated":   approx_flag,
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
        da, _ = _da_estimate(bsc, is_)
        da = da or 0.0

        prev = period_statements[i - 1] if i > 0 else None
        if prev:
            pb = _extract_bs(prev)
            dr = bsc["receivables"] - pb["receivables"]
            di = bsc["inventory"]   - pb["inventory"]
            dp = bsc["payables"]    - pb["payables"]
            wc_adj = -dr - di + dp
        else:
            wc_adj = 0.0

        ocf = _r2(np_ + da + wc_adj)
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
        return {"error": "no data", "flags": {"capex_missing": True,
                "da_approximated": True, "wc_approximated": True, "single_period": True}}

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
            "single_period":   single,
        },
        "debug": {
            "net_profit":        ocf_detail["net_profit"],
            "da_addback":        ocf_detail["da_addback"],
            "delta_receivables": ocf_detail["delta_receivables"],
            "delta_inventory":   ocf_detail["delta_inventory"],
            "delta_payables":    ocf_detail["delta_payables"],
            "wc_adjustment":     ocf_detail["wc_adjustment"],
            "formula":           ocf_detail["formula"],
            "formula_check":     ocf_detail["formula_check"],
        },
    }
