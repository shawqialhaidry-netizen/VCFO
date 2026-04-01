"""
root_cause_engine.py — Phase 10
Root Cause Analysis Engine — CFO-level "Why" explanations.

Moves beyond "What happened" to "Why it happened".

Input:  analysis dict (from run_analysis) + cashflow dict (from build_cashflow)
Output: root_cause dict appended to API response

All text output uses i18n keys + structured data — zero hardcoded English.

Output shape:
{
  "revenue":        RootCauseBlock,
  "profit":         RootCauseBlock,
  "cashflow":       RootCauseBlock,
  "cost_structure": RootCauseBlock,
  "trends":         TrendSummary,
  "period":         str,
  "period_count":   int,
}

RootCauseBlock = {
  "key":      str,        # primary i18n key (what + why combined)
  "data":     dict,       # interpolation data
  "severity": str,        # "low" | "medium" | "high" | "critical"
  "drivers":  [Driver],   # ordered list of contributing factors
  "trend":    str,        # "improving" | "stable" | "deteriorating"
}

Driver = {
  "key":       str,
  "data":      dict,
  "direction": str,   # "positive" | "negative" | "neutral"
  "magnitude": str,   # "small" | "medium" | "large"
}
"""
from __future__ import annotations

import math
import statistics
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _r2(v) -> Optional[float]:
    return round(float(v), 2) if v is not None else None

def _r1(v) -> Optional[float]:
    return round(float(v), 1) if v is not None else None

def _get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict): return default
        cur = cur.get(k, default)
        if cur is None: return default
    return cur

def _last(series: list, n: int = 1):
    vals = [v for v in series if v is not None]
    return vals[-n:] if len(vals) >= n else vals

def _mean(series: list) -> Optional[float]:
    vals = [v for v in series if v is not None]
    return round(statistics.mean(vals), 2) if vals else None

def _slope(series: list, window: int = 6) -> Optional[float]:
    """OLS slope over last `window` non-None values."""
    vals = [v for v in series if v is not None][-window:]
    n = len(vals)
    if n < 2: return None
    xm = (n - 1) / 2
    ym = sum(vals) / n
    num = sum((i - xm) * (vals[i] - ym) for i in range(n))
    den = sum((i - xm) ** 2 for i in range(n))
    return round(num / den, 4) if den else 0.0

def _cv(series: list) -> Optional[float]:
    """Coefficient of variation (std/mean) — volatility measure."""
    vals = [v for v in series if v is not None]
    if len(vals) < 2: return None
    m = abs(statistics.mean(vals))
    if m == 0: return None
    return round(statistics.stdev(vals) / m, 4)

def _classify_trend(slope: Optional[float], cv: Optional[float] = None) -> str:
    """Classify directional trend from slope."""
    if slope is None: return "stable"
    threshold = 1000  # absolute slope units per period
    if slope > threshold:   return "improving"
    if slope < -threshold:  return "deteriorating"
    return "stable"

def _classify_pct_trend(mom_series: list, window: int = 3) -> str:
    """Classify trend from MoM pct series."""
    vals = [v for v in mom_series if v is not None][-window:]
    if not vals: return "stable"
    pos = sum(1 for v in vals if v > 0.5)
    neg = sum(1 for v in vals if v < -0.5)
    if pos >= len(vals) - 1: return "improving"
    if neg >= len(vals) - 1: return "deteriorating"
    return "stable"

def _magnitude(value: float, thresholds: tuple = (5, 15)) -> str:
    """Classify absolute value magnitude."""
    abs_v = abs(value)
    if abs_v < thresholds[0]: return "small"
    if abs_v < thresholds[1]: return "medium"
    return "large"

def _fmtK(v) -> str:
    if v is None: return "—"
    return f"{v/1000:.0f}K" if abs(v) >= 1000 else f"{v:.0f}"

def _severity_from_mom(mom: Optional[float]) -> str:
    if mom is None: return "low"
    abs_m = abs(mom)
    if abs_m > 25: return "high"
    if abs_m > 10: return "medium"
    return "low"

def _driver(key: str, data: dict, direction: str, magnitude: str) -> dict:
    return {"key": key, "data": data, "direction": direction, "magnitude": magnitude}


# ══════════════════════════════════════════════════════════════════════════════
#  A. Revenue Root Cause
# ══════════════════════════════════════════════════════════════════════════════

def _analyze_revenue(trends: dict, latest_ratios: dict) -> dict:
    """
    Determine WHY revenue changed — consistency, acceleration, or one-off.
    """
    rev  = trends.get("revenue_series", [])
    mom  = trends.get("revenue_mom_pct", [])
    yoy  = trends.get("yoy_revenue_pct")
    streak_up   = 0
    streak_down = trends.get("revenue_decline_streak", 0)

    # Count consecutive positive MoM
    for v in reversed([x for x in mom if x is not None]):
        if v > 0: streak_up += 1
        else: break

    last_mom  = _last(mom, 1)[0]  if _last(mom, 1)  else None
    last3_avg = _mean(_last(mom, 3)) if _last(mom, 3) else None
    last_rev  = _last(rev, 1)[0]  if _last(rev, 1)  else None
    prev_rev  = _last(rev, 2)[0]  if _last(rev, 2)  else None
    slope     = _slope(rev, window=6)
    cv_val    = _cv(rev)
    trend     = _classify_pct_trend(mom, window=3)

    # Build primary key + drivers
    drivers = []

    if trend == "improving":
        if streak_up >= 3:
            primary_key = "rc_rev_consistent_growth"
            data = {"streak": streak_up, "avg_mom": round(last3_avg or 0, 1),
                    "current": _fmtK(last_rev)}
        else:
            primary_key = "rc_rev_recovering"
            data = {"mom": round(last_mom or 0, 1), "current": _fmtK(last_rev)}
    elif trend == "deteriorating":
        if streak_down >= 3:
            primary_key = "rc_rev_structural_decline"
            data = {"streak": streak_down, "avg_mom": round(last3_avg or 0, 1),
                    "current": _fmtK(last_rev)}
        elif last_mom is not None and last_mom < -15:
            primary_key = "rc_rev_sharp_drop"
            data = {"mom": round(last_mom, 1), "prev": _fmtK(prev_rev),
                    "current": _fmtK(last_rev)}
        else:
            primary_key = "rc_rev_mild_decline"
            data = {"mom": round(last_mom or 0, 1), "current": _fmtK(last_rev)}
    else:
        primary_key = "rc_rev_stable"
        data = {"current": _fmtK(last_rev), "avg_mom": round(last3_avg or 0, 1)}

    # YoY context driver
    if yoy is not None:
        direction = "positive" if yoy > 0 else "negative"
        drivers.append(_driver("rc_drv_yoy_context",
                               {"yoy": round(yoy, 1)},
                               direction, _magnitude(yoy, (5, 20))))

    # Volatility driver
    if cv_val is not None and cv_val > 0.15:
        drivers.append(_driver("rc_drv_rev_volatile",
                               {"cv": round(cv_val, 2)},
                               "negative", "medium" if cv_val < 0.30 else "large"))

    # Acceleration/deceleration driver
    if len([v for v in mom if v is not None]) >= 4:
        recent_avg = _mean(_last(mom, 2))
        prior_avg  = _mean(mom[-4:-2] if len(mom) >= 4 else mom)
        if recent_avg is not None and prior_avg is not None:
            accel = recent_avg - prior_avg
            if abs(accel) > 5:
                key = "rc_drv_rev_accelerating" if accel > 0 else "rc_drv_rev_decelerating"
                drivers.append(_driver(key, {"delta": round(abs(accel), 1)},
                               "positive" if accel > 0 else "negative",
                               _magnitude(abs(accel), (5, 15))))

    return {
        "key":      primary_key,
        "data":     data,
        "severity": _severity_from_mom(last_mom),
        "drivers":  drivers,
        "trend":    trend,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  B. Profit Root Cause — Decomposition
# ══════════════════════════════════════════════════════════════════════════════

def _analyze_profit(trends: dict, latest_ratios: dict) -> dict:
    """
    Attribute NP change to: revenue effect, COGS ratio, OpEx growth.

    NP_change ≈ Revenue_effect - COGS_ratio_effect - OpEx_ratio_effect
    Revenue_effect   = ΔRevenue × prior_NP_margin
    COGS_effect      = -ΔCOGS%  × latest_Revenue
    OpEx_effect      = -ΔOpEx%  × latest_Revenue
    """
    rev  = trends.get("revenue_series", [])
    cogs = trends.get("cogs_series", [])
    exp  = trends.get("expenses_series", [])
    np_  = trends.get("net_profit_series", [])
    mom  = trends.get("net_profit_mom_pct", [])
    gm   = trends.get("gross_margin_series", [])
    streak_down = trends.get("net_profit_decline_streak", 0)

    last_mom  = _last(mom, 1)[0]  if _last(mom, 1)  else None
    last3_avg = _mean(_last(mom, 3))
    slope     = _slope(np_, window=6)
    trend     = _classify_pct_trend(mom, window=3)

    drivers = []

    # Decompose latest period vs prior
    if len(rev) >= 2 and len(cogs) >= 2 and len(exp) >= 2 and len(np_) >= 2:
        r1, r0 = rev[-1], rev[-2]
        c1, c0 = cogs[-1], cogs[-2]
        o1, o0 = exp[-1], exp[-2]
        n1, n0 = np_[-1], np_[-2]

        cp0 = c0/r0*100 if r0 else 0
        cp1 = c1/r1*100 if r1 else 0
        op0 = o0/r0*100 if r0 else 0
        op1 = o1/r1*100 if r1 else 0

        delta_rev       = r1 - r0
        delta_cogs_pct  = cp1 - cp0   # negative = margin improvement
        delta_opex_pct  = op1 - op0

        # Attribution: how much NP change came from each driver
        rev_contribution   = delta_rev * (1 - cp0/100 - op0/100)  # NP rate × ΔRev
        cogs_contribution  = -delta_cogs_pct / 100 * r1           # COGS% change × Rev
        opex_contribution  = -delta_opex_pct / 100 * r1           # OpEx% change × Rev
        np_change          = n1 - n0

        # Revenue driver
        if abs(delta_rev) > 5000:
            dir_ = "positive" if delta_rev > 0 else "negative"
            drivers.append(_driver("rc_drv_profit_from_revenue",
                                   {"contribution": _fmtK(round(rev_contribution)),
                                    "delta_rev": _fmtK(round(delta_rev))},
                                   dir_, _magnitude(abs(delta_rev)/r0*100 if r0 else 0, (5, 20))))

        # COGS rate driver
        if abs(delta_cogs_pct) > 0.5:
            dir_ = "positive" if delta_cogs_pct < 0 else "negative"
            drivers.append(_driver("rc_drv_profit_from_cogs",
                                   {"delta_pct": round(abs(delta_cogs_pct), 2),
                                    "contribution": _fmtK(round(cogs_contribution)),
                                    "direction_word": "improved" if delta_cogs_pct < 0 else "worsened"},
                                   dir_, _magnitude(abs(delta_cogs_pct), (0.5, 2.0))))

        # OpEx rate driver
        if abs(delta_opex_pct) > 0.5:
            dir_ = "positive" if delta_opex_pct < 0 else "negative"
            drivers.append(_driver("rc_drv_profit_from_opex",
                                   {"delta_pct": round(abs(delta_opex_pct), 2),
                                    "contribution": _fmtK(round(opex_contribution)),
                                    "direction_word": "reduced" if delta_opex_pct < 0 else "grew"},
                                   dir_, _magnitude(abs(delta_opex_pct), (0.5, 2.0))))

        # Primary key selection
        dominant_driver = max([
            ("revenue",  abs(rev_contribution)),
            ("cogs",     abs(cogs_contribution)),
            ("opex",     abs(opex_contribution)),
        ], key=lambda x: x[1])[0]

        if trend == "improving":
            if dominant_driver == "revenue":
                primary_key = "rc_profit_rev_driven_growth"
                data = {"mom": round(last_mom or 0, 1),
                        "driver_pct": round(abs(rev_contribution / np_change * 100) if np_change else 0, 1),
                        "current": _fmtK(n1)}
            elif dominant_driver == "cogs":
                primary_key = "rc_profit_margin_expansion"
                data = {"delta_cogs": round(abs(delta_cogs_pct), 2),
                        "current": _fmtK(n1)}
            else:
                primary_key = "rc_profit_opex_efficiency"
                data = {"delta_opex": round(abs(delta_opex_pct), 2),
                        "current": _fmtK(n1)}
        elif trend == "deteriorating":
            if dominant_driver == "revenue":
                primary_key = "rc_profit_rev_driven_decline"
                data = {"mom": round(last_mom or 0, 1),
                        "delta_rev": _fmtK(round(delta_rev)),
                        "current": _fmtK(n1)}
            elif dominant_driver == "cogs":
                primary_key = "rc_profit_margin_compression_cogs"
                data = {"delta_cogs": round(delta_cogs_pct, 2),
                        "current": _fmtK(n1)}
            else:
                primary_key = "rc_profit_opex_overrun"
                data = {"delta_opex": round(delta_opex_pct, 2),
                        "current": _fmtK(n1)}
        else:
            primary_key = "rc_profit_stable"
            data = {"current": _fmtK(n1),
                    "avg_mom": round(last3_avg or 0, 1)}
    else:
        primary_key = "rc_profit_insufficient_data"
        data = {}

    return {
        "key":      primary_key,
        "data":     data,
        "severity": _severity_from_mom(last_mom),
        "drivers":  drivers,
        "trend":    trend,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  C. Cash Flow Root Cause
# ══════════════════════════════════════════════════════════════════════════════

def _analyze_cashflow(cashflow: dict) -> dict:
    """
    Explain WHY OCF differs from Net Profit — attribute to WC components.
    """
    ocf    = cashflow.get("operating_cashflow") or 0
    np_    = (cashflow.get("debug") or {}).get("net_profit") or 0
    da     = cashflow.get("da_estimate") or 0
    wc     = cashflow.get("working_capital_change") or {}
    qual   = cashflow.get("quality") or {}
    gap    = qual.get("profit_vs_cash_gap") or 0
    q_lbl  = qual.get("cash_conversion_quality", "moderate")
    ratio  = qual.get("cash_conversion_ratio")
    ocf_mom = cashflow.get("operating_cashflow_mom")

    delta_rec = wc.get("receivables", 0) or 0
    delta_inv = wc.get("inventory", 0)   or 0
    delta_pay = wc.get("payables", 0)    or 0
    wc_net    = wc.get("net", 0) or 0

    drivers = []

    # D&A addback driver (non-cash)
    if da and da > 2000:
        drivers.append(_driver("rc_drv_cf_da_addback",
                               {"da": _fmtK(da)},
                               "positive", _magnitude(da / max(abs(np_), 1) * 100, (5, 20))))

    # Receivables driver
    if abs(delta_rec) > 5000:
        dir_ = "negative" if delta_rec > 0 else "positive"
        drivers.append(_driver("rc_drv_cf_receivables",
                               {"delta": _fmtK(abs(delta_rec)),
                                "direction_word": "increased" if delta_rec > 0 else "decreased"},
                               dir_, _magnitude(abs(delta_rec) / max(abs(np_), 1) * 100, (10, 30))))

    # Inventory driver
    if abs(delta_inv) > 5000:
        dir_ = "negative" if delta_inv > 0 else "positive"
        drivers.append(_driver("rc_drv_cf_inventory",
                               {"delta": _fmtK(abs(delta_inv)),
                                "direction_word": "built up" if delta_inv > 0 else "reduced"},
                               dir_, _magnitude(abs(delta_inv) / max(abs(np_), 1) * 100, (10, 30))))

    # Payables driver
    if abs(delta_pay) > 5000:
        dir_ = "positive" if delta_pay > 0 else "negative"
        drivers.append(_driver("rc_drv_cf_payables",
                               {"delta": _fmtK(abs(delta_pay)),
                                "direction_word": "extended" if delta_pay > 0 else "reduced"},
                               dir_, _magnitude(abs(delta_pay) / max(abs(np_), 1) * 100, (10, 30))))

    # Primary key selection
    trend = ("improving"    if (ocf_mom or 0) > 5
             else "deteriorating" if (ocf_mom or 0) < -5
             else "stable")

    if q_lbl == "strong":
        primary_key = "rc_cf_strong_conversion"
        data = {"ocf": _fmtK(ocf), "np": _fmtK(np_),
                "ratio": round(ratio or 1.0, 2)}
        severity = "low"
    elif q_lbl == "weak":
        # Find dominant WC drag
        biggest_drag = max(
            [("receivables", delta_rec),
             ("inventory", delta_inv),
             ("payables", -delta_pay)],
            key=lambda x: x[1]
        )
        if biggest_drag[1] > 10000:
            primary_key = "rc_cf_wc_drag"
            data = {"gap": _fmtK(abs(gap)),
                    "driver": biggest_drag[0],
                    "ocf": _fmtK(ocf), "np": _fmtK(np_)}
        else:
            primary_key = "rc_cf_weak_conversion"
            data = {"gap": _fmtK(abs(gap)), "ocf": _fmtK(ocf),
                    "np": _fmtK(np_), "ratio": round(ratio or 0, 2)}
        severity = "medium" if abs(gap) < abs(np_) * 0.3 else "high"
    elif ocf < 0:
        primary_key = "rc_cf_negative"
        data = {"ocf": _fmtK(ocf), "np": _fmtK(np_),
                "wc_net": _fmtK(abs(wc_net))}
        severity = "high"
    else:
        primary_key = "rc_cf_moderate"
        data = {"ocf": _fmtK(ocf), "np": _fmtK(np_),
                "ratio": round(ratio or 0.8, 2)}
        severity = "low"

    return {
        "key":      primary_key,
        "data":     data,
        "severity": severity,
        "drivers":  drivers,
        "trend":    trend,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  D. Cost Structure Root Cause
# ══════════════════════════════════════════════════════════════════════════════

def _analyze_cost_structure(trends: dict, latest_ratios: dict) -> dict:
    """
    Detect COGS vs OpEx structural shifts.
    """
    rev  = trends.get("revenue_series", [])
    cogs = trends.get("cogs_series", [])
    exp  = trends.get("expenses_series", [])

    if not rev or not cogs or not exp:
        return {"key": "rc_cost_insufficient_data", "data": {},
                "severity": "low", "drivers": [], "trend": "stable"}

    # Compute rolling COGS% and OpEx% series
    cogs_pct = [c/r*100 for c, r in zip(cogs, rev) if r]
    opex_pct = [o/r*100 for o, r in zip(exp,  rev) if r]

    latest_cogs_pct = cogs_pct[-1] if cogs_pct else 0
    latest_opex_pct = opex_pct[-1] if opex_pct else 0
    avg_cogs_pct    = _mean(cogs_pct) or 0
    avg_opex_pct    = _mean(opex_pct) or 0

    cogs_slope = _slope(cogs_pct, window=min(6, len(cogs_pct)))
    opex_slope = _slope(opex_pct, window=min(6, len(opex_pct)))

    # Last 3 periods COGS trend
    last3_cogs = cogs_pct[-3:] if len(cogs_pct) >= 3 else cogs_pct
    cogs_trend = ("improving"    if (cogs_slope or 0) < -0.1
                  else "deteriorating" if (cogs_slope or 0) > 0.1
                  else "stable")
    opex_trend = ("improving"    if (opex_slope or 0) < -0.1
                  else "deteriorating" if (opex_slope or 0) > 0.1
                  else "stable")

    drivers = []

    # COGS driver
    delta_cogs = latest_cogs_pct - avg_cogs_pct
    if abs(delta_cogs) > 1.0:
        dir_ = "negative" if delta_cogs > 0 else "positive"
        drivers.append(_driver(
            "rc_drv_cost_cogs_shift",
            {"current": round(latest_cogs_pct, 1),
             "avg": round(avg_cogs_pct, 1),
             "delta": round(abs(delta_cogs), 1),
             "direction_word": "above" if delta_cogs > 0 else "below"},
            dir_, _magnitude(abs(delta_cogs), (1, 3))
        ))

    # OpEx driver
    delta_opex = latest_opex_pct - avg_opex_pct
    if abs(delta_opex) > 1.0:
        dir_ = "negative" if delta_opex > 0 else "positive"
        drivers.append(_driver(
            "rc_drv_cost_opex_shift",
            {"current": round(latest_opex_pct, 1),
             "avg": round(avg_opex_pct, 1),
             "delta": round(abs(delta_opex), 1),
             "direction_word": "above" if delta_opex > 0 else "below"},
            dir_, _magnitude(abs(delta_opex), (1, 3))
        ))

    # Primary key
    if cogs_trend == "improving" and opex_trend == "improving":
        primary_key = "rc_cost_structure_improving"
        data = {"cogs": round(latest_cogs_pct, 1), "opex": round(latest_opex_pct, 1)}
        severity = "low"
        trend = "improving"
    elif cogs_trend == "deteriorating" or opex_trend == "deteriorating":
        worse  = "COGS" if (cogs_slope or 0) > (opex_slope or 0) else "OpEx"
        primary_key = "rc_cost_structure_deteriorating"
        data = {"cogs": round(latest_cogs_pct, 1), "opex": round(latest_opex_pct, 1),
                "primary_driver": worse}
        severity = "medium"
        trend = "deteriorating"
    else:
        primary_key = "rc_cost_structure_stable"
        data = {"cogs": round(latest_cogs_pct, 1), "opex": round(latest_opex_pct, 1),
                "avg_cogs": round(avg_cogs_pct, 1)}
        severity = "low"
        trend = "stable"

    return {
        "key":      primary_key,
        "data":     data,
        "severity": severity,
        "drivers":  drivers,
        "trend":    trend,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  E. Trend Classification Summary
# ══════════════════════════════════════════════════════════════════════════════

def _build_trend_summary(trends: dict, cashflow: dict) -> dict:
    """
    Classify each key metric as improving / stable / deteriorating.
    """
    rev_mom  = trends.get("revenue_mom_pct", [])
    np_mom   = trends.get("net_profit_mom_pct", [])
    gm_ser   = trends.get("gross_margin_series", [])
    cf_series= (cashflow.get("series") or {}).get("operating_cashflow", [])

    # Revenue trend
    rev_trend = _classify_pct_trend(rev_mom, window=3)

    # NP trend
    np_trend = _classify_pct_trend(np_mom, window=3)

    # Gross margin trend (use slope of last 4)
    gm_slope = _slope(gm_ser, window=4)
    gm_trend = ("improving"    if (gm_slope or 0) > 0.1
                else "deteriorating" if (gm_slope or 0) < -0.1
                else "stable")

    # OCF trend (use last 4 OCF values slope)
    cf_slope = _slope([v for v in cf_series if v is not None], window=4)
    cf_trend = ("improving"    if (cf_slope or 0) > 500
                else "deteriorating" if (cf_slope or 0) < -500
                else "stable")

    # Overall score: count improving vs deteriorating
    trend_list = [rev_trend, np_trend, gm_trend, cf_trend]
    n_imp = trend_list.count("improving")
    n_det = trend_list.count("deteriorating")

    if n_imp >= 3:
        overall = "improving"
    elif n_det >= 3:
        overall = "deteriorating"
    elif n_det >= 2:
        overall = "mixed_negative"
    elif n_imp >= 2:
        overall = "mixed_positive"
    else:
        overall = "stable"

    return {
        "revenue":      rev_trend,
        "net_profit":   np_trend,
        "gross_margin": gm_trend,
        "cashflow":     cf_trend,
        "overall":      overall,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def build_root_cause(
    analysis: dict,
    cashflow: dict,
) -> dict:
    """
    Phase 10 Root Cause Analysis Engine.

    Input:
      analysis — dict from run_analysis()
      cashflow — dict from build_cashflow()

    Output: root_cause dict (appended to API response)
    """
    trends       = analysis.get("trends") or {}
    latest       = analysis.get("latest") or {}
    periods      = analysis.get("periods") or []

    revenue_rc      = _analyze_revenue(trends, latest)
    profit_rc       = _analyze_profit(trends, latest)
    cashflow_rc     = _analyze_cashflow(cashflow)
    cost_rc         = _analyze_cost_structure(trends, latest)
    trend_summary   = _build_trend_summary(trends, cashflow)

    # Overall severity (worst of the four)
    _sev_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    worst_sev = max(
        [revenue_rc["severity"], profit_rc["severity"],
         cashflow_rc["severity"], cost_rc["severity"]],
        key=lambda s: _sev_rank.get(s, 0)
    )

    return {
        "period":         periods[-1] if periods else "",
        "period_count":   len(periods),
        "overall_severity": worst_sev,
        "revenue":        revenue_rc,
        "profit":         profit_rc,
        "cashflow":       cashflow_rc,
        "cost_structure": cost_rc,
        "trends":         trend_summary,
    }


def derive_phase43_metrics_trends(
    stmts: list,
    analysis: dict,
) -> tuple[dict, dict]:
    """
    Build (metrics, trends) inputs for build_root_causes() from statements + run_analysis.
    Deterministic; uses canonical metric_definitions ratios (aligned with company path).
    """
    from app.services.metric_definitions import cogs_ratio_pct, opex_ratio_pct, total_cost_ratio_pct

    def _last_valid(series):
        valid = [x for x in (series or []) if x is not None]
        return valid[-1] if valid else None

    def _mom_series(series: list) -> list:
        out: list = [None]
        for i in range(1, len(series)):
            prev = series[i - 1]
            curr = series[i]
            if prev is None or curr is None or prev == 0:
                out.append(None)
            else:
                out.append(round((curr - prev) / abs(prev) * 100, 2))
        return out

    trends_r = analysis.get("trends") or {}
    latest = analysis.get("latest") or {}
    prof = latest.get("profitability") or {} if isinstance(latest, dict) else {}

    _latest_stmt = stmts[-1] if stmts else {}
    _is = _latest_stmt.get("income_statement", {}) if isinstance(_latest_stmt, dict) else {}
    _rev = (_is.get("revenue", {}) or {}).get("total")
    _cogs = (_is.get("cogs", {}) or {}).get("total")
    _exp = (_is.get("expenses", {}) or {}).get("total")
    _unc = float((_is.get("unclassified_pnl_debits") or {}).get("total") or 0)

    _opex_ratio = opex_ratio_pct(
        float(_exp) if _exp is not None else None,
        float(_rev) if _rev is not None else None,
    )
    _cogs_ratio = cogs_ratio_pct(
        float(_cogs) if _cogs is not None else None,
        float(_rev) if _rev is not None else None,
    )
    _total_cost_ratio = total_cost_ratio_pct(
        float(_cogs) if _cogs is not None else None,
        float(_exp) if _exp is not None else None,
        float(_rev) if _rev is not None else None,
        _unc,
    )
    _expense_ratio = _total_cost_ratio

    _exp_ratio_series: list = []
    _cogs_ratio_series: list = []
    _nm_series: list = []
    for _s in (stmts or []):
        _is_s = (_s.get("income_statement") or {}) if isinstance(_s, dict) else {}
        _r = ((_is_s.get("revenue", {}) or {}).get("total"))
        _e = ((_is_s.get("expenses", {}) or {}).get("total"))
        _cg = ((_is_s.get("cogs", {}) or {}).get("total"))
        _u = float((_is_s.get("unclassified_pnl_debits") or {}).get("total") or 0)
        _nm = _is_s.get("net_margin_pct")
        _exp_ratio_series.append(
            total_cost_ratio_pct(
                float(_cg) if _cg is not None else None,
                float(_e) if _e is not None else None,
                float(_r) if _r is not None else None,
                _u,
            )
        )
        _cogs_ratio_series.append(
            cogs_ratio_pct(
                float(_cg) if _cg is not None else None,
                float(_r) if _r is not None else None,
            )
        )
        _nm_series.append(float(_nm) if _nm is not None else None)

    _total_cost_ratio_mom = _last_valid(_mom_series(_exp_ratio_series))
    _cogs_ratio_mom = _last_valid(_mom_series(_cogs_ratio_series))
    _net_margin_mom = _last_valid(_mom_series(_nm_series))

    _p43_metrics = {
        "net_margin_pct": prof.get("net_margin_pct"),
        "opex_ratio_pct": _opex_ratio,
        "cogs_ratio_pct": _cogs_ratio,
        "total_cost_ratio_pct": _total_cost_ratio,
        "expense_ratio": _expense_ratio,
        "cogs_ratio": _cogs_ratio,
    }
    _p43_trends = {
        "revenue_mom": _last_valid(trends_r.get("revenue_mom_pct")),
        "net_profit_mom": _last_valid(trends_r.get("net_profit_mom_pct")),
        "opex_mom_pct": _last_valid(trends_r.get("expenses_mom_pct")),
        "expense_ratio_mom": _last_valid(trends_r.get("expenses_mom_pct")),
        "total_cost_ratio_mom": _total_cost_ratio_mom,
        "cogs_ratio_mom": _cogs_ratio_mom,
        "net_margin_mom": _net_margin_mom,
    }
    return _p43_metrics, _p43_trends


# ── Phase 43 — Root Cause Engine (simplified interface) ──────────────────────
# Interprets existing metrics and trends ONLY.
# No financial recalculation. No engine modification.

def build_root_causes(
    metrics: dict,
    trends:  dict,
    lang:    str = "en",
) -> list:
    """
    WHY layer: detect the 4 canonical root cause patterns from existing
    metric and trend snapshots.

    Args:
        metrics: flat dict of latest-period KPIs
        trends:  flat dict of MoM % change values
        lang:    "en" | "ar" | "tr"

    Returns:
        list of root-cause dicts, ordered by severity (high first).
    """
    ar = lang == "ar"
    tr = lang == "tr"

    def _g(d, *keys, default=None):
        for k in keys:
            v = d.get(k)
            if v is not None:
                return v
        return default

    nm       = _g(metrics, "net_margin_pct", "net_margin") or 0.0
    exp_r    = _g(metrics, "total_cost_ratio_pct", "expense_ratio", "expense_ratio_pct") or 0.0
    cogs_r   = _g(metrics, "cogs_ratio", "cogs_ratio_pct") or 0.0

    rev_mom  = _g(trends, "revenue_mom",       "revenue_mom_pct",      default=0.0)
    np_mom   = _g(trends, "net_profit_mom",    "net_profit_mom_pct",   default=0.0)
    exp_mom  = _g(trends, "opex_mom_pct", "expense_ratio_mom", "expense_ratio_mom_pct", default=0.0)
    cogs_mom = _g(trends, "cogs_ratio_mom",    "cogs_ratio_mom_pct",   default=0.0)
    nm_mom   = _g(trends, "net_margin_mom",    "net_margin_mom_pct",   default=0.0)

    results: list[dict] = []

    # ── 1. margin_pressure ────────────────────────────────────────────────────
    mp_trigger = (nm_mom < -1.0) or (cogs_mom > rev_mom and cogs_mom > 0)
    if mp_trigger:
        drivers = []
        if cogs_mom > rev_mom and cogs_mom > 0:
            drivers.append("cogs_increase")
        if exp_mom > 3.0:
            drivers.append("expense_growth")
        if nm_mom < -1.0 and "expense_growth" not in drivers:
            drivers.append("margin_contraction")

        if ar:
            what = (f"تكلفة البضاعة ارتفعت {cogs_mom:.1f}٪ متجاوزةً نمو الإيرادات البالغ {rev_mom:.1f}٪، "
                    f"مما أحدث ضغطاً مباشراً على هامش الربح الإجمالي.")
            why  = ("عندما تنمو التكاليف أسرع من الإيرادات يتآكل الهامش الإجمالي، وإن تزامن ذلك مع "
                    "ارتفاع المصروفات التشغيلية، تتراجع الربحية الصافية بصورة أكثر حدة.")
        elif tr:
            what = (f"SMM {cogs_mom:.1f}% artarak {rev_mom:.1f}% olan gelir büyümesini geçti; "
                    f"bu durum brüt kâr marjını doğrudan baskı altına aldı.")
            why  = ("Maliyetler gelirden hızlı büyüdüğünde brüt marj erir; faaliyet giderleri de "
                    "artıyorsa net kârlılık çok daha sert gerileyebilir.")
        else:
            what = (f"COGS grew {cogs_mom:.1f}% — outpacing revenue growth of {rev_mom:.1f}% — "
                    f"applying direct pressure on gross margin.")
            why  = ("When costs grow faster than revenue, gross margin erodes. If operating expenses "
                    "are also rising, net profitability declines more sharply.")

        results.append({
            "type":           "margin_pressure",
            "severity":       "high" if (cogs_mom - rev_mom) > 5 or nm_mom < -3 else "medium",
            "what_happened":  what,
            "why":            why,
            "drivers":        drivers,
            "confidence":     "high" if len(drivers) >= 2 else "medium",
            "source_metrics": {
                "cogs_ratio_mom_pct":  cogs_mom,
                "revenue_mom_pct":     rev_mom,
                "net_margin_mom_pct":  nm_mom,
                "net_margin_pct":      nm,
            },
        })

    # ── 2. cost_spike ─────────────────────────────────────────────────────────
    if exp_mom > 3.0:
        sev = "high" if exp_mom > 10 else "medium" if exp_mom > 6 else "low"

        if ar:
            what = f"نسبة المصروفات التشغيلية ارتفعت {exp_mom:.1f}٪ مقارنةً بالشهر الماضي."
            why  = ("الارتفاع السريع في المصروفات يُضيّق هامش التشغيل حتى حين تكون الإيرادات في نمو؛ "
                    "مصادر الضغط الأكثر شيوعاً هي الرواتب والإيجار والخدمات والعقود المتغيرة التكلفة.")
        elif tr:
            what = f"Faaliyet gideri oranı geçen aya göre {exp_mom:.1f}% arttı."
            why  = ("Giderlerdeki hızlı artış, gelir büyürken bile faaliyet marjını daraltır; "
                    "en yaygın baskı kaynakları bordro, kira, hizmetler ve değişken maliyetli sözleşmelerdir.")
        else:
            what = f"Operating expense ratio spiked {exp_mom:.1f}% MoM."
            why  = ("Rapid expense growth compresses operating margin even when revenue is rising. "
                    "Common pressure sources: payroll, rent, services, and variable-cost contracts.")

        results.append({
            "type":           "cost_spike",
            "severity":       sev,
            "what_happened":  what,
            "why":            why,
            "drivers":        ["operating_expense_increase"],
            "confidence":     "high",
            "source_metrics": {
                "expense_ratio_mom_pct": exp_mom,
                "expense_ratio_pct":     exp_r,
            },
        })

    # ── 3. profit_growth_quality_issue ────────────────────────────────────────
    if rev_mom > 0 and np_mom < rev_mom:
        gap = round(rev_mom - np_mom, 1)
        sev = "high" if np_mom < 0 else "medium" if gap > 10 else "low"

        if ar:
            what = (f"الإيرادات نمت {rev_mom:.1f}٪ لكن صافي الربح ارتفع بمعدل أبطأ ({np_mom:.1f}٪)، "
                    f"مما يكشف فجوة {gap:.1f} نقطة مئوية بين نمو الإيرادات ونمو الأرباح.")
            why  = ("النمو المُفضي إلى ربح أقل نسبياً يعني أن التكاليف تمتص الجزء الأكبر من الإيرادات "
                    "الإضافية. الأسباب الأكثر احتمالاً: هامش أقل على الإيرادات الجديدة، ارتفاع تكلفة "
                    "التسليم، أو ضغط تسعيري.")
        elif tr:
            what = (f"Gelir {rev_mom:.1f}% büyüdü ancak net kâr daha yavaş arttı ({np_mom:.1f}%); "
                    f"gelir büyümesi ile kâr büyümesi arasında {gap:.1f} puanlık açık var.")
            why  = ("Görece daha az kâr üreten büyüme, ek gelirlerin büyük bölümünü maliyetlerin "
                    "yuttuğuna işaret eder. Olası nedenler: yeni gelirde düşük marj, teslimat "
                    "maliyetlerinde artış veya fiyatlandırma baskısı.")
        else:
            what = (f"Revenue grew {rev_mom:.1f}% but net profit grew slower ({np_mom:.1f}%), "
                    f"revealing a {gap:.1f}pp gap between Revenue growth and profit growth.")
            why  = ("Growth that produces proportionally less profit means incremental revenue is "
                    "being absorbed by costs. Likely causes: lower margin on new Revenue, rising "
                    "delivery costs, or pricing pressure.")

        results.append({
            "type":           "profit_growth_quality_issue",
            "severity":       sev,
            "what_happened":  what,
            "why":            why,
            "drivers":        ["revenue_outpacing_profit", "cost_absorption"],
            "confidence":     "high",
            "source_metrics": {
                "revenue_mom_pct":    rev_mom,
                "net_profit_mom_pct": np_mom,
                "growth_gap_pp":      gap,
            },
        })

    # ── 4. strong_profitability ───────────────────────────────────────────────
    # Triggered only when margin is healthy AND not already covered by a warning above
    margin_under_pressure = any(r["type"] == "margin_pressure" for r in results)
    if nm > 20 and not margin_under_pressure:
        if ar:
            what = f"هامش الربح الصافي بلغ {nm:.1f}٪ — أعلى من عتبة الأداء القوي البالغة 20٪."
            why  = ("هامش بهذا المستوى يُشير إلى ضبط جيد للتكاليف وقوة تسعيرية مستدامة. "
                    "الأولوية الآن هي حماية هذا الهامش من خلال انضباط المصروفات ومراجعة هيكل التكاليف "
                    "قبل توسّع الطاقة الإنتاجية.")
        elif tr:
            what = f"Net kâr marjı {nm:.1f}% — güçlü performans eşiği olan %20'nin üzerinde."
            why  = ("Bu marj seviyesi, iyi maliyet kontrolü ve sürdürülebilir fiyat gücüne işaret eder. "
                    "Şu an öncelik, kapasite genişlemesinden önce gider disiplini ve maliyet yapısı "
                    "gözden geçirilerek bu marjı korumaktır.")
        else:
            what = f"Net margin at {nm:.1f}% — above the strong-performance threshold of 20%."
            why  = ("This margin level signals well-controlled costs and sustainable pricing power. "
                    "Priority now is protecting this margin through expense discipline and cost structure "
                    "review before capacity expansion.")

        results.append({
            "type":           "strong_profitability",
            "severity":       "info",
            "what_happened":  what,
            "why":            why,
            "drivers":        ["healthy_margin", "cost_control"],
            "confidence":     "high",
            "source_metrics": {
                "net_margin_pct":      nm,
                "expense_ratio_pct":   exp_r,
            },
        })

    # ── Conflict resolution: pressure overrides positive signal ──────────────
    types = {r["type"] for r in results}
    if "margin_pressure" in types and "strong_profitability" in types:
        results = [r for r in results if r["type"] != "strong_profitability"]

    # Sort: high → medium → low → info
    _sev_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    results.sort(key=lambda r: _sev_rank.get(r["severity"], 4))

    # Conflict resolution: pressure overrides positive signal
    types = {r["type"] for r in results}
    if "margin_pressure" in types and "strong_profitability" in types:
        results = [r for r in results if r["type"] != "strong_profitability"]

    def _confidence_score(conf: str) -> int:
        return {"high": 88, "medium": 66, "low": 48, "info": 55}.get(str(conf or "").lower(), 55)

    def _why_numerical(sm: dict) -> str:
        """Deterministic, numbers-only explanation (auditable)."""
        if not sm:
            return ""
        parts = []
        for k in sorted(sm.keys()):
            v = sm[k]
            if v is None:
                continue
            try:
                parts.append(f"{k}={float(v):.4g}")
            except (TypeError, ValueError):
                parts.append(f"{k}={v}")
        return "; ".join(parts)

    def _enrich(r: dict) -> dict:
        """Additive CFO structure: cause, metric, direction, impact_level, evidence."""
        typ = r.get("type", "")
        sev = r.get("severity", "medium")
        impact_level = {"high": "high", "medium": "medium", "low": "low", "info": "low"}.get(sev, "medium")
        direction = "stable"
        if typ in ("margin_pressure", "cost_spike", "profit_growth_quality_issue"):
            direction = "deteriorating"
        elif typ == "strong_profitability":
            direction = "improving"

        primary_metric = {
            "margin_pressure": "cogs_ratio_mom_pct",
            "cost_spike": "expense_ratio_mom_pct",
            "profit_growth_quality_issue": "net_profit_mom_pct",
            "strong_profitability": "net_margin_pct",
        }.get(typ, typ)

        sm = dict(r.get("source_metrics") or {})
        cause_key = typ.replace("_", " ")
        conf = r.get("confidence", "medium")
        out = {
            **r,
            "cause": typ,
            "cause_label_key": cause_key,
            "metric": primary_metric,
            "direction": direction,
            "impact_level": impact_level,
            "why_numerical": _why_numerical(sm),
            "confidence_score": _confidence_score(conf),
            "evidence": {
                "source_metrics": sm,
                "drivers":        list(r.get("drivers") or []),
                "confidence":     conf,
                "confidence_score": _confidence_score(conf),
                "severity":       sev,
            },
        }
        return out

    return [_enrich(r) for r in results]
