"""
CFO-grade profit bridge from structured income statement variance.

Inputs (only):
  - Output of `build_structured_income_statement_variance_bundle_from_window`
    (which is grounded in `structured_income_statement` per period).

No KPI shortcuts or legacy summary fields.
"""
from __future__ import annotations

from typing import Any, Optional

from app.services.structured_income_statement_variance import (
    build_structured_income_statement_variance_bundle_from_window,
)

_DRIVER_KEYS = ("revenue", "cogs", "opex")
_TIE_EPS = 1e-6


def _change_block(var_line: dict) -> dict[str, Any]:
    return {
        "delta": var_line.get("delta"),
        "delta_pct": var_line.get("delta_pct"),
    }


def _effect_revenue(delta: Optional[float]) -> Optional[str]:
    if delta is None:
        return None
    if delta > 0:
        return "positive"
    if delta < 0:
        return "negative"
    return "neutral"


def _effect_cogs(delta: Optional[float]) -> Optional[str]:
    """Higher COGS is negative for profit; lower COGS is positive."""
    if delta is None:
        return None
    if delta > 0:
        return "negative"
    if delta < 0:
        return "positive"
    return "neutral"


def _effect_opex(delta: Optional[float]) -> Optional[str]:
    """Higher OpEx is negative for profit; lower OpEx is positive."""
    if delta is None:
        return None
    if delta > 0:
        return "negative"
    if delta < 0:
        return "positive"
    return "neutral"


def _net_result(net_delta: Optional[float]) -> Optional[str]:
    if net_delta is None:
        return None
    if net_delta > 0:
        return "profit_up"
    if net_delta < 0:
        return "profit_down"
    return "flat"


def _primary_driver(variance_block: dict[str, Any]) -> Optional[str]:
    """
    Driver = P&L line with largest absolute period delta among revenue, cogs, opex.
    Tie within _TIE_EPS -> "mixed". Any delta null excluded; if none left -> null.
    """
    scored: list[tuple[str, float]] = []
    for k in _DRIVER_KEYS:
        line = variance_block.get(k) or {}
        d = line.get("delta")
        if d is None:
            continue
        scored.append((k, abs(float(d))))
    if not scored:
        return None
    scored.sort(key=lambda x: x[1], reverse=True)
    top_k, top_v = scored[0]
    if len(scored) >= 2:
        second_v = scored[1][1]
        if abs(top_v - second_v) <= _TIE_EPS:
            return "mixed"
    return top_k


def _paradox_flags(
    revenue_delta: Optional[float],
    net_delta: Optional[float],
) -> dict[str, bool]:
    up_down = (
        revenue_delta is not None
        and net_delta is not None
        and revenue_delta > 0
        and net_delta < 0
    )
    down_up = (
        revenue_delta is not None
        and net_delta is not None
        and revenue_delta < 0
        and net_delta > 0
    )
    return {
        "revenue_up_profit_down": bool(up_down),
        "revenue_down_profit_up": bool(down_up),
    }


def _interpretation(
    variance_block: dict[str, Any],
) -> dict[str, Any]:
    rev_d = (variance_block.get("revenue") or {}).get("delta")
    cogs_d = (variance_block.get("cogs") or {}).get("delta")
    opex_d = (variance_block.get("opex") or {}).get("delta")
    net_d = (variance_block.get("net_profit") or {}).get("delta")

    return {
        "revenue_effect": _effect_revenue(rev_d),
        "cogs_effect": _effect_cogs(cogs_d),
        "opex_effect": _effect_opex(opex_d),
        "net_result": _net_result(net_d),
        "primary_driver": _primary_driver(variance_block),
        "paradox_flags": _paradox_flags(rev_d, net_d),
    }


def _missing_components(
    bridge_body: dict[str, Any],
    variance_meta: dict[str, Any],
) -> list[str]:
    if variance_meta.get("completeness") == "none":
        return ["insufficient_periods"]
    out: list[str] = []
    for key in (
        "revenue_change",
        "cogs_change",
        "gross_profit_change",
        "opex_change",
        "operating_profit_change",
        "net_profit_change",
    ):
        blk = bridge_body.get(key) or {}
        if blk.get("delta") is None:
            out.append(f"{key}.delta")
        if blk.get("delta_pct") is None:
            out.append(f"{key}.delta_pct")
    return sorted(set(out))


def build_structured_profit_bridge_bundle_from_window(windowed: list[dict]) -> dict[str, Any]:
    """
    Build bridge + interpretation + meta from the last two periods in windowed.

    Formulas (from variance only):
      Each *_change.delta / *_change.delta_pct copies
      structured_income_statement_variance[line].delta / .delta_pct.

    Interpretation:
      - revenue_effect: sign of revenue delta (up = positive for profit)
      - cogs_effect / opex_effect: inverted sign (increase = negative for profit)
      - net_result: from net_profit delta sign
      - primary_driver: argmax(|Δrevenue|, |Δcogs|, |Δopex|) among non-null; tie -> mixed
      - paradox_flags: revenue vs net_profit delta directions as specified
    """
    var_pack = build_structured_income_statement_variance_bundle_from_window(windowed)
    vmeta = var_pack["structured_income_statement_variance_meta"]
    vblk = var_pack["structured_income_statement_variance"]

    bridge = {
        "latest_period": vmeta.get("latest_period"),
        "previous_period": vmeta.get("previous_period"),
        "revenue_change": _change_block(vblk.get("revenue") or {}),
        "cogs_change": _change_block(vblk.get("cogs") or {}),
        "gross_profit_change": _change_block(vblk.get("gross_profit") or {}),
        "opex_change": _change_block(vblk.get("opex") or {}),
        "operating_profit_change": _change_block(vblk.get("operating_profit") or {}),
        "net_profit_change": _change_block(vblk.get("net_profit") or {}),
    }

    interp = _interpretation(vblk)

    vcomp = vmeta.get("completeness") or "none"
    if vcomp == "full":
        bcomp = "full"
    elif vcomp == "partial":
        bcomp = "partial"
    else:
        bcomp = "none"

    bridge_meta = {
        "completeness": bcomp,
        "missing_components": _missing_components(bridge, vmeta),
        "latest_period": bridge["latest_period"],
        "previous_period": bridge["previous_period"],
    }

    return {
        "structured_profit_bridge": bridge,
        "structured_profit_bridge_interpretation": interp,
        "structured_profit_bridge_meta": bridge_meta,
    }
