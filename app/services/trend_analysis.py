"""
trend_analysis.py — Phase 21
Reads from run_analysis()["trends"] and period_aggregation annual_layer.
Computes direction labels + CAGR + rolling averages.
No new DB access. Pure function.
"""
from __future__ import annotations
from typing import Optional
import math


def _safe(v) -> Optional[float]:
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else round(f, 2)
    except (TypeError, ValueError):
        return None


def _direction(series: list) -> str:
    """Classify trend direction from a MoM series of changes."""
    vals = [v for v in (series or []) if v is not None]
    if len(vals) < 2:
        return "insufficient_data"
    pos = sum(1 for v in vals if v > 0.5)
    neg = sum(1 for v in vals if v < -0.5)
    if pos >= len(vals) * 0.6:
        return "up"
    if neg >= len(vals) * 0.6:
        return "down"
    return "stable"


def _rolling_avg(series: list, n: int = 3) -> Optional[float]:
    vals = [v for v in (series or []) if v is not None]
    if len(vals) < n:
        return None
    return round(sum(vals[-n:]) / n, 2)


def _cagr(start: Optional[float], end: Optional[float], periods: int) -> Optional[float]:
    """Monthly CAGR as annualised %."""
    try:
        s, e, p = float(start), float(end), int(periods)
        if s <= 0 or e <= 0 or p <= 0:
            return None
        return round(((e / s) ** (12 / p) - 1) * 100, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def build_trends(analysis_trends: dict, annual_layer: dict) -> dict:
    """
    Enrich existing run_analysis()["trends"] with direction labels,
    rolling averages, and CAGR pulled from annual_layer.
    """
    if not analysis_trends:
        return {}

    # FIX-2: Key names corrected to match analysis_engine output
    rev_mom   = analysis_trends.get("revenue_mom_pct",       [])  # was: revenue_mom
    np_mom    = analysis_trends.get("net_profit_mom_pct",    [])  # was: net_profit_mom
    gm_mom    = analysis_trends.get("gross_margin_mom_pct",  [])  # was: gross_margin_mom
    rev_ser   = analysis_trends.get("revenue_series",        [])
    np_ser    = analysis_trends.get("net_profit_series",     [])

    # Direction
    rev_dir = _direction(rev_mom)
    np_dir  = _direction(np_mom)
    gm_dir  = _direction(gm_mom)

    # Rolling 3-month average MoM change
    rev_roll  = _rolling_avg(rev_mom)
    np_roll   = _rolling_avg(np_mom)

    # YoY from existing trends — FIX-2: corrected key names
    yoy_rev = _safe(analysis_trends.get("yoy_revenue_pct"))     # was: yoy_revenue_change
    yoy_np  = _safe(analysis_trends.get("yoy_net_profit_pct"))  # was: yoy_net_profit_change

    # CAGR from revenue series
    n = len([v for v in rev_ser if v is not None])
    cagr_rev = _cagr(
        next((v for v in rev_ser if v is not None), None),
        next((v for v in reversed(rev_ser) if v is not None), None),
        n
    )

    # YTD comparison from annual_layer
    ytd_comp = (annual_layer.get("comparisons") or {}).get("ytd_vs_prior_ytd") or {}
    ytd_chg  = ytd_comp.get("changes") or {}

    return {
        "revenue": {
            "direction":    rev_dir,
            "mom_series":   rev_mom,
            "rolling_3m":   rev_roll,
            "yoy_change":   yoy_rev,
            "ytd_vs_prior": _safe(ytd_chg.get("revenue")),
            "cagr_pct":     cagr_rev,
        },
        "net_profit": {
            "direction":    np_dir,
            "mom_series":   np_mom,
            "rolling_3m":   np_roll,
            "yoy_change":   yoy_np,
            "ytd_vs_prior": _safe(ytd_chg.get("net_profit")),
        },
        "gross_margin": {
            "direction":    gm_dir,
            "mom_series":   gm_mom,
            "ytd_margin_pp": _safe(ytd_chg.get("net_margin_pct")),
        },
        "periods": analysis_trends.get("periods", []),
    }
