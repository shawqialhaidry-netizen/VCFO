"""
executive_engine.py — Phase 11
Executive Interpretation Engine.

Transforms analytical outputs into management-ready language.
Rules:
  - ZERO calculations — reads only from existing engine outputs
  - Returns i18n keys + structured data (no hardcoded text)
  - Every domain returns a consistent RatedBlock shape
  - Actions are concrete and prioritised

Output shape:
{
  "period":          str,
  "overall_status":  "excellent|good|warning|critical",
  "overall_key":     str,         # i18n key for main headline
  "overall_data":    dict,        # interpolation data
  "top_actions":     [Action],    # top 3 prioritised actions
  "domains": {
    "profitability": RatedBlock,
    "liquidity":     RatedBlock,
    "growth":        RatedBlock,
    "cost_control":  RatedBlock,
    "risk":          RatedBlock,
  }
}

RatedBlock = {
  "status":      "excellent|good|warning|critical",
  "headline_key": str,
  "data":         dict,
  "action_key":   str,
  "action_data":  dict,
  "icon":         str,
}

Action = {
  "priority": "immediate|near_term|monitor",
  "key":      str,
  "data":     dict,
  "domain":   str,
}
"""
from __future__ import annotations
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict): return default
        cur = cur.get(k, default)
        if cur is None: return default
    return cur

def _r1(v) -> Optional[float]:
    return round(float(v), 1) if v is not None else None

def _r2(v) -> Optional[float]:
    return round(float(v), 2) if v is not None else None

def _fmtK(v) -> str:
    if v is None: return "—"
    return f"{v/1000:.0f}K" if abs(v) >= 1000 else f"{v:.0f}"

def _status_order(s: str) -> int:
    return {"excellent": 0, "good": 1, "warning": 2, "critical": 3}.get(s, 2)

def _worst(*statuses: str) -> str:
    return max(statuses, key=_status_order)

def _block(status: str, headline_key: str, data: dict,
           action_key: str, action_data: dict, icon: str) -> dict:
    return {
        "status":       status,
        "headline_key": headline_key,
        "data":         data,
        "action_key":   action_key,
        "action_data":  action_data,
        "icon":         icon,
    }

def _action(priority: str, key: str, data: dict, domain: str) -> dict:
    return {"priority": priority, "key": key, "data": data, "domain": domain}


# ══════════════════════════════════════════════════════════════════════════════
#  A. Profitability
# ══════════════════════════════════════════════════════════════════════════════

def _exec_profitability(analysis: dict, adv: dict) -> tuple[dict, list]:
    """Interpret profitability in executive language."""
    nm  = _get(analysis, "latest", "profitability", "net_margin_pct") or 0
    gm  = _get(analysis, "latest", "profitability", "gross_margin_pct") or 0
    op  = _get(analysis, "latest", "profitability", "operating_margin_pct") or 0
    np_ = _get(analysis, "latest", "profitability", "net_profit") or 0
    dol = _get(adv, "profitability", "operating_leverage_dol") or 0
    inc = _get(adv, "profitability", "incremental_margin_pct") or 0
    avg_gm = _get(adv, "profitability", "avg_gross_margin_pct") or gm

    actions = []

    # Status thresholds
    if nm >= 15:
        status       = "excellent"
        headline_key = "exec_profit_excellent"
        action_key   = "exec_lang_margin_healthy"
    elif nm >= 8:
        status       = "good"
        headline_key = "exec_profit_good"
        action_key   = "exec_lang_margin_healthy"
    elif nm >= 3:
        status       = "warning"
        headline_key = "exec_profit_warning"
        action_key   = "exec_lang_margin_warning"
        actions.append(_action("near_term", "exec_lang_margin_warning", {}, "profitability"))
    else:
        status       = "critical"
        headline_key = "exec_profit_critical"
        action_key   = "exec_act_emergency_cost_review"
        actions.append(_action("immediate", "exec_act_emergency_cost_review",
                               {"margin": _r1(nm)}, "profitability"))

    # DOL: business language — no jargon
    if dol and dol > 3.0:
        actions.append(_action("monitor", "exec_lang_dol_risk", {}, "profitability"))

    # Incremental margin: simple opportunity message
    if inc and inc > 20 and status in ("good", "excellent"):
        actions.append(_action("near_term", "exec_lang_growth_strong", {}, "profitability"))

    data = {
        "nm":     _r1(nm),  "gm":     _r1(gm),
        "op":     _r1(op),  "np":     _fmtK(np_),
        "dol":    _r2(dol), "inc":    _r1(inc),
        "avg_gm": _r1(avg_gm),
    }
    return _block(status, headline_key, data, action_key, data, "💰"), actions


# ══════════════════════════════════════════════════════════════════════════════
#  B. Liquidity
# ══════════════════════════════════════════════════════════════════════════════

def _exec_liquidity(analysis: dict, adv: dict, cashflow: dict) -> tuple[dict, list]:
    """Interpret liquidity & cash position."""
    cr       = _get(analysis, "latest", "liquidity", "current_ratio") or 0
    qr       = _get(analysis, "latest", "liquidity", "quick_ratio")   or 0
    wc       = _get(analysis, "latest", "liquidity", "working_capital") or 0
    cash     = cashflow.get("cash_balance") or 0
    cf_ratio = _get(cashflow, "quality", "cash_conversion_ratio") or 0
    cf_qual  = _get(cashflow, "quality", "cash_conversion_quality") or "moderate"
    wc_dir   = _get(adv, "liquidity", "wc_direction") or "stable"
    burn     = cashflow.get("burn_rate") or 0
    runway   = cashflow.get("runway_months")

    actions = []

    # Cash conversion is primary executive signal
    if cf_ratio >= 1.0:
        cf_status = "excellent"
    elif cf_ratio >= 0.7:
        cf_status = "good"
    elif cf_ratio >= 0.4:
        cf_status = "warning"
    else:
        cf_status = "critical"

    # Current ratio supplement
    if cr >= 1.5:
        cr_status = "excellent"
    elif cr >= 1.0:
        cr_status = "good"
    elif cr >= 0.8:
        cr_status = "warning"
    else:
        cr_status = "critical"

    status = _worst(cf_status, cr_status)

    headline_map = {
        "excellent": "exec_liq_excellent",
        "good":      "exec_liq_good",
        "warning":   "exec_liq_warning",
        "critical":  "exec_liq_critical",
    }
    action_map = {
        "excellent": "exec_act_maintain_liquidity",
        "good":      "exec_act_monitor_wc",
        "warning":   "exec_act_accelerate_collections",
        "critical":  "exec_act_cash_emergency",
    }

    if status in ("warning", "critical"):
        actions.append(_action("near_term" if status == "warning" else "immediate",
                               action_map[status],
                               {"cr": _r2(cr), "cf_ratio": _r2(cf_ratio)},
                               "liquidity"))

    # Pass cr to action_data for good status too
    if status == "good":
        actions.append(_action("monitor", "exec_act_monitor_wc",
                               {"cr": _r2(cr)}, "liquidity"))

    if wc_dir == "deteriorating":
        actions.append(_action("monitor", "exec_act_wc_deteriorating",
                               {"wc": _fmtK(wc), "cr": _r2(cr)}, "liquidity"))

    if burn > 0 and runway is not None and runway < 6:
        actions.append(_action("immediate", "exec_act_cash_runway_low",
                               {"runway": _r1(runway), "burn": _fmtK(burn)},
                               "liquidity"))

    data = {
        "cr":       _r2(cr),    "qr":      _r2(qr),
        "wc":       _fmtK(wc),  "cash":    _fmtK(cash),
        "cf_ratio": _r2(cf_ratio), "cf_qual": cf_qual,
        "wc_dir":   wc_dir,
    }
    return _block(status, headline_map[status], data, action_map[status], data, "💧"), actions


# ══════════════════════════════════════════════════════════════════════════════
#  C. Growth
# ══════════════════════════════════════════════════════════════════════════════

def _exec_growth(analysis: dict, root_cause: dict) -> tuple[dict, list]:
    """Interpret revenue and profit growth trajectory."""
    trends    = analysis.get("trends") or {}
    rev_mom   = trends.get("revenue_mom_pct", [])
    np_mom    = trends.get("net_profit_mom_pct", [])
    yoy_rev   = trends.get("yoy_revenue_pct")
    yoy_np    = trends.get("yoy_net_profit_pct")
    rev_trend = _get(root_cause, "revenue", "trend") or "stable"
    np_trend  = _get(root_cause, "profit",  "trend") or "stable"

    # Last MoM values
    last_rev_mom = next((v for v in reversed(rev_mom) if v is not None), None)
    last_np_mom  = next((v for v in reversed(np_mom)  if v is not None), None)

    actions = []

    # Combined growth score
    rev_good = rev_trend == "improving" or (last_rev_mom or 0) > 0
    np_good  = np_trend  == "improving" or (last_np_mom  or 0) > 0
    yoy_good = (yoy_rev  or 0) > 0

    if rev_good and np_good and yoy_good:
        status       = "excellent" if (yoy_rev or 0) > 10 else "good"
        headline_key = "exec_growth_excellent" if status == "excellent" else "exec_growth_good"
        action_key   = "exec_lang_growth_strong"
        actions.append(_action("monitor", "exec_lang_growth_strong", {}, "growth"))
    elif rev_good or np_good:
        status       = "good"
        headline_key = "exec_growth_partial"
        action_key   = "exec_lang_growth_strong"
    elif rev_trend == "deteriorating":
        status       = "critical" if (last_rev_mom or 0) < -20 else "warning"
        headline_key = "exec_growth_declining"
        action_key   = "exec_lang_growth_stalled"
        actions.append(_action(
            "immediate" if status == "critical" else "near_term",
            "exec_lang_growth_stalled", {}, "growth"
        ))
    else:
        status       = "warning"
        headline_key = "exec_growth_stagnant"
        action_key   = "exec_lang_growth_stalled"
        actions.append(_action("near_term", "exec_lang_growth_stalled", {}, "growth"))

    # YoY: business language
    if (yoy_rev or 0) > 15 and status in ("good", "excellent"):
        actions.append(_action("monitor", "exec_lang_yoy_positive", {}, "growth"))

    data = {
        "rev_mom":  _r1(last_rev_mom or 0),
        "np_mom":   _r1(last_np_mom  or 0),
        "yoy_rev":  _r1(yoy_rev      or 0),
        "yoy_np":   _r1(yoy_np       or 0),
        "rev_trend": rev_trend,
        "np_trend":  np_trend,
    }
    return _block(status, headline_key, data, action_key, data, "📈"), actions


# ══════════════════════════════════════════════════════════════════════════════
#  D. Cost Control
# ══════════════════════════════════════════════════════════════════════════════

def _exec_cost_control(adv: dict, root_cause: dict) -> tuple[dict, list]:
    """Interpret cost structure from a management perspective."""
    cs_risk     = adv.get("risk", {}).get("cost_structure", {})
    cogs_pct    = cs_risk.get("latest_cogs_pct", 0) or 0
    opex_pct    = cs_risk.get("latest_opex_pct", 0) or 0
    avg_cogs    = cs_risk.get("avg_cogs_pct", cogs_pct) or cogs_pct
    avg_opex    = cs_risk.get("avg_opex_pct", opex_pct) or opex_pct
    cs_type     = cs_risk.get("cost_structure_type", "balanced")
    rc_cost_trend = _get(root_cause, "cost_structure", "trend") or "stable"
    rc_cost_key   = _get(root_cause, "cost_structure", "key") or ""

    # Thresholds: total cost load = cogs + opex
    total_cost_pct = cogs_pct + opex_pct
    trend_direction = rc_cost_trend

    actions = []

    if trend_direction == "improving" and total_cost_pct < 82:
        status       = "good"
        headline_key = "exec_cost_improving"
        action_key   = "exec_lang_cost_improving"
        actions.append(_action("monitor", "exec_lang_cost_improving", {}, "cost_control"))
    elif trend_direction == "deteriorating":
        if total_cost_pct > 92:
            status       = "critical"
            headline_key = "exec_cost_critical"
            action_key   = "exec_lang_cost_pressure"
            actions.append(_action("immediate", "exec_lang_cost_pressure", {}, "cost_control"))
        else:
            status       = "warning"
            headline_key = "exec_cost_warning"
            action_key   = "exec_lang_cost_pressure"
            actions.append(_action("near_term", "exec_lang_cost_pressure", {}, "cost_control"))
    else:
        status       = "good" if total_cost_pct < 87 else "warning"
        headline_key = "exec_cost_stable"
        action_key   = "exec_lang_cost_improving"

    # COGS vs historical: business language
    if cogs_pct > avg_cogs + 2:
        actions.append(_action("near_term", "exec_lang_cogs_worsened", {}, "cost_control"))
    elif cogs_pct < avg_cogs - 1:
        actions.append(_action("monitor", "exec_lang_cogs_improved", {}, "cost_control"))

    data = {
        "cogs":      _r1(cogs_pct),  "opex":     _r1(opex_pct),
        "avg_cogs":  _r1(avg_cogs),  "avg_opex": _r1(avg_opex),
        "total":     _r1(total_cost_pct), "type": cs_type,
    }
    return _block(status, headline_key, data, action_key, data, "⚙️"), actions


# ══════════════════════════════════════════════════════════════════════════════
#  E. Risk
# ══════════════════════════════════════════════════════════════════════════════

def _exec_risk(adv: dict, cashflow: dict, root_cause: dict) -> tuple[dict, list]:
    """Interpret operational and financial risk for management."""
    risk_rating  = adv.get("risk", {}).get("risk_rating", "low")
    risk_factors = adv.get("risk", {}).get("risk_factor_count", 0)
    earn_cons    = _get(adv, "risk", "earnings_consistency", "consistency_score") or 100
    rev_stab     = _get(adv, "risk", "revenue_stability", "stability_score") or 100
    gm_std       = _get(adv, "risk", "margin_volatility", "gross_margin_std_dev") or 0
    dso          = _get(adv, "efficiency", "dso_days") or 0
    ccc          = _get(adv, "efficiency", "ccc_days") or 0
    burn         = cashflow.get("burn_rate") or 0
    runway       = cashflow.get("runway_months")
    rc_severity  = root_cause.get("overall_severity", "low")

    actions = []

    # Map risk_rating to executive status
    status_map = {"low": "good", "medium": "warning",
                  "high": "warning", "critical": "critical"}
    status = status_map.get(risk_rating, "warning")

    # Escalate if RC severity is high
    if rc_severity in ("high", "critical"):
        status = _worst(status, "warning")

    headline_map = {
        "excellent": "exec_risk_excellent",
        "good":      "exec_risk_good",
        "warning":   "exec_risk_warning",
        "critical":  "exec_risk_critical",
    }
    action_map = {
        "excellent": "exec_act_risk_maintain",
        "good":      "exec_act_risk_monitor",
        "warning":   "exec_act_risk_mitigation",
        "critical":  "exec_act_risk_immediate",
    }

    if status in ("warning", "critical"):
        actions.append(_action(
            "immediate" if status == "critical" else "near_term",
            "exec_lang_risk_elevated", {}, "risk"
        ))
    else:
        actions.append(_action("monitor", "exec_lang_risk_low", {}, "risk"))

    # Receivables: business language
    if dso > 45:
        actions.append(_action("near_term", "exec_lang_receivables_slow", {}, "risk"))
    elif dso > 30:
        actions.append(_action("monitor", "exec_lang_receivables_slow", {}, "risk"))

    # Earnings consistency: business language
    if earn_cons < 60:
        actions.append(_action("near_term", "exec_lang_risk_elevated", {}, "risk"))

    data = {
        "risk_rating":  risk_rating,
        "risk_factors": risk_factors,
        "earn_cons":    round(earn_cons),
        "rev_stab":     round(rev_stab),
        "gm_std":       _r1(gm_std),
        "dso":          _r1(dso),
        "ccc":          _r1(ccc),
        "burn":         _fmtK(burn) if burn > 0 else "0",
        "runway":       _r1(runway) if runway else "N/A",
    }
    return _block(status, headline_map[status], data, action_map[status], data, "⚡"), actions


# ══════════════════════════════════════════════════════════════════════════════
#  Overall + Top Actions
# ══════════════════════════════════════════════════════════════════════════════

def _build_overall(domains: dict, all_actions: list, period: str) -> tuple[str, str, dict, list]:
    """Compute overall status and select top 3 prioritised actions."""
    statuses = [d["status"] for d in domains.values()]
    overall  = _worst(*statuses)

    # Overall headline key
    headline_map = {
        "excellent": "exec_overall_excellent",
        "good":      "exec_overall_good",
        "warning":   "exec_overall_warning",
        "critical":  "exec_overall_critical",
    }
    headline_key = headline_map[overall]

    # Data for headline interpolation
    good_count = statuses.count("good") + statuses.count("excellent")
    warn_count = statuses.count("warning") + statuses.count("critical")

    data = {
        "period":     period,
        "good_count": good_count,
        "warn_count": warn_count,
        "domains":    len(domains),
    }

    # Prioritise actions: immediate > near_term > monitor
    priority_order = {"immediate": 0, "near_term": 1, "monitor": 2}
    sorted_actions = sorted(all_actions,
                            key=lambda a: priority_order.get(a["priority"], 2))

    # Deduplicate by key, take top 3
    seen, top3 = set(), []
    for act in sorted_actions:
        if act["key"] not in seen:
            seen.add(act["key"])
            top3.append(act)
        if len(top3) == 3:
            break

    return overall, headline_key, data, top3


# ══════════════════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def build_executive_summary(
    analysis:       dict,
    advanced_metrics: dict,
    cashflow:       dict,
    root_cause:     dict,
) -> dict:
    """
    Phase 11 Executive Interpretation Engine.

    Reads ONLY from existing engine outputs — zero calculations.
    Returns structured executive summary with i18n keys.
    """
    period   = (analysis.get("periods") or [""])[-1]
    all_acts = []

    # ── Run all 5 domain interpreters ─────────────────────────────────────────
    prof_block, prof_acts = _exec_profitability(analysis, advanced_metrics)
    liq_block,  liq_acts  = _exec_liquidity(analysis, advanced_metrics, cashflow)
    grow_block, grow_acts = _exec_growth(analysis, root_cause)
    cost_block, cost_acts = _exec_cost_control(advanced_metrics, root_cause)
    risk_block, risk_acts = _exec_risk(advanced_metrics, cashflow, root_cause)

    all_acts.extend(prof_acts + liq_acts + grow_acts + cost_acts + risk_acts)

    domains = {
        "profitability": prof_block,
        "liquidity":     liq_block,
        "growth":        grow_block,
        "cost_control":  cost_block,
        "risk":          risk_block,
    }

    # ── Overall summary ───────────────────────────────────────────────────────
    overall, overall_key, overall_data, top3 = _build_overall(domains, all_acts, period)

    return {
        "period":         period,
        "overall_status": overall,
        "overall_key":    overall_key,
        "overall_data":   overall_data,
        "top_actions":    top3,
        "domains":        domains,
    }
