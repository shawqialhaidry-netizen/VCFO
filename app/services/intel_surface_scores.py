"""
Single source for Command Center / intelligence surface scores (0–100).
Mirrors former frontend commandCenterIntelScores.js — server-owned only.
"""
from __future__ import annotations

from typing import Any


def _score_from_category(ratios: dict, cat: str) -> int:
    s2 = {"good": 100, "neutral": 60, "warning": 35, "risk": 10}
    category = (ratios or {}).get(cat) or {}
    if not isinstance(category, dict):
        return 50
    vs: list[int] = []
    for v in category.values():
        if isinstance(v, dict):
            st = v.get("status")
            vs.append(s2.get(str(st), 50))
    if not vs:
        return 50
    return int(round(sum(vs) / len(vs)))


def _risk_composite(ratios: dict, alerts: list | None) -> int:
    lev = _score_from_category(ratios, "leverage")
    hi = sum(1 for a in (alerts or []) if (a or {}).get("severity") == "high")
    med = sum(1 for a in (alerts or []) if (a or {}).get("severity") == "medium")
    penalty = min(30, hi * 12 + med * 5)
    return max(0, min(100, int(round(lev - penalty))))


def build_intel_surface_scores(intelligence: dict, alerts: list | None) -> dict[str, Any]:
    ratios = (intelligence or {}).get("ratios") or {}
    return {
        "profitability": _score_from_category(ratios, "profitability"),
        "liquidity": _score_from_category(ratios, "liquidity"),
        "efficiency": _score_from_category(ratios, "efficiency"),
        "leverage": _score_from_category(ratios, "leverage"),
        "growth": _score_from_category(ratios, "growth"),
        "risk_composite": _risk_composite(ratios, alerts),
    }


def build_intel_tile_hints(cashflow: dict | None, kpi_block: dict | None) -> dict[str, Any]:
    """Which headline number to show on intel tiles — no client-side metric picking."""
    cf = cashflow or {}
    kpis = (kpi_block or {}).get("kpis") or {}
    ocf = cf.get("operating_cashflow")
    wc_entry = kpis.get("working_capital") or {}
    wc_val = wc_entry.get("value")
    liquidity_primary = None
    try:
        if ocf is not None and float(ocf) == float(ocf):
            liquidity_primary = "ocf"
        elif wc_val is not None and float(wc_val) == float(wc_val):
            liquidity_primary = "wc"
    except (TypeError, ValueError):
        liquidity_primary = None

    exp_mom = (kpis.get("expenses") or {}).get("mom_pct")
    nm_val = (kpis.get("net_margin") or {}).get("value")
    efficiency_primary = None
    try:
        if exp_mom is not None and float(exp_mom) == float(exp_mom):
            efficiency_primary = "exp_mom"
        elif nm_val is not None and float(nm_val) == float(nm_val):
            efficiency_primary = "net_margin"
    except (TypeError, ValueError):
        efficiency_primary = None

    return {
        "liquidity_primary": liquidity_primary,
        "liquidity_ocf": float(ocf) if liquidity_primary == "ocf" and ocf is not None else None,
        "liquidity_wc": float(wc_val) if liquidity_primary == "wc" and wc_val is not None else None,
        "efficiency_primary": efficiency_primary,
        "efficiency_expense_mom": float(exp_mom) if efficiency_primary == "exp_mom" else None,
        "efficiency_net_margin_pct": float(nm_val) if efficiency_primary == "net_margin" else None,
    }
