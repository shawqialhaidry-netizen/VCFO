"""
financial_engine.py — Internal Validation Helper
ARCHITECTURE ROLE: Internal helper used ONLY by financial_statements.py
for accounting-identity validation.

This module does NOT serve as a pipeline entry point.
It is NOT called directly by any API endpoint or service layer.

The single source of truth for all financial values is:
  financial_statements.py → build_statements() → statements_to_dict()

This module provides:
  - build_financials()        — low-level accounting identity validator
  - build_financials_by_period() — batch validator (used in tests/debug only)
  - financials_to_dict()      — serialiser for debug output

Formula (for validation):
  revenue      = sum of (credit - debit) for mapped_type == 'revenue'
  cogs         = sum of (debit - credit) for mapped_type == 'cogs'
  gross_profit = revenue - cogs
  opex         = sum of (debit - credit) for mapped_type == 'expenses'
                 + net debit of mapped_type == 'other' (non-zero net debits)
  tax          = sum of (debit - credit) for mapped_type == 'tax'
  net_profit   = revenue - cogs - opex - tax

  check        = abs(revenue - cogs - opex - tax - net_profit) < 0.01

DO NOT import this module from any service except financial_statements.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union
import math

# ── Pandas is optional at import time so unit tests run without it ─────────────
try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

# ── Type constants (must match account_rules.py) ──────────────────────────────
_REVENUE     = "revenue"
_COGS        = "cogs"
_EXPENSES    = "expenses"
_TAX         = "tax"
_ASSETS      = "assets"
_LIABILITIES = "liabilities"
_EQUITY      = "equity"
_OTHER       = "other"

_TOLERANCE = 0.02   # floating-point rounding tolerance (2 cents)


# ══════════════════════════════════════════════════════════════════════════════
#  Result dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FinancialResult:
    # ── Income Statement ──────────────────────────────────────────────────────
    revenue:          float = 0.0
    cogs:             float = 0.0
    gross_profit:     float = 0.0
    gross_margin_pct: Optional[float] = None

    opex:             float = 0.0    # operating expenses (excl COGS)
    operating_profit: float = 0.0
    operating_margin_pct: Optional[float] = None

    tax:              float = 0.0
    net_profit:       float = 0.0
    net_margin_pct:   Optional[float] = None

    # ── Derived totals used in dashboard ─────────────────────────────────────
    # expenses = cogs + opex (total cost base, used in "Revenue vs Expenses" chart)
    total_cost_base:  float = 0.0   # cogs + opex + tax  (everything that reduces revenue)
    expenses_for_chart: float = 0.0  # cogs + opex  (used in Revenue vs Expenses overlay)

    # ── Debug / validation block ──────────────────────────────────────────────
    check:   bool  = False
    diff:    float = 0.0
    period:  str   = ""
    error:   Optional[str] = None

    # ── Raw component sums (for transparency) ─────────────────────────────────
    raw_revenue_credit:  float = 0.0
    raw_revenue_debit:   float = 0.0
    raw_cogs_debit:      float = 0.0
    raw_opex_debit:      float = 0.0
    raw_other_net_debit: float = 0.0
    raw_tax_debit:       float = 0.0
    row_count:           int   = 0


# ══════════════════════════════════════════════════════════════════════════════
#  Core function
# ══════════════════════════════════════════════════════════════════════════════

def build_financials(
    rows,            # pd.DataFrame  OR  list[dict]
    period: str = "",
) -> FinancialResult:
    """
    Compute all financial figures from a set of classified TB rows.

    Parameters
    ----------
    rows   : pd.DataFrame or list[dict]
             Must have: mapped_type (str), debit (float), credit (float)
    period : str  optional label e.g. "2025-01"

    Returns
    -------
    FinancialResult with check=True if the accounting identity holds.
    """
    r = FinancialResult(period=period)

    if rows is None:
        r.error = "rows is None"
        return r

    # ── Normalise to list[dict] ───────────────────────────────────────────────
    if _HAS_PANDAS and isinstance(rows, pd.DataFrame):
        if rows.empty:
            r.error = "empty DataFrame"
            return r
        row_list = rows.to_dict(orient="records")
    else:
        row_list = list(rows)

    if not row_list:
        r.error = "no rows"
        return r

    r.row_count = len(row_list)

    # ── Accumulate by type ────────────────────────────────────────────────────
    rev_credit = rev_debit = 0.0
    cogs_d = cogs_c = 0.0
    opex_d = opex_c = 0.0
    tax_d  = tax_c  = 0.0
    other_d = other_c = 0.0

    for row in row_list:
        mtype  = str(row.get("mapped_type", "")).strip().lower()
        debit  = float(row.get("debit",  0) or 0)
        credit = float(row.get("credit", 0) or 0)

        if mtype == _REVENUE:
            rev_credit += credit
            rev_debit  += debit
        elif mtype == _COGS:
            cogs_d += debit
            cogs_c += credit
        elif mtype == _EXPENSES:
            opex_d += debit
            opex_c += credit
        elif mtype == _TAX:
            tax_d += debit
            tax_c += credit
        elif mtype == _OTHER:
            other_d += debit
            other_c += credit
        # assets / liabilities / equity → balance sheet only, not IS

    # ── Raw sums ──────────────────────────────────────────────────────────────
    r.raw_revenue_credit  = _r2(rev_credit)
    r.raw_revenue_debit   = _r2(rev_debit)
    r.raw_cogs_debit      = _r2(cogs_d)
    r.raw_opex_debit      = _r2(opex_d)
    r.raw_tax_debit       = _r2(tax_d)

    # ── Income Statement computation ──────────────────────────────────────────
    # Revenue: credit-normal (net of any debits)
    r.revenue = _r2(rev_credit - rev_debit)

    # COGS: debit-normal
    r.cogs = _r2(cogs_d - cogs_c)

    # Gross Profit
    r.gross_profit = _r2(r.revenue - r.cogs)
    r.gross_margin_pct = _pct(r.gross_profit, r.revenue)

    # OpEx: debit-normal operating expenses
    # Also absorb net-debit 'other' rows so nothing falls off the IS
    other_net_debit = max(0.0, other_d - other_c)   # only if net debit
    r.raw_other_net_debit = _r2(other_net_debit)
    r.opex = _r2(opex_d - opex_c + other_net_debit)

    # Operating Profit
    r.operating_profit = _r2(r.gross_profit - r.opex)
    r.operating_margin_pct = _pct(r.operating_profit, r.revenue)

    # Tax: debit-normal
    r.tax = _r2(tax_d - tax_c)

    # Net Profit — ONE formula, always
    r.net_profit = _r2(r.revenue - r.cogs - r.opex - r.tax)
    r.net_margin_pct = _pct(r.net_profit, r.revenue)

    # ── Dashboard convenience fields ──────────────────────────────────────────
    r.expenses_for_chart = _r2(r.cogs + r.opex)          # used in Rev vs Exp chart
    r.total_cost_base    = _r2(r.cogs + r.opex + r.tax)  # full cost reduction

    # ── Validation check ──────────────────────────────────────────────────────
    expected = _r2(r.revenue - r.cogs - r.opex - r.tax)
    r.diff   = abs(expected - r.net_profit)
    r.check  = r.diff <= _tolerance(r.revenue)

    if not r.check:
        r.error = (
            f"ACCOUNTING IDENTITY VIOLATED: "
            f"rev({r.revenue}) - cogs({r.cogs}) - opex({r.opex}) - tax({r.tax}) "
            f"= {expected:.2f} ≠ net_profit({r.net_profit:.2f}), diff={r.diff:.4f}"
        )

    return r


# ══════════════════════════════════════════════════════════════════════════════
#  Batch: build one FinancialResult per period
# ══════════════════════════════════════════════════════════════════════════════

def build_financials_by_period(
    rows,
    period_col: str = "period",
) -> dict[str, FinancialResult]:
    """
    Split rows by period and call build_financials() for each.

    Returns {period_str: FinancialResult}, sorted chronologically.
    """
    if _HAS_PANDAS and isinstance(rows, pd.DataFrame):
        if period_col not in rows.columns:
            return {"": build_financials(rows, period="")}
        grouped = {str(p): g for p, g in rows.groupby(period_col)}
    else:
        from collections import defaultdict
        grouped: dict = defaultdict(list)
        for row in rows:
            grouped[str(row.get(period_col, ""))].append(row)

    return {
        period: build_financials(grp, period=period)
        for period in sorted(grouped.keys())
        for grp in [grouped[period]]
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Serialiser  — converts FinancialResult → plain dict for JSON responses
# ══════════════════════════════════════════════════════════════════════════════

def financials_to_dict(r: FinancialResult) -> dict:
    """
    Return the complete debug + summary dict.
    This is what the API includes in every response so callers can verify.
    """
    return {
        "period":   r.period,
        "row_count": r.row_count,

        # ── Income Statement ─────────────────────────────────────────────────
        "revenue":            r.revenue,
        "cogs":               r.cogs,
        "gross_profit":       r.gross_profit,
        "gross_margin_pct":   r.gross_margin_pct,
        "opex":               r.opex,
        "operating_profit":   r.operating_profit,
        "operating_margin_pct": r.operating_margin_pct,
        "tax":                r.tax,
        "net_profit":         r.net_profit,
        "net_margin_pct":     r.net_margin_pct,

        # ── Dashboard convenience ─────────────────────────────────────────────
        "expenses_for_chart": r.expenses_for_chart,   # cogs + opex  (Rev vs Exp chart)
        "total_cost_base":    r.total_cost_base,       # cogs + opex + tax

        # ── Validation ───────────────────────────────────────────────────────
        "check":  r.check,
        "diff":   r.diff,
        "error":  r.error,

        # ── Raw component sums ────────────────────────────────────────────────
        "_raw": {
            "revenue_credit":  r.raw_revenue_credit,
            "revenue_debit":   r.raw_revenue_debit,
            "cogs_debit":      r.raw_cogs_debit,
            "opex_debit":      r.raw_opex_debit,
            "other_net_debit": r.raw_other_net_debit,
            "tax_debit":       r.raw_tax_debit,
        },

        # ── Formula (documentation) ───────────────────────────────────────────
        "_formula": "net_profit = revenue - cogs - opex - tax",
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _r2(v: float) -> float:
    return round(v, 2)


def _pct(numerator: float, denominator: float) -> Optional[float]:
    if not denominator or math.isnan(denominator) or denominator == 0:
        return None
    return _r2(numerator / denominator * 100)


def _tolerance(revenue: float) -> float:
    """Scale-aware tolerance: 2 cents for small amounts, 1 ppm for large."""
    return max(_TOLERANCE, abs(revenue) * 1e-6)
