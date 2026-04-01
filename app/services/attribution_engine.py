"""
attribution_engine.py — Deterministic attribution helpers (EAC standard).

Goal:
- Provide simple, explainable attribution outputs with residuals.
- Never pretend full attribution when data is insufficient.

No DB/HTTP. Safe arithmetic.
"""
from __future__ import annotations

from typing import Optional


def _sf(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _r2(v) -> Optional[float]:
    try:
        return round(float(v), 2) if v is not None else None
    except Exception:
        return None


def variance_share_attribution(
    *,
    deltas: dict[str, Optional[float]],
) -> dict:
    """
    Attribute a total delta to component deltas by absolute share.
    deltas: {driver_key: delta_amount}

    Returns drivers with contribution_pct_of_total and residual.
    """
    clean = {k: _sf(v) for k, v in (deltas or {}).items() if _sf(v) is not None}
    if not clean:
        return {"method": "variance_share", "drivers": [], "residual": None}
    total = sum(clean.values())
    denom = sum(abs(v) for v in clean.values()) or None
    drivers = []
    for k, v in sorted(clean.items(), key=lambda kv: -abs(kv[1])):
        pct = (abs(v) / denom * 100) if denom else None
        drivers.append({
            "driver_key": k,
            "contribution_amount": _r2(v),
            "contribution_pct_of_total": _r2(pct),
            "direction": "positive" if v > 0 else "negative" if v < 0 else "neutral",
            "evidence_metrics": [],
        })
    # Residual: not meaningful for simple share attribution; set to 0 if totals finite
    residual = {"amount": _r2(0.0), "pct_of_total": _r2(0.0)} if denom else None
    return {"method": "variance_share", "drivers": drivers, "residual": residual}


def profit_bridge_attribution(
    *,
    revenue_delta: Optional[float],
    prior_net_margin_pct: Optional[float],
    cogs_ratio_delta_pct: Optional[float],
    opex_ratio_delta_pct: Optional[float],
    latest_revenue: Optional[float],
    observed_net_profit_delta: Optional[float] = None,
) -> dict:
    """
    Simple deterministic profit bridge (one-step, latest vs prior):
    - revenue_effect = ΔRevenue × prior_net_margin
    - cogs_effect    = -(ΔCOGS% /100) × latest_revenue
    - opex_effect    = -(ΔOpEx% /100) × latest_revenue

    Residual = observed_delta - (sum effects) when observed provided.
    """
    dr = _sf(revenue_delta)
    nm0 = _sf(prior_net_margin_pct)
    dc = _sf(cogs_ratio_delta_pct)
    do = _sf(opex_ratio_delta_pct)
    r1 = _sf(latest_revenue)

    if dr is None or nm0 is None or r1 is None:
        return {"method": "profit_bridge", "drivers": [], "residual": None}

    rev_eff = dr * (nm0 / 100.0)
    cogs_eff = -((dc or 0.0) / 100.0) * r1
    opex_eff = -((do or 0.0) / 100.0) * r1

    drivers = [
        {"driver_key": "revenue_effect", "contribution_amount": _r2(rev_eff), "contribution_pct_of_total": None, "direction": "positive" if rev_eff > 0 else "negative" if rev_eff < 0 else "neutral", "evidence_metrics": ["revenue", "net_margin_pct"]},
        {"driver_key": "cogs_ratio_effect", "contribution_amount": _r2(cogs_eff), "contribution_pct_of_total": None, "direction": "positive" if cogs_eff > 0 else "negative" if cogs_eff < 0 else "neutral", "evidence_metrics": ["cogs_ratio_pct", "revenue"]},
        {"driver_key": "opex_ratio_effect", "contribution_amount": _r2(opex_eff), "contribution_pct_of_total": None, "direction": "positive" if opex_eff > 0 else "negative" if opex_eff < 0 else "neutral", "evidence_metrics": ["opex_ratio_pct", "revenue"]},
    ]

    modeled = (rev_eff + cogs_eff + opex_eff)
    resid = None
    obs = _sf(observed_net_profit_delta)
    if obs is not None:
        resid_amt = obs - modeled
        resid = {"amount": _r2(resid_amt), "pct_of_total": None}
    return {"method": "profit_bridge", "drivers": drivers, "residual": resid}

