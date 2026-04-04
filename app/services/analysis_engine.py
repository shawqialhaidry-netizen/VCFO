"""
analysis_engine.py — Phase 5
Pure financial analysis engine.

Responsibilities:
  - Financial ratios (profitability, liquidity, leverage, efficiency)
  - Working capital
  - MoM / YoY trends

Design rules:
  - Pure functions only — zero DB, zero HTTP, zero side effects
  - Safe division — never raises ZeroDivisionError
  - Returns None explicitly when data is missing or insufficient
  - Does NOT interpret or generate recommendations (that is Phase 6)

Input:  dict produced by statements_to_dict() — one or multiple periods
Output: AnalysisResult dataclass → serialisable dict
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.structured_income_statement import build_structured_income_statement_bundle
from app.services.structured_income_statement_variance import (
    build_structured_income_statement_variance_bundle_from_window,
)
from app.services.structured_profit_bridge import (
    build_structured_profit_bridge_bundle_from_window,
)
from app.services.structured_profit_story import build_structured_profit_story_from_analysis


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Divide safely. Returns None if either operand is None or denominator is 0."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _pct(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Return percentage (0–100). Returns None on missing/zero data."""
    v = _safe_div(numerator, denominator)
    return round(v * 100, 2) if v is not None else None


def _round2(v: Optional[float]) -> Optional[float]:
    return round(v, 2) if v is not None else None


def _mom_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Month-over-month % change. Returns None if either value is missing or previous is 0."""
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


# ══════════════════════════════════════════════════════════════════════════════
#  Balance Sheet component extraction
#  Uses account code ranges — standard Arabic chart of accounts:
#    1000-1399 → current assets
#    1400+     → non-current / fixed assets
#    2000-2199 → current liabilities
#    2200+     → non-current liabilities
# ══════════════════════════════════════════════════════════════════════════════

def _extract_bs_components(bs: dict) -> dict:
    """
    Extract balance sheet components for ratio computation.

    ARCHITECTURE:
    Reads pre-computed current/non-current values from financial_statements.py
    when available (via statements_to_dict output). Falls back to account-code
    range scanning only for legacy data or when pre-computed values are absent.

    Granular sub-buckets (cash, receivables, inventory, payables) always use
    code-range scan as financial_statements.py does not split at that level.
    """
    def _code_range(items: list[dict], lo: int, hi: int) -> float:
        total = 0.0
        for item in items:
            code = str(item.get("account_code", "")).strip()
            try:
                num = int(code[:4]) if len(code) >= 4 else int(code)
            except (ValueError, TypeError):
                num = lo
            if lo <= num <= hi:
                total += abs(float(item.get("amount", 0) or 0))
        return total

    asset_items = bs.get("assets", {}).get("items", [])
    liab_items  = bs.get("liabilities", {}).get("items", [])

    # ── Use pre-computed values from statement_engine when available ──────────
    current_assets     = float(bs.get("current_assets",      0) or 0)
    noncurrent_assets  = float(bs.get("noncurrent_assets",   0) or 0)
    current_liabilities    = float(bs.get("current_liabilities",    0) or 0)
    noncurrent_liabilities = float(bs.get("noncurrent_liabilities", 0) or 0)



    # ── Granular sub-buckets — always from code-range scan ───────────────────
    inventory   = _code_range(asset_items, 1200, 1299)
    cash        = _code_range(asset_items, 1000, 1099)
    receivables = _code_range(asset_items, 1100, 1199)
    payables    = _code_range(liab_items,  2000, 2099)

    total_assets      = float(bs.get("assets",      {}).get("total", 0) or 0)
    total_liabilities = float(bs.get("liabilities", {}).get("total", 0) or 0)
    total_equity      = float(bs.get("equity",      {}).get("total", 0) or 0)

    return {
        "current_assets":         current_assets,
        "noncurrent_assets":      noncurrent_assets,
        "inventory":              inventory,
        "cash":                   cash,
        "receivables":            receivables,
        "current_liabilities":    current_liabilities,
        "noncurrent_liabilities": noncurrent_liabilities,
        "payables":               payables,
        "total_assets":           total_assets,
        "total_liabilities":      total_liabilities,
        "total_equity":           total_equity,
    }
def compute_ratios(stmt: dict, period: str = "") -> dict:
    """
    Compute all financial ratios for a single period's statement dict.

    ARCHITECTURE: reads values from statement_engine output ONLY.
    Does NOT recompute net_profit, gross_profit, or working_capital.
    Those are the exclusive responsibility of financial_statements.py.

    Input:  output of statements_to_dict() for one period
    Output: dict with ratios (all values float or None)
    """
    is_  = stmt.get("income_statement", {})
    bs   = stmt.get("balance_sheet", {})
    bsc  = _extract_bs_components(bs)

    # ── Read IS values from statement_engine (do NOT recompute) ──────────────
    revenue_raw = is_.get("revenue", {}).get("total")
    cogs_raw = is_.get("cogs", {}).get("total")
    expenses_raw = is_.get("expenses", {}).get("total")

    revenue = float(revenue_raw) if revenue_raw is not None else None
    cogs = float(cogs_raw) if cogs_raw is not None else None
    gross_profit     = float(is_.get("gross_profit",     0) or 0)
    operating_profit = float(is_.get("operating_profit", 0) or 0)
    net_profit       = float(is_.get("net_profit",       0) or 0)
    expenses = float(expenses_raw) if expenses_raw is not None else None

    # ── Read BS values — current/non-current from statement_engine ────────────
    ca_raw = bs.get("current_assets")
    cl_raw = bs.get("current_liabilities")

    ca = float(ca_raw) if ca_raw is not None else None
    cl = float(cl_raw) if cl_raw is not None else None

    inv = bsc["inventory"]
    cash = bsc["cash"]
    rec = bsc["receivables"]
    pay = bsc["payables"]
    ta = bsc["total_assets"]
    tl = bsc["total_liabilities"]
    eq = bsc["total_equity"]

    # ── Profitability — ratios only, values already from statement_engine ─────
    gross_margin     = is_.get("gross_margin_pct")
    net_margin       = is_.get("net_margin_pct")
    operating_margin = is_.get("operating_margin_pct")

    # EBITDA ≈ Operating Profit + Depreciation
    ebitda_margin = operating_margin

    # ── Liquidity ──────────────────────────────────────────────────────────────
    _ca_approx = bs.get("current_assets_approximated", False)
    _cl_approx = bs.get("current_liabilities_approximated", False)
    _liquidity_approximated = _ca_approx or _cl_approx

    if _liquidity_approximated:
        current_ratio = None
        quick_ratio = None
    else:
        current_ratio = _safe_div(ca, cl)
        quick_assets = (ca or 0) - (inv or 0)
        quick_ratio = _safe_div(quick_assets if (ca and cl) else None, cl)

    # ── Leverage ───────────────────────────────────────────────────────────────
    debt_to_equity = _safe_div(tl, eq) if (eq and eq > 0) else None

    # ── Period granularity detection ──────────────────────────────────────────
    _p = (period or stmt.get("period", "")).strip()
    if len(_p) == 4 and _p.isdigit():
        _days = 365
    elif "Q" in _p.upper():
        _days = 91
    else:
        _days = 30

    # ── Efficiency ────────────────────────────────────────────────────────────
    inv_turnover = _safe_div(cogs, inv)
    dio = _round2((_safe_div(inv, cogs) or 0) * _days) if (inv and cogs) else None
    dpo = _round2((_safe_div(pay, cogs) or 0) * _days) if (pay and cogs) else None
    dso = _round2((_safe_div(rec, revenue) or 0) * _days) if (rec and revenue) else None

    ccc: Optional[float] = None
    if dio is not None and dso is not None and dpo is not None:
        ccc = _round2(dio + dso - dpo)

    # ── Working Capital — READ from statement_engine, never recompute ─────────
    _wc_raw = bs.get("working_capital")
    working_capital = _round2(float(_wc_raw)) if _wc_raw is not None else None

    return {
        "profitability": {
            "gross_margin_pct": gross_margin,
            "net_margin_pct": net_margin,
            "operating_margin_pct": operating_margin,
            "ebitda_margin_pct": ebitda_margin,
            "gross_profit": _round2(gross_profit),
            "operating_profit": _round2(operating_profit),
            "net_profit": _round2(net_profit),
        },
        "liquidity": {
            "current_ratio": current_ratio,
            "quick_ratio": quick_ratio,
            "liquidity_approximated": _liquidity_approximated,
            "working_capital": working_capital,
            "current_assets": _round2(ca),
            "current_liabilities": _round2(cl),
        },
        "leverage": {
            "debt_to_equity": debt_to_equity,
            "total_liabilities": _round2(tl),
            "total_equity": _round2(eq),
        },
        "efficiency": {
            "inventory_turnover": inv_turnover,
            "dio_days": dio,
            "dso_days": dso,
            "dpo_days": dpo,
            "ccc_days": ccc,
            "inventory": _round2(inv),
            "receivables": _round2(rec),
            "payables": _round2(pay),
        },
    }
# ══════════════════════════════════════════════════════════════════════════════
#  Trend analysis — multiple periods
# ══════════════════════════════════════════════════════════════════════════════

def compute_trends(period_statements: list[dict]) -> dict:
    """
    Compute MoM trends across a list of period statement dicts.
    List must be sorted chronologically (oldest first).

    Returns:
      {
        "revenue_mom":         [null, +3.2, -1.5, ...],
        "net_profit_mom":      [...],
        "gross_margin_mom":    [...],
        "periods":             ["2025-01", "2025-02", ...],
        "revenue_series":      [...],
        "net_profit_series":   [...],
        "gross_margin_series": [...],
        "cogs_series":         [...],
        "expenses_series":     [...],
        "yoy_revenue_change":  float | null,
        "yoy_net_profit_change": float | null,
      }
    """
    if not period_statements:
        return {}

    def _is_nested_total(stmt: dict, *keys: str) -> Optional[float]:
        """Read income_statement.{section}.total; None if path missing (not 0)."""
        is_ = stmt.get("income_statement")
        if not isinstance(is_, dict):
            return None
        cur: Any = is_
        for k in keys:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        if cur is None:
            return None
        try:
            return float(cur)
        except (TypeError, ValueError):
            return None

    def _is_scalar(stmt: dict, key: str) -> Optional[float]:
        is_ = stmt.get("income_statement")
        if not isinstance(is_, dict):
            return None
        v = is_.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    periods         = [s.get("period", "") for s in period_statements]
    revenue_series  = [_is_nested_total(s, "revenue", "total") for s in period_statements]
    np_series       = [_is_scalar(s, "net_profit") for s in period_statements]
    gm_series       = [_is_scalar(s, "gross_margin_pct") for s in period_statements]
    cogs_series     = [_is_nested_total(s, "cogs", "total") for s in period_statements]
    exp_series      = [_is_nested_total(s, "expenses", "total") for s in period_statements]
    op_series       = [_is_scalar(s, "operating_profit") for s in period_statements]

    def _mom_series(series: list[Optional[float]]) -> list[Optional[float]]:
        result: list[Optional[float]] = [None]
        for i in range(1, len(series)):
            result.append(_mom_change(series[i], series[i - 1]))
        return result

    revenue_mom  = _mom_series(revenue_series)
    np_mom       = _mom_series(np_series)
    gm_mom       = _mom_series(gm_series)
    expenses_mom = _mom_series(exp_series)

    # YoY: compare last period to same period 12 months earlier
    yoy_revenue     = None
    yoy_net_profit  = None
    if len(revenue_series) >= 13:
        yoy_revenue    = _mom_change(revenue_series[-1], revenue_series[-13])
        yoy_net_profit = _mom_change(np_series[-1], np_series[-13])

    # Consecutive decline detection
    rev_decline_streak   = _consecutive_decline(revenue_series)
    np_decline_streak    = _consecutive_decline(np_series)

    def _ser_round(series: list[Optional[float]]) -> list[Optional[float]]:
        return [_round2(v) if v is not None else None for v in series]

    return {
        "periods":                periods,
        "revenue_series":         _ser_round(revenue_series),
        "net_profit_series":      _ser_round(np_series),
        "gross_margin_series":    _ser_round(gm_series),
        "cogs_series":            _ser_round(cogs_series),
        "expenses_series":        _ser_round(exp_series),
        "operating_profit_series":_ser_round(op_series),
        "revenue_mom_pct":        revenue_mom,
        "net_profit_mom_pct":     np_mom,
        "gross_margin_mom_pct":   gm_mom,
        "expenses_mom_pct":       expenses_mom,
        "yoy_revenue_pct":        yoy_revenue,
        "yoy_net_profit_pct":     yoy_net_profit,
        "revenue_decline_streak": rev_decline_streak,
        "net_profit_decline_streak": np_decline_streak,
    }


def _trend_direction(mom_series: list) -> str:
    """
    Derive trend direction from a MoM percentage series.
    Ignores null values. Evaluates only the latest 2 valid (non-null) points.

    Returns:
      'improving'  — last 2+ valid MoM values are positive
      'declining'  — last 2+ valid MoM values are negative
      'stable'     — mixed, flat (abs < 0.5%), or fewer than 2 valid points
    """
    valid = [x for x in (mom_series or []) if x is not None]
    if len(valid) < 2:
        return "stable"
    last_two = valid[-2:]
    if all(v > 0.5 for v in last_two):
        return "improving"
    if all(v < -0.5 for v in last_two):
        return "declining"
    return "stable"


def _consecutive_decline(series: list[Optional[float]]) -> int:
    """Return how many consecutive periods (from the end) show decline (levels)."""
    streak = 0
    for i in range(len(series) - 1, 0, -1):
        a, b = series[i], series[i - 1]
        if a is None or b is None:
            break
        if a < b:
            streak += 1
        else:
            break
    return streak


# ══════════════════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis(
    period_statements: list[dict],
) -> dict:
    """
    Run full Phase 5 analysis over a list of period statements.

    Input:  list of dicts — each from statements_to_dict(), sorted oldest→newest
    Output: {
              "ratios":     {period: {...}},   — per-period ratios
              "latest":     {...},             — ratios for most recent period
              "trends":     {...},             — MoM / YoY trends
              "period_count": int,
              "periods":    [str],
            }
    """
    if not period_statements:
        _empty = build_structured_income_statement_bundle({})
        _var_empty = build_structured_income_statement_variance_bundle_from_window([])
        _bridge_empty = build_structured_profit_bridge_bundle_from_window([])
        _story_stub = {**_bridge_empty, **_var_empty, "latest": None}
        return {
            "ratios": {},
            "latest": None,
            "trends": {},
            "period_count": 0,
            "periods": [],
            "structured_income_statement": _empty["structured_income_statement"],
            "structured_income_statement_meta": _empty["structured_income_statement_meta"],
            **_var_empty,
            **_bridge_empty,
            "structured_profit_story": build_structured_profit_story_from_analysis(_story_stub),
        }

    ratios_by_period: dict[str, dict] = {}
    for stmt in period_statements:
        period = stmt.get("period", "unknown")
        ratios_by_period[period] = compute_ratios(stmt, period)

    trends = compute_trends(period_statements)

    latest_stmt = period_statements[-1]
    latest_period = latest_stmt.get("period", "unknown")
    latest_ratios = ratios_by_period.get(latest_period)

    if latest_ratios is None and ratios_by_period:
        latest_ratios = list(ratios_by_period.values())[-1]

    _sis = build_structured_income_statement_bundle(latest_stmt)
    _var = build_structured_income_statement_variance_bundle_from_window(period_statements)
    _bridge = build_structured_profit_bridge_bundle_from_window(period_statements)

    out = {
        "period_count": len(period_statements),
        "periods": [s.get("period", "") for s in period_statements],
        "latest": latest_ratios,
        "ratios": ratios_by_period,
        "trends": trends,
        "structured_income_statement": _sis["structured_income_statement"],
        "structured_income_statement_meta": _sis["structured_income_statement_meta"],
        **_var,
        **_bridge,
    }
    out["structured_profit_story"] = build_structured_profit_story_from_analysis(out)
    return out
