"""
Rolling / historical context for CFO decisions (Phase 5B).
Builds multi-period baselines from run_analysis()["ratios"] (raw compute_ratios output).
"""
from __future__ import annotations

import math
from typing import Any, Optional


def _dig(raw: dict, *path: str) -> Optional[float]:
    d: Any = raw
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    if d is None:
        return None
    try:
        v = float(d)
        return None if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return None


def _mean(vals: list[float]) -> Optional[float]:
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _stdev(vals: list[float]) -> Optional[float]:
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
    sd = math.sqrt(var)
    return round(sd, 6) if sd > 1e-9 else None


def _percentile_rank(latest: float, history: list[float]) -> Optional[float]:
    """0–100 rank of latest within history (inclusive)."""
    if not history:
        return None
    below = sum(1 for x in history if x < latest)
    return round(100.0 * below / len(history), 1)


def _z_score(latest: float, baseline_vals: list[float]) -> Optional[float]:
    if not baseline_vals:
        return None
    m = _mean(baseline_vals)
    sd = _stdev(baseline_vals)
    if m is None or sd is None or sd < 1e-9:
        return None
    return round((latest - m) / sd, 2)


# (category, field) on raw compute_ratios() dict per period
_RAW_METRIC_PATHS: list[tuple[str, str, str]] = [
    ("liquidity", "current_ratio", "current_ratio"),
    ("liquidity", "quick_ratio", "quick_ratio"),
    ("liquidity", "working_capital", "working_capital"),
    ("profitability", "net_margin_pct", "net_margin_pct"),
    ("profitability", "gross_margin_pct", "gross_margin_pct"),
    ("profitability", "operating_margin_pct", "operating_margin_pct"),
    ("leverage", "debt_to_equity", "debt_to_equity"),
    ("efficiency", "dso_days", "dso_days"),
    ("efficiency", "dpo_days", "dpo_days"),
    ("efficiency", "ccc_days", "ccc_days"),
]


def build_ratio_depth_context(analysis: Optional[dict]) -> dict[str, Any]:
    """
    Returns {
      period_span: { from_period, to_period, n_periods },
      metrics: { "liquidity.current_ratio": {
          latest, rolling_avg_3m, rolling_avg_6m,
          delta_vs_roll_6m, yoy_same_period (optional),
          stdev_6m, z_vs_roll6_excl_latest, percentile_in_window
      }, ... }
    }
    """
    if not analysis or not isinstance(analysis, dict):
        return {}

    ratios_by_p = analysis.get("ratios") or {}
    periods: list[str] = list(analysis.get("periods") or [])
    if not periods and ratios_by_p:
        periods = sorted(ratios_by_p.keys())

    if not periods:
        return {}

    n = len(periods)
    out_metrics: dict[str, Any] = {}

    for cat, name, field in _RAW_METRIC_PATHS:
        key = f"{cat}.{name}"
        series: list[Optional[float]] = []
        for p in periods:
            raw = ratios_by_p.get(p) or {}
            series.append(_dig(raw, cat, field))

        valid_all = [x for x in series if x is not None]
        latest = series[-1] if series else None

        def _tail_avg(k: int) -> Optional[float]:
            if not series:
                return None
            kk = min(k, len(series))
            vv = [x for x in series[-kk:] if x is not None]
            if not vv:
                return None
            return _mean(vv)

        r3 = _tail_avg(3)
        r6 = _tail_avg(6)

        # Delta vs baseline = prior window mean (exclude latest to avoid double-counting)
        prev5 = [x for x in series[-6:-1] if x is not None]
        prev2 = [x for x in series[-3:-1] if x is not None]
        baseline6 = _mean(prev5) if prev5 else None
        baseline3 = _mean(prev2) if prev2 else None
        delta6 = round(latest - baseline6, 4) if latest is not None and baseline6 is not None else None
        delta3 = round(latest - baseline3, 4) if latest is not None and baseline3 is not None else None

        prior = series[:-1] if len(series) > 1 else []
        hist_excl = [x for x in prior[-6:] if x is not None]
        z_excl = _z_score(latest, hist_excl) if latest is not None and len(hist_excl) >= 2 else None

        pct = None
        if latest is not None and valid_all:
            pct = _percentile_rank(latest, valid_all)

        roll6_vals = [x for x in series[-min(6, len(series)) :] if x is not None]
        st6 = _stdev(roll6_vals) if len(roll6_vals) >= 2 else None

        yoy = None
        if len(series) >= 13 and series[-1] is not None and series[-13] is not None:
            prev = series[-13]
            if prev != 0:
                yoy = round((series[-1] - prev) / abs(prev) * 100, 2)

        out_metrics[key] = {
            "latest": latest,
            "rolling_avg_3m": r3,
            "rolling_avg_6m": r6,
            "delta_vs_roll_3m": delta3,
            "delta_vs_roll_6m": delta6,
            "yoy_change_pct": yoy,
            "stdev_6m": st6,
            "z_vs_roll6_excl_latest": z_excl,
            "percentile_in_window": pct,
        }

    return {
        "period_span": {
            "from_period": periods[0],
            "to_period": periods[-1],
            "n_periods": n,
        },
        "metrics": out_metrics,
    }


def depth_get(depth: dict, path: str) -> dict:
    return (depth.get("metrics") or {}).get(path) or {}


def material_ratio_signal(
    depth: dict,
    path: str,
    *,
    abs_delta_min: float = 0.0,
    abs_z_min: float = 0.0,
) -> bool:
    row = depth_get(depth, path)
    d = row.get("delta_vs_roll_6m")
    z = row.get("z_vs_roll6_excl_latest")
    ok = False
    if d is not None and abs(float(d)) >= abs_delta_min:
        ok = True
    if z is not None and abs(float(z)) >= abs_z_min:
        ok = True
    return ok
