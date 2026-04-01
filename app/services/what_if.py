"""
what_if.py — Phase 15
Pure simulation engine. Accepts a baseline statement block and percentage
adjustments, returns a scenario with recalculated P&L and impact deltas.

Design rules:
  - Pure function — no DB, no HTTP, no file I/O
  - Margins always derived from sums (never applied directly)
  - All inputs validated and clamped to sensible bounds
  - basis comes pre-resolved by the caller (API layer)
"""
from __future__ import annotations

from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _safe_div(num: float, den: float) -> Optional[float]:
    if den and abs(den) > 0.001:
        return round(num / den * 100, 2)
    return None


def _pct_delta(scenario: float, baseline: float) -> Optional[float]:
    if baseline and abs(baseline) > 0.001:
        return round((scenario - baseline) / abs(baseline) * 100, 2)
    return None


def _apply_pct(value: float, pct: float) -> float:
    """Apply a percentage change. pct=5 → +5%, pct=-2 → -2%."""
    return round(value * (1 + pct / 100), 2)


def _clamp(pct: float, lo: float = -100.0, hi: float = 500.0) -> float:
    """Prevent nonsensical inputs."""
    return max(lo, min(hi, float(pct)))


# ──────────────────────────────────────────────────────────────────────────────
#  Baseline extractor
# ──────────────────────────────────────────────────────────────────────────────

def _extract_baseline(block: dict) -> dict:
    """
    Extract the key P&L values from an annual_layer block
    (latest_month, ytd, or a full_year entry).

    Expected input shape (from period_aggregation.py):
      { revenue, cogs, expenses, tax, gross_profit, operating_profit,
        net_profit, gross_margin_pct, operating_margin_pct, net_margin_pct }
    """
    return {
        "revenue":           float(block.get("revenue",           0) or 0),
        "cogs":              float(block.get("cogs",              0) or 0),
        "expenses":          float(block.get("expenses",          0) or 0),
        "tax":               float(block.get("tax") or 0),
        "gross_profit":      float(block.get("gross_profit",      0) or 0),
        "operating_profit":  float(block.get("operating_profit",  0) or 0),
        "net_profit":        float(block.get("net_profit",        0) or 0),
        "gross_margin_pct":  block.get("gross_margin_pct"),
        "operating_margin_pct": block.get("operating_margin_pct"),
        "net_margin_pct":    block.get("net_margin_pct"),
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def run_what_if(
    baseline_block: dict,
    revenue_pct: float = 0.0,
    cogs_pct:    float = 0.0,
    opex_pct:    float = 0.0,
) -> dict:
    """
    Simulate P&L changes given percentage adjustments.

    Args:
        baseline_block: a block from annual_layer (latest_month / ytd / full_year)
        revenue_pct:    % change to revenue   (e.g. 5 = +5%)
        cogs_pct:       % change to COGS      (e.g. -2 = -2%)
        opex_pct:       % change to OpEx      (e.g. 0 = unchanged)

    Returns:
        {
          "baseline":  { revenue, cogs, expenses, gross_profit, net_profit, margins },
          "scenario":  { ... same structure with new values },
          "impact":    { revenue_delta, profit_delta, margin_improvement, ... },
          "inputs":    { revenue_pct, cogs_pct, opex_pct }
        }
    """
    # ── Sanitise inputs ───────────────────────────────────────────────────────
    revenue_pct = _clamp(revenue_pct)
    cogs_pct    = _clamp(cogs_pct)
    opex_pct    = _clamp(opex_pct)

    # ── Extract baseline ──────────────────────────────────────────────────────
    b = _extract_baseline(baseline_block)

    # ── Scenario calculation ──────────────────────────────────────────────────
    s_revenue   = _apply_pct(b["revenue"],  revenue_pct)
    s_cogs      = _apply_pct(b["cogs"],     cogs_pct)
    s_expenses  = _apply_pct(b["expenses"], opex_pct)
    s_tax       = b["tax"]   # tax unchanged unless explicitly modelled

    s_gross_profit     = round(s_revenue - s_cogs, 2)
    s_operating_profit = round(s_gross_profit - s_expenses, 2)
    s_net_profit       = round(s_operating_profit - s_tax, 2)

    # Derive margins from scenario sums
    s_gross_margin_pct     = _safe_div(s_gross_profit,     s_revenue)
    s_operating_margin_pct = _safe_div(s_operating_profit, s_revenue)
    s_net_margin_pct       = _safe_div(s_net_profit,       s_revenue)

    scenario = {
        "revenue":               s_revenue,
        "cogs":                  s_cogs,
        "expenses":              s_expenses,
        "tax":                   s_tax,
        "gross_profit":          s_gross_profit,
        "operating_profit":      s_operating_profit,
        "net_profit":            s_net_profit,
        "gross_margin_pct":      s_gross_margin_pct,
        "operating_margin_pct":  s_operating_margin_pct,
        "net_margin_pct":        s_net_margin_pct,
    }

    # ── Impact deltas ─────────────────────────────────────────────────────────
    impact = {
        "revenue_delta":        round(s_revenue  - b["revenue"],  2),
        "cogs_delta":           round(s_cogs     - b["cogs"],     2),
        "expenses_delta":       round(s_expenses - b["expenses"], 2),
        "gross_profit_delta":   round(s_gross_profit     - b["gross_profit"],     2),
        "net_profit_delta":     round(s_net_profit        - b["net_profit"],       2),

        # Percentage changes
        "revenue_pct_change":       _pct_delta(s_revenue,         b["revenue"]),
        "gross_profit_pct_change":  _pct_delta(s_gross_profit,    b["gross_profit"]),
        "net_profit_pct_change":    _pct_delta(s_net_profit,      b["net_profit"]),

        # Margin point differences (percentage points)
        "gross_margin_pp":      round((s_gross_margin_pct     or 0) - (b["gross_margin_pct"]     or 0), 2),
        "net_margin_pp":        round((s_net_margin_pct       or 0) - (b["net_margin_pct"]       or 0), 2),
        "operating_margin_pp":  round((s_operating_margin_pct or 0) - (b["operating_margin_pct"] or 0), 2),
    }

    return {
        "inputs": {
            "revenue_pct": revenue_pct,
            "cogs_pct":    cogs_pct,
            "opex_pct":    opex_pct,
        },
        "baseline": b,
        "scenario": scenario,
        "impact":   impact,
    }
