"""
financial_ratios.py — Phase 21
Formats a card-ready ratio set from analysis_engine output.

ARCHITECTURE:
  Does NOT recompute any financial values.
  Reads ONLY from run_analysis()["latest"] which itself reads from
  statement_engine (financial_statements.py) — the single source of truth.

  Pipeline position:
    financial_statements → statements_to_dict → run_analysis → extract_ratios

Input:  analysis["latest"]  (from run_analysis)
Output: { gross_margin, net_margin, current_ratio, quick_ratio,
          working_capital, debt_ratio, inventory_turnover, ... }

Note: working_capital here is read from analysis["latest"]["liquidity"]["working_capital"]
which originates from balance_sheet.working_capital in financial_statements.py.
"""
from __future__ import annotations
from typing import Optional


def _r2(v) -> Optional[float]:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _status(v: Optional[float], good_above: Optional[float] = None,
            warn_above: Optional[float] = None, good_below: Optional[float] = None,
            warn_below: Optional[float] = None) -> str:
    """Return 'good'|'warning'|'risk'|'neutral' for a single ratio value."""
    if v is None:
        return "neutral"
    if good_above is not None and v >= good_above:
        return "good"
    if good_below is not None and v <= good_below:
        return "good"
    if warn_above is not None and v >= warn_above:
        return "warning"
    if warn_below is not None and v <= warn_below:
        return "warning"
    return "neutral"


def extract_ratios(latest: dict, currency: str = "") -> dict:
    """
    Flatten the nested ratio dict from run_analysis()["latest"]
    into a card-ready structure for the intelligence endpoint.
    """
    if not latest:
        return {}

    prof = latest.get("profitability") or {}
    liq  = latest.get("liquidity")     or {}
    lev  = latest.get("leverage")      or {}
    eff  = latest.get("efficiency")    or {}

    gm   = _r2(prof.get("gross_margin_pct"))
    nm   = _r2(prof.get("net_margin_pct"))
    om   = _r2(prof.get("operating_margin_pct"))
    cr   = _r2(liq.get("current_ratio"))
    qr   = _r2(liq.get("quick_ratio"))
    wc   = _r2(liq.get("working_capital"))
    de   = _r2(lev.get("debt_to_equity"))
    tl   = _r2(lev.get("total_liabilities"))
    ta_val = (_r2(lev.get("total_equity")) or 0) + (_r2(tl) or 0)
    dr   = _r2(tl / ta_val * 100) if ta_val and tl else None  # debt ratio %
    it   = _r2(eff.get("inventory_turnover"))
    dso  = _r2(eff.get("dso_days"))
    ccc  = _r2(eff.get("ccc_days"))

    return {
        "profitability": {
            "gross_margin_pct":     {"value": gm,  "status": _status(gm,  good_above=40, warn_above=20),  "unit": "%"},
            "net_margin_pct":       {"value": nm,  "status": _status(nm,  good_above=10, warn_above=3),   "unit": "%"},
            "operating_margin_pct": {"value": om,  "status": _status(om,  good_above=15, warn_above=5),   "unit": "%"},
        },
        "liquidity": {
            "current_ratio":  {"value": cr,  "status": _status(cr,  good_above=1.5, warn_below=1.0), "unit": "x"},
            "quick_ratio":    {"value": qr,  "status": _status(qr,  good_above=1.0, warn_below=0.7), "unit": "x"},
            "working_capital":{"value": wc,  "status": "good" if (wc or 0) > 0 else "risk",          "unit": currency},
        },
        "leverage": {
            "debt_ratio_pct":   {"value": dr,  "status": _status(dr,  good_below=40, warn_above=70),  "unit": "%"},
            "debt_to_equity":   {"value": de,  "status": _status(de,  good_below=1.0, warn_above=2.0),"unit": "x"},
        },
        "efficiency": {
            "inventory_turnover": {"value": it,  "status": _status(it,  good_above=4, warn_below=2),  "unit": "x"},
            "dso_days":           {"value": dso, "status": _status(dso, good_below=30, warn_above=60), "unit": "days"},
            "ccc_days":           {"value": ccc, "status": _status(ccc, good_below=45, warn_above=90), "unit": "days"},
        },
    }
