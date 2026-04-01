"""
trend_engine.py — Phase 43 Trend Intelligence Upgrade

Interprets MoM trend values into structured pattern signals.
No financial recalculation. No dependencies on other engines.
"""
from __future__ import annotations

# Thresholds — tuned for financial MoM data (all in percentage points)
_MEANINGFUL_GAP  = 2.0   # min pp difference to call accelerating / slowing
_LARGE_GAP       = 6.0   # pp gap that signals volatility
_WEAK_THRESHOLD  = 3.0   # abs(current) below this → weak
_STRONG_THRESHOLD= 8.0   # abs(current) at or above this → strong


def classify_trend(
    current_mom:  float | None,
    previous_mom: float | None,
) -> dict:
    """
    Classify a MoM trend based on two consecutive data points.

    Args:
        current_mom:  latest period MoM % change (may be None)
        previous_mom: prior period MoM % change (may be None)

    Returns:
        {
            "trend_type":    "accelerating" | "slowing" | "reversing" | "stable",
            "trend_strength":"weak" | "moderate" | "strong",
            "consistency":   "stable" | "volatile",
        }
    """
    # ── Safe coercion ─────────────────────────────────────────────────────────
    def _f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    cur  = _f(current_mom)
    prev = _f(previous_mom)

    # ── trend_strength (based solely on current magnitude) ────────────────────
    if cur is None:
        strength = "weak"
    elif abs(cur) >= _STRONG_THRESHOLD:
        strength = "strong"
    elif abs(cur) >= _WEAK_THRESHOLD:
        strength = "moderate"
    else:
        strength = "weak"

    # ── trend_type ────────────────────────────────────────────────────────────
    if cur is None or prev is None:
        trend_type = "stable"
    else:
        same_sign = (cur >= 0 and prev >= 0) or (cur < 0 and prev < 0)
        gap       = abs(cur) - abs(prev)       # positive = magnitude increased

        if not same_sign:
            trend_type = "reversing"
        elif gap > _MEANINGFUL_GAP:
            trend_type = "accelerating"
        elif gap < -_MEANINGFUL_GAP:
            trend_type = "slowing"
        else:
            trend_type = "stable"

    # ── consistency ───────────────────────────────────────────────────────────
    if cur is None or prev is None:
        consistency = "stable"
    else:
        sign_changed  = not ((cur >= 0 and prev >= 0) or (cur < 0 and prev < 0))
        large_swing   = abs(cur - prev) >= _LARGE_GAP
        consistency   = "volatile" if (sign_changed or large_swing) else "stable"

    return {
        "trend_type":     trend_type,
        "trend_strength": strength,
        "consistency":    consistency,
    }
