"""
Canonical structured profit story derived from structured profit bridge + interpretation.

Uses only keys present on the analysis dict:
  structured_profit_bridge, structured_profit_bridge_interpretation,
  structured_profit_bridge_meta

Optional context for classification:
  latest.profitability.net_margin_pct (same shape as run_analysis["latest"])
"""
from __future__ import annotations

from typing import Any, Optional


def _fmt_delta(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    try:
        s = f"{float(v):+.2f}"
        return s
    except (TypeError, ValueError):
        return "n/a"


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def _null_story(bridge: dict, meta: dict) -> dict[str, Any]:
    return {
        "latest_period": bridge.get("latest_period"),
        "previous_period": bridge.get("previous_period"),
        "summary_type": None,
        "what_changed_key": None,
        "what_changed_params": {},
        "why_key": None,
        "why_params": {},
        "action_key": None,
        "action_params": {},
    }


def build_structured_profit_story_from_analysis(analysis: dict) -> dict[str, Any]:
    """
    Deterministic bridge → story mapping:

      - paradox_flags.revenue_up_profit_down → paradox_growth_loss
      - net_result=profit_down & primary_driver=opex → cost_pressure
      - net_result=profit_down & primary_driver=cogs → margin_compression
      - net_result=profit_up & primary_driver=revenue → healthy_growth if latest NM >= 10%
        else profit_recovery (weak margin context)
      - otherwise → mixed (or null story if bridge meta completeness is none)
    """
    if not isinstance(analysis, dict):
        return _null_story({}, {})

    bridge = analysis.get("structured_profit_bridge") or {}
    interp = analysis.get("structured_profit_bridge_interpretation") or {}
    meta = analysis.get("structured_profit_bridge_meta") or {}

    if (meta.get("completeness") or "") == "none":
        return _null_story(bridge, meta)

    latest_pf = (analysis.get("latest") or {}).get("profitability") or {}
    nm = latest_pf.get("net_margin_pct")
    try:
        nm_f = float(nm) if nm is not None else None
    except (TypeError, ValueError):
        nm_f = None

    rc = bridge.get("revenue_change") or {}
    cc = bridge.get("cogs_change") or {}
    oc = bridge.get("opex_change") or {}
    gc = bridge.get("gross_profit_change") or {}
    opc = bridge.get("operating_profit_change") or {}
    nc = bridge.get("net_profit_change") or {}

    base_params: dict[str, Any] = {
        "latest_period": bridge.get("latest_period"),
        "previous_period": bridge.get("previous_period"),
        "delta_rev": rc.get("delta"),
        "delta_rev_pct": rc.get("delta_pct"),
        "delta_cogs": cc.get("delta"),
        "delta_cogs_pct": cc.get("delta_pct"),
        "delta_opex": oc.get("delta"),
        "delta_opex_pct": oc.get("delta_pct"),
        "delta_gp": gc.get("delta"),
        "delta_op": opc.get("delta"),
        "delta_np": nc.get("delta"),
        "delta_np_pct": nc.get("delta_pct"),
        "delta_rev_fmt": _fmt_delta(rc.get("delta")),
        "delta_rev_pct_fmt": _fmt_pct(rc.get("delta_pct")),
        "delta_cogs_fmt": _fmt_delta(cc.get("delta")),
        "delta_opex_fmt": _fmt_delta(oc.get("delta")),
        "delta_np_fmt": _fmt_delta(nc.get("delta")),
        "delta_gp_fmt": _fmt_delta(gc.get("delta")),
        "delta_op_fmt": _fmt_delta(opc.get("delta")),
        "primary_driver": interp.get("primary_driver") or "n/a",
        "net_result": interp.get("net_result"),
    }

    paradox = interp.get("paradox_flags") or {}
    net_r = interp.get("net_result")
    pdrv = interp.get("primary_driver")

    summary_type: Optional[str] = None
    what_key: Optional[str] = None
    why_key: Optional[str] = None
    action_key: Optional[str] = None

    if paradox.get("revenue_up_profit_down"):
        summary_type = "paradox_growth_loss"
        what_key = "profit_story.paradox_growth_loss.what_changed"
        why_key = "profit_story.paradox_growth_loss.why"
        action_key = "profit_story.paradox_growth_loss.action"
    elif net_r == "profit_down" and pdrv == "opex":
        summary_type = "cost_pressure"
        what_key = "profit_story.cost_pressure.what_changed"
        why_key = "profit_story.cost_pressure.why"
        action_key = "profit_story.cost_pressure.action"
    elif net_r == "profit_down" and pdrv == "cogs":
        summary_type = "margin_compression"
        what_key = "profit_story.margin_compression.what_changed"
        why_key = "profit_story.margin_compression.why"
        action_key = "profit_story.margin_compression.action"
    elif net_r == "profit_up" and pdrv == "revenue":
        if nm_f is not None and nm_f < 10.0:
            summary_type = "profit_recovery"
            what_key = "profit_story.profit_recovery.what_changed"
            why_key = "profit_story.profit_recovery.why"
            action_key = "profit_story.profit_recovery.action"
        else:
            summary_type = "healthy_growth"
            what_key = "profit_story.healthy_growth.what_changed"
            why_key = "profit_story.healthy_growth.why"
            action_key = "profit_story.healthy_growth.action"
    else:
        summary_type = "mixed"
        what_key = "profit_story.mixed.what_changed"
        why_key = "profit_story.mixed.why"
        action_key = "profit_story.mixed.action"

    nm_disp = f"{nm_f:.1f}" if nm_f is not None else "n/a"
    params_w = {**base_params, "nm_pct": nm_disp}
    params_y = {**base_params}
    params_a = {**base_params}

    return {
        "latest_period": bridge.get("latest_period"),
        "previous_period": bridge.get("previous_period"),
        "summary_type": summary_type,
        "what_changed_key": what_key,
        "what_changed_params": params_w,
        "why_key": why_key,
        "why_params": params_y,
        "action_key": action_key,
        "action_params": params_a,
    }


def build_structured_profit_story_from_window(
    windowed: list[dict],
    *,
    latest_profitability: Optional[dict] = None,
) -> dict[str, Any]:
    """Build story when full analysis dict is unavailable (e.g. statement bundle)."""
    from app.services.structured_profit_bridge import (
        build_structured_profit_bridge_bundle_from_window,
    )

    pack = build_structured_profit_bridge_bundle_from_window(windowed)
    fake = {
        **pack,
        "latest": {"profitability": latest_profitability or {}},
    }
    return build_structured_profit_story_from_analysis(fake)
