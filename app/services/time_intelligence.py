"""
time_intelligence.py — Phase 7.6
Pure time-series analysis layer.

Responsibilities:
  - MoM / YoY calculation for any numeric series
  - Period filtering (3M / 6M / 12M / YTD / ALL)
  - Trend classification (up / down / flat)
  - KPI enrichment: wrap any scalar with MoM + YoY + trend

Design rules:
  - Pure functions only — no DB, no HTTP
  - Safe division (never raises)
  - Returns None when data is insufficient (not 0)
"""
from __future__ import annotations

from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════════════

PERIOD_WINDOWS = {
    "3M":  3,
    "6M":  6,
    "12M": 12,
    "YTD": None,   # handled by caller — all periods in current calendar year
    "ALL": None,   # no filter
}

TREND_THRESHOLD = 0.5   # % — below this is "flat"


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _safe_pct(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """(current - previous) / |previous| * 100, or None if insufficient."""
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def _trend(pct: Optional[float]) -> str:
    """Classify a percentage change as 'up' / 'down' / 'flat' / 'unknown'."""
    if pct is None:
        return "unknown"
    if pct > TREND_THRESHOLD:
        return "up"
    if pct < -TREND_THRESHOLD:
        return "down"
    return "flat"


def _round2(v: Optional[float]) -> Optional[float]:
    return round(v, 2) if v is not None else None


# ══════════════════════════════════════════════════════════════════════════════
#  Period filtering
# ══════════════════════════════════════════════════════════════════════════════

def filter_periods(
    period_statements: list[dict],
    window: str = "ALL",
) -> list[dict]:
    """
    Return the subset of period_statements matching the requested window.

    window:
      "3M"  → last 3 periods
      "6M"  → last 6 periods
      "12M" → last 12 periods
      "YTD" → periods whose YYYY == the most recent period's YYYY
      "ALL" → all (unchanged)

    Input must already be sorted chronologically (oldest first).
    """
    if not period_statements or window == "ALL":
        return period_statements

    if window == "YTD":
        if not period_statements:
            return period_statements
        latest_period = period_statements[-1].get("period", "")
        current_year  = latest_period[:4] if len(latest_period) >= 4 else ""
        if not current_year:
            return period_statements
        return [s for s in period_statements if str(s.get("period", "")).startswith(current_year)]

    n = PERIOD_WINDOWS.get(window)
    if n is None:
        return period_statements

    return period_statements[-n:]


# ══════════════════════════════════════════════════════════════════════════════
#  MoM / YoY for a single series
# ══════════════════════════════════════════════════════════════════════════════

def enrich_series_with_changes(
    series: list[Optional[float]],
) -> list[dict]:
    """
    For each element in the series, compute:
      - value
      - mom_pct   (vs previous element)
      - mom_trend
      - yoy_pct   (vs element 12 positions earlier)
      - yoy_trend

    Returns a list of dicts, one per element.
    """
    result = []
    n = len(series)
    for i, v in enumerate(series):
        mom_pct = _safe_pct(v, series[i - 1]) if i > 0 else None
        yoy_pct = _safe_pct(v, series[i - 12]) if i >= 12 else None
        result.append({
            "value":     _round2(v),
            "mom_pct":   mom_pct,
            "mom_trend": _trend(mom_pct),
            "yoy_pct":   yoy_pct,
            "yoy_trend": _trend(yoy_pct),
        })
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  KPI enrichment — single scalar (latest value) with MoM + YoY
# ══════════════════════════════════════════════════════════════════════════════

# Flow KPIs: value = SUM across window (revenue, expenses, etc.)
# Rate KPIs: value = last period in window (margins, ratios)
_KPI_FLOW_LABELS = {
    "revenue", "expenses", "cogs",
    "gross_profit", "net_profit", "operating_profit",
}


def enrich_kpi(
    series: list[Optional[float]],
    label: str = "",
) -> dict:
    """
    Return a KPI dict from a windowed series.

    Semantics:
      Flow metrics (revenue, expenses, profit…): value = SUM of all periods in window.
        1M = that month's value, 3M = sum of 3 months, ALL = sum of all history.
      Rate metrics (margins…): value = last period in window (latest snapshot).

    MoM: last element vs second-to-last (both within the window series).
    YoY: cannot be computed from windowed series alone — kept as None here;
         YoY is provided separately via _yoy_at() in the full series.
    """
    if not series:
        return {"label": label, "value": None, "mom_pct": None, "mom_trend": "unknown",
                "yoy_pct": None, "yoy_trend": "unknown"}

    is_flow = label in _KPI_FLOW_LABELS

    # value: SUM for flow metrics, LAST for rate metrics
    if is_flow:
        vals = [v for v in series if v is not None]
        value = _round2(sum(vals)) if vals else None
    else:
        value = _round2(series[-1]) if series[-1] is not None else None

    # MoM: last vs previous period in the windowed series
    current  = series[-1]
    previous = series[-2] if len(series) >= 2 else None
    mom_pct  = _safe_pct(current, previous)

    return {
        "label":     label,
        "value":     value,
        "mom_pct":   mom_pct,
        "mom_trend": _trend(mom_pct),
        "yoy_pct":   None,   # computed separately via _yoy_at() for full history
        "yoy_trend": "unknown",
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Full KPI dashboard block
# ══════════════════════════════════════════════════════════════════════════════

def build_kpi_block(
    period_statements: list[dict],
    window: str = "ALL",
) -> dict:
    """
    Build the complete KPI block for the dashboard — all KPIs with MoM/YoY.
    Input: period_statements from _build_period_statements() in analysis API.
    Window: "3M" | "6M" | "12M" | "YTD" | "ALL"

    Returns:
    {
      "window":         str,
      "period_count":   int,
      "periods":        [str],
      "kpis": {
        "revenue":         { value, mom_pct, mom_trend, yoy_pct, yoy_trend },
        "expenses":        { ... },
        "gross_profit":    { ... },
        "net_profit":      { ... },
        "gross_margin":    { ... },
        "net_margin":      { ... },
        "operating_margin":{ ... },
        "cogs":            { ... },
      },
      "series": {
        "revenue":        [float, ...],
        "expenses":       [float, ...],
        "net_profit":     [float, ...],
        "gross_margin":   [float, ...],
        "cogs":           [float, ...],
        "operating_profit":[float, ...],
      },
      "mom_series": {
        "revenue":  [None, pct, pct, ...],
        ...
      }
    }
    """
    # Apply window filter — but keep full history for YoY (need 13 months back)
    windowed = filter_periods(period_statements, window)
    # For YoY, we need the raw (unfiltered) full history
    full     = period_statements

    if not windowed:
        return {"window": window, "period_count": 0, "periods": [], "kpis": {}, "series": {}, "mom_series": {}}

    periods = [s.get("period", "") for s in windowed]

    def _extract(stmts: list[dict], path: tuple) -> list[Optional[float]]:
        """Extract a nested value from each statement."""
        result = []
        for s in stmts:
            cur = s
            for key in path:
                if isinstance(cur, dict):
                    cur = cur.get(key)
                else:
                    cur = None
                    break
            result.append(float(cur) if cur is not None else None)
        return result

    IS = ("income_statement",)

    def _expenses_for_chart(stmts):
        """expenses_for_chart = cogs + opex (NOT opex alone).
        This is the total cost base shown in Revenue vs Expenses chart.
        Matches financial_engine.FinancialResult.expenses_for_chart.
        """
        result = []
        for s in stmts:
            is_ = s.get("income_statement", {})
            cogs = float(is_.get("cogs",     {}).get("total", 0) or 0)
            opex = float(is_.get("expenses", {}).get("total", 0) or 0)
            result.append(cogs + opex)
        return result

    # Full series (needed for YoY — must use full history)
    full_rev   = _extract(full, IS + ("revenue",   "total"))
    full_exp   = _expenses_for_chart(full)          # cogs + opex (fixed)
    full_cogs  = _extract(full, IS + ("cogs",      "total"))
    full_gp    = _extract(full, IS + ("gross_profit",))
    full_op    = _extract(full, IS + ("operating_profit",))
    full_np    = _extract(full, IS + ("net_profit",))
    full_gm    = _extract(full, IS + ("gross_margin_pct",))
    full_nm    = _extract(full, IS + ("net_margin_pct",))
    full_om    = _extract(full, IS + ("operating_margin_pct",))

    # Windowed series (for charts and MoM display)
    w_rev  = _extract(windowed, IS + ("revenue",   "total"))
    w_exp  = _expenses_for_chart(windowed)          # cogs + opex (fixed)
    w_cogs = _extract(windowed, IS + ("cogs",      "total"))
    w_gp   = _extract(windowed, IS + ("gross_profit",))
    w_op   = _extract(windowed, IS + ("operating_profit",))
    w_np   = _extract(windowed, IS + ("net_profit",))
    w_gm   = _extract(windowed, IS + ("gross_margin_pct",))
    w_nm   = _extract(windowed, IS + ("net_margin_pct",))
    w_om   = _extract(windowed, IS + ("operating_margin_pct",))

    def _mom_series(series: list) -> list[Optional[float]]:
        """MoM % change for each element vs previous."""
        result: list[Optional[float]] = [None]
        for i in range(1, len(series)):
            result.append(_safe_pct(series[i], series[i - 1]))
        return result

    # YoY: use position in full series aligned to windowed
    # Find where windowed starts in full
    full_periods = [s.get("period", "") for s in full]
    w_start_period = periods[0] if periods else ""
    offset = next((i for i, p in enumerate(full_periods) if p == w_start_period), 0)

    def _yoy_at(full_ser: list, windowed_ser: list) -> list[Optional[float]]:
        result = []
        for wi, v in enumerate(windowed_ser):
            fi = offset + wi
            yoy_base = full_ser[fi - 12] if fi >= 12 else None
            result.append(_safe_pct(v, yoy_base))
        return result

    return {
        "window":       window,
        "period_count": len(windowed),
        "periods":      periods,

        "kpis": {
            # FIX: use windowed (w_*) series so .value reflects the selected window,
            # not the last period in full history. YoY is computed separately via _yoy_at().
            "revenue":          enrich_kpi(w_rev,  "revenue"),
            "expenses":         enrich_kpi(w_exp,  "expenses"),
            "cogs":             enrich_kpi(w_cogs, "cogs"),
            "gross_profit":     enrich_kpi(w_gp,   "gross_profit"),
            "net_profit":       enrich_kpi(w_np,   "net_profit"),
            "gross_margin":     enrich_kpi(w_gm,   "gross_margin"),
            "net_margin":       enrich_kpi(w_nm,   "net_margin"),
            "operating_margin": enrich_kpi(w_om,   "operating_margin"),
            "operating_profit": enrich_kpi(w_op,   "operating_profit"),
        },

        "series": {
            "revenue":          [_round2(v) for v in w_rev],
            "expenses":         [_round2(v) for v in w_exp],
            "cogs":             [_round2(v) for v in w_cogs],
            "gross_profit":     [_round2(v) for v in w_gp],
            "net_profit":       [_round2(v) for v in w_np],
            "gross_margin":     [_round2(v) for v in w_gm],
            "net_margin":       [_round2(v) for v in w_nm],
            "operating_profit": [_round2(v) for v in w_op],
        },

        "mom_series": {
            "revenue":      _mom_series(w_rev),
            "expenses":     _mom_series(w_exp),
            "net_profit":   _mom_series(w_np),
            "gross_margin": _mom_series(w_gm),
        },

        "yoy_series": {
            "revenue":    _yoy_at(full_rev, w_rev),
            "net_profit": _yoy_at(full_np,  w_np),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Unified windowed metric helper — guarantees {current, series, trend} shape
# ══════════════════════════════════════════════════════════════════════════════

def build_windowed_metric(
    period_statements: list[dict],
    extractor,          # callable(stmt) → float|None
    window: str = "ALL",
) -> dict:
    """
    Returns a standardised metric dict from a windowed period list.

    Shape (guaranteed):
    {
        "current": float | None,   ← latest value
        "previous": float | None,  ← prior period value
        "series":  [float|None],   ← full windowed series (oldest→newest)
        "periods": [str],          ← period labels
        "trend":   float | None,   ← MoM % change
        "trend_dir": "up"|"down"|"flat"|"unknown",
        "window":  str,
    }

    Args:
        period_statements: windowed list (already filtered)
        extractor:         callable that takes a stmt dict → float|None
        window:            label for the response
    """
    if not period_statements:
        return {
            "current": None, "previous": None,
            "series": [], "periods": [],
            "trend": None, "trend_dir": "unknown",
            "window": window,
        }

    series  = [extractor(s) for s in period_statements]
    periods = [s.get("period", "") for s in period_statements]

    current  = series[-1]
    previous = series[-2] if len(series) >= 2 else None
    trend    = _safe_pct(current, previous)

    return {
        "current":   _round2(current),
        "previous":  _round2(previous),
        "series":    [_round2(v) for v in series],
        "periods":   periods,
        "trend":     trend,
        "trend_dir": _trend(trend),
        "window":    window,
    }
