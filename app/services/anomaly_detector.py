"""
anomaly_detector.py — Phase 21
Threshold-based anomaly detection over financial series.
Detects unusual spikes/drops using Z-score + absolute thresholds.
Pure function — no DB, no HTTP.
"""
from __future__ import annotations
from typing import Optional
import math


# ── Thresholds ────────────────────────────────────────────────────────────────

SPIKE_Z       = 2.0   # Z-score threshold for spike/drop detection
MIN_PERIODS   = 3     # Minimum periods needed for meaningful detection
REV_DROP_PCT  = -15.0 # Hard threshold: revenue drop > 15% = anomaly
MARGIN_DROP   = -5.0  # Hard threshold: margin drop > 5pp = anomaly
NP_SWING_PCT  = 50.0  # Hard threshold: net profit swing > ±50% = anomaly


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def _z(val: float, series: list[float]) -> float:
    sd = _std(series)
    return (val - _mean(series)) / sd if sd > 0.001 else 0.0


def _anomaly(period: str, metric: str, value: float, change_pct: float,
             severity: str, detail: str) -> dict:
    return {
        "period":      period,
        "metric":      metric,
        "value":       round(value, 2),
        "change_pct":  round(change_pct, 1),
        "severity":    severity,  # "critical" | "high" | "medium"
        "detail":      detail,
    }


# ── Detector ──────────────────────────────────────────────────────────────────

def detect_anomalies(
    analysis_trends: dict,
    annual_layer:    dict,
) -> list[dict]:
    """
    Scan financial series for anomalies.
    Returns a list of anomaly dicts (empty if none found).
    """
    anomalies: list[dict] = []
    periods    = analysis_trends.get("periods", [])
    rev_ser    = analysis_trends.get("revenue_series",    [])
    np_ser     = analysis_trends.get("net_profit_series", [])
    rev_mom    = analysis_trends.get("revenue_mom_pct") or analysis_trends.get("revenue_mom",       [])
    np_mom     = analysis_trends.get("net_profit_mom_pct") or analysis_trends.get("net_profit_mom",    [])
    gm_ser     = analysis_trends.get("gross_margin_series", [])
    gm_mom     = analysis_trends.get("gross_margin_mom_pct") or analysis_trends.get("gross_margin_mom",    [])

    if len(periods) < MIN_PERIODS:
        return anomalies

    # ── Revenue anomalies ─────────────────────────────────────────────────────
    rev_clean = [v for v in rev_ser if v is not None and v > 0]
    for i, chg in enumerate(rev_mom):
        if chg is None or i >= len(periods):
            continue
        period = periods[i]
        # Hard threshold
        if chg <= REV_DROP_PCT:
            sev = "critical" if chg <= -25 else "high"
            anomalies.append(_anomaly(period, "revenue", rev_ser[i] or 0, chg, sev,
                f"Revenue dropped {chg:.1f}% vs prior month"))
        elif len(rev_clean) >= MIN_PERIODS:
            z = _z(chg, [v for v in rev_mom[:i] if v is not None] or [0.0])
            if abs(z) >= SPIKE_Z:
                sev = "high" if abs(z) >= 3 else "medium"
                direction = "spike" if chg > 0 else "drop"
                anomalies.append(_anomaly(period, "revenue", rev_ser[i] or 0, chg, sev,
                    f"Unusual revenue {direction} ({chg:+.1f}%) — {abs(z):.1f}σ from baseline"))

    # ── Net profit anomalies ──────────────────────────────────────────────────
    for i, chg in enumerate(np_mom):
        if chg is None or i >= len(periods):
            continue
        period = periods[i]
        if abs(chg) >= NP_SWING_PCT:
            sev = "critical" if abs(chg) >= 80 else "high"
            direction = "surge" if chg > 0 else "collapse"
            anomalies.append(_anomaly(period, "net_profit", np_ser[i] or 0, chg, sev,
                f"Net profit {direction} of {chg:+.1f}%"))

    # ── Margin anomalies ──────────────────────────────────────────────────────
    for i, chg in enumerate(gm_mom):
        if chg is None or i >= len(periods):
            continue
        period = periods[i]
        if chg <= MARGIN_DROP:
            sev = "high" if chg <= -10 else "medium"
            anomalies.append(_anomaly(period, "gross_margin", gm_ser[i] or 0, chg, sev,
                f"Gross margin declined {chg:.1f} pp — cost pressure signal"))

    # ── YTD gap warning (from annual_layer) ───────────────────────────────────
    ytd = annual_layer.get("ytd") or {}
    if ytd.get("has_gaps"):
        anomalies.append({
            "period":     f"YTD {ytd.get('year','')}",
            "metric":     "data_quality",
            "value":      ytd.get("missing_count", 0),
            "change_pct": None,
            "severity":   "medium",
            "detail":     f"{ytd.get('missing_count','?')} missing month(s) in YTD data — totals may be understated",
        })

    # Deduplicate by (period, metric) — keep highest severity
    seen: dict[tuple, dict] = {}
    sev_rank = {"critical": 3, "high": 2, "medium": 1}
    for a in anomalies:
        key = (a["period"], a["metric"])
        if key not in seen or sev_rank.get(a["severity"], 0) > sev_rank.get(seen[key]["severity"], 0):
            seen[key] = a

    return sorted(seen.values(), key=lambda x: (-sev_rank.get(x["severity"], 0), x["period"]))
