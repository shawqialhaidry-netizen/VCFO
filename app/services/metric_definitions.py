"""
metric_definitions.py — canonical P&L ratio formulas (Phase: metric alignment).

Official definitions (all return 0–100 scale % or None if not meaningful):

- opex_ratio_pct           = operating_expenses / revenue × 100
- cogs_ratio_pct           = cogs / revenue × 100
- total_cost_ratio_pct     = (cogs + operating_expenses + unclassified_pnl_debits) / revenue × 100

Legacy alias:
- expense_ratio (and expense_ratio_pct in summaries) = total_cost_ratio_pct
  for backward compatibility — full cost load vs revenue.

Revenue / margin semantics are documented at call sites (latest vs window sums).
"""
from __future__ import annotations

from typing import Optional


def pct_of_revenue(numerator: Optional[float], revenue: Optional[float]) -> Optional[float]:
    if numerator is None or revenue is None:
        return None
    if abs(float(revenue)) < 1e-9:
        return None
    return round(float(numerator) / float(revenue) * 100, 2)


def opex_ratio_pct(opex: Optional[float], revenue: Optional[float]) -> Optional[float]:
    return pct_of_revenue(opex, revenue)


def cogs_ratio_pct(cogs: Optional[float], revenue: Optional[float]) -> Optional[float]:
    return pct_of_revenue(cogs, revenue)


def total_cost_ratio_pct(
    cogs: Optional[float],
    opex: Optional[float],
    revenue: Optional[float],
    unclassified_pnl_debits: Optional[float] = None,
) -> Optional[float]:
    """(COGS + classified OpEx + optional unclassified P&amp;L debits) / revenue × 100."""
    if revenue is None or abs(float(revenue)) < 1e-9:
        return None
    c = float(cogs or 0)
    o = float(opex or 0)
    u = float(unclassified_pnl_debits or 0)
    total = c + o + u
    return round(total / float(revenue) * 100, 2)
