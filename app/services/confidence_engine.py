"""
confidence_engine.py — Deterministic confidence scoring (EAC standard).

Inputs: MetricResolver quality snapshot + optional signal metadata.
Outputs: {score_0_100, level, reasons}

Rules:
- Deterministic only.
- Conservative defaults: missing/approximated data reduces confidence.
- No DB, no HTTP.
"""
from __future__ import annotations

from typing import Literal, Optional


ConfidenceLevel = Literal["low", "medium", "high"]


def _level(score: int) -> ConfidenceLevel:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def score_confidence(
    *,
    n_periods: int,
    missing_points: int = 0,
    approximated: bool = False,
    volatile: bool = False,
    denom_risk: bool = False,
) -> dict:
    """
    Deterministic confidence score.

    Starting point depends on periods; then penalties are applied.
    """
    reasons: list[str] = []

    if n_periods >= 12:
        score = 85
    elif n_periods >= 6:
        score = 78
    elif n_periods >= 3:
        score = 65
    elif n_periods >= 2:
        score = 55
    elif n_periods >= 1:
        score = 40
    else:
        score = 20
        reasons.append("no_periods")

    if missing_points:
        score -= min(25, missing_points * 6)
        reasons.append("missing_points")

    if approximated:
        score -= 12
        reasons.append("approximated_inputs")

    if volatile:
        score -= 10
        reasons.append("high_volatility")

    if denom_risk:
        score -= 10
        reasons.append("denominator_risk")

    score = max(0, min(100, int(round(score))))
    lvl = _level(score)
    if n_periods and n_periods < 3:
        reasons.append("short_history")

    return {
        "score_0_100": score,
        "level": lvl,
        "reasons": reasons,
    }

