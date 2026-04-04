"""
ai_cfo_engine.py — AI CFO Decision Engine

Transforms financial analysis output into prioritized, actionable decisions
for each company and each branch.

Design rules:
  - Deterministic threshold logic only — no randomness, no ML inference
  - Reads ONLY from analysis_engine + branch_comparison output (no recalculation)
  - Does NOT duplicate decision_engine.py (company-level warnings/recs)
    or cfo_decision_engine.py (domain-scored CFO actions)
  - Adds: action_type taxonomy, risk_score 0-100, branch-level decisions,
    impact estimation, and structured priority ranking

Action types:
  COST_REDUCTION  — expense ratio too high, margins being compressed
  SCALE_UP        — strong margin + growth momentum, expand capacity
  OPTIMIZE        — mid-range performance, targeted efficiency improvements
  RESTRUCTURE     — negative or near-zero margin, cost model broken
  CLOSE           — persistent losses + high expense ratio, no recovery signal
  MONITOR         — marginal performance, watch-and-wait

Risk score (0-100):
  0  = no risk    (strong positive on all dimensions)
  100 = maximum risk (losses, high expense, declining revenue)
"""
from __future__ import annotations
from typing import Any, Optional

# Wave 2B: template keys for causal realization (no English prose on this path)
_AI_CFO_TOPIC: dict[str, str] = {
    "COST_REDUCTION": "cost",
    "SCALE_UP": "growth",
    "OPTIMIZE": "efficiency",
    "RESTRUCTURE": "risk",
    "CLOSE": "risk",
    "MONITOR": "efficiency",
}

# ── Threshold constants — single source of truth ─────────────────────────────

class Th:
    # Margin thresholds (%)
    MARGIN_STRONG       =  20.0   # → consider SCALE_UP
    MARGIN_HEALTHY      =  10.0   # → OPTIMIZE
    MARGIN_WEAK         =   5.0   # → COST_REDUCTION
    MARGIN_CRITICAL     =   0.0   # → RESTRUCTURE
    MARGIN_LOSS         = -5.0    # → CLOSE signal

    # Expense ratio thresholds (%)
    EXP_CONTROLLED      =  50.0   # healthy
    EXP_ELEVATED        =  65.0   # → OPTIMIZE
    EXP_HIGH            =  75.0   # → COST_REDUCTION
    EXP_CRITICAL        =  90.0   # → RESTRUCTURE/CLOSE

    # Revenue MoM growth (%)
    GROWTH_STRONG       =  10.0   # → SCALE_UP signal
    GROWTH_POSITIVE     =   3.0   # → healthy
    GROWTH_STAGNANT     =  -3.0   # → OPTIMIZE
    GROWTH_DECLINING    = -10.0   # → risk flag

    # Risk score weights (must sum to 100)
    W_MARGIN            =  40
    W_EXPENSE_RATIO     =  30
    W_GROWTH            =  20
    W_LOSS_FLAG         =  10


# ── Helpers ───────────────────────────────────────────────────────────────────

def _g(d: dict, *keys, default=None):
    """Safe nested get."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
        if cur is None:
            return default
    return cur


def _lv(series: list) -> Optional[float]:
    """Last non-None value in a series."""
    if not series:
        return None
    for v in reversed(series):
        if v is not None:
            return v
    return None


def _compute_risk_score(
    net_margin:    Optional[float],
    expense_ratio: Optional[float],
    revenue_mom:   Optional[float],
    is_loss:       bool,
) -> int:
    """
    Deterministic risk score 0-100.
    Higher = more risk. Each component scored 0-100 then weighted.
    """
    # Margin component (0=strong, 100=deep loss)
    if net_margin is None:
        m_score = 50   # unknown → neutral
    elif net_margin >= Th.MARGIN_STRONG:
        m_score = 0
    elif net_margin >= Th.MARGIN_HEALTHY:
        m_score = 20
    elif net_margin >= Th.MARGIN_WEAK:
        m_score = 45
    elif net_margin >= Th.MARGIN_CRITICAL:
        m_score = 70
    else:
        m_score = 95   # loss territory

    # Expense ratio component (0=controlled, 100=critical)
    if expense_ratio is None:
        e_score = 30
    elif expense_ratio <= Th.EXP_CONTROLLED:
        e_score = 0
    elif expense_ratio <= Th.EXP_ELEVATED:
        e_score = 25
    elif expense_ratio <= Th.EXP_HIGH:
        e_score = 55
    elif expense_ratio <= Th.EXP_CRITICAL:
        e_score = 80
    else:
        e_score = 100

    # Revenue growth component (0=growing fast, 100=declining)
    if revenue_mom is None:
        g_score = 40
    elif revenue_mom >= Th.GROWTH_STRONG:
        g_score = 0
    elif revenue_mom >= Th.GROWTH_POSITIVE:
        g_score = 15
    elif revenue_mom >= Th.GROWTH_STAGNANT:
        g_score = 40
    elif revenue_mom >= Th.GROWTH_DECLINING:
        g_score = 70
    else:
        g_score = 95

    # Loss flag component
    l_score = 100 if is_loss else 0

    raw = (
        m_score * Th.W_MARGIN +
        e_score * Th.W_EXPENSE_RATIO +
        g_score * Th.W_GROWTH +
        l_score * Th.W_LOSS_FLAG
    ) / 100

    return min(100, max(0, round(raw)))


def _priority_label(risk_score: int) -> str:
    if risk_score >= 65:
        return "HIGH"
    elif risk_score >= 35:
        return "MEDIUM"
    return "LOW"


def _priority_to_severity(priority: str) -> str:
    p = (priority or "LOW").upper()
    if p == "HIGH":
        return "high"
    if p == "MEDIUM":
        return "medium"
    return "low"


def _causal_item_for_ai_decision(decision: dict) -> dict[str, Any]:
    """Structured causal row for advisor/board (no realization here)."""
    action_type = str(decision.get("action_type") or "OPTIMIZE")
    topic = _AI_CFO_TOPIC.get(action_type, "efficiency")
    fin = decision.get("financials") or {}
    nm = fin.get("net_margin_pct")
    er = fin.get("expense_ratio")
    mom = fin.get("revenue_mom_pct")
    rev = fin.get("revenue")
    is_loss = bool(fin.get("is_loss"))
    params: dict[str, Any] = {
        "action_type": action_type,
        "risk_score": decision.get("risk_score"),
        "priority": decision.get("priority"),
        "net_margin_pct": nm,
        "expense_ratio": er,
        "revenue_mom_pct": mom,
        "revenue": rev,
        "is_loss": is_loss,
    }
    params = {k: v for k, v in sorted(params.items()) if v is not None}
    tid = f"ai_cfo.decision.{action_type}"
    ent = str(decision.get("entity") or "entity").replace(" ", "_")[:48]
    et = str(decision.get("entity_type") or "company")
    per = str(decision.get("period") or "")
    cid = f"ai_cfo:{et}:{ent}:{per}:{action_type}"
    sm = {k: v for k, v in {
        "net_margin_pct": nm,
        "expense_ratio": er,
        "revenue_mom_pct": mom,
        "revenue": rev,
        "risk_score": decision.get("risk_score"),
    }.items() if v is not None}
    sev = _priority_to_severity(str(decision.get("priority") or "LOW"))
    return {
        "id": cid,
        "topic": topic,
        "severity": sev,
        "source": "ai_cfo_heuristic",
        "change": {"key": f"{tid}.change", "params": dict(params)},
        "cause": {"key": f"{tid}.cause", "params": dict(params)},
        "action": {"key": f"{tid}.action", "params": dict(params)},
        "evidence": {
            "source_metrics": sm,
            "template_ids": [tid],
            "merged_from": [action_type],
        },
    }


def _choose_action_type(
    net_margin:    Optional[float],
    expense_ratio: Optional[float],
    revenue_mom:   Optional[float],
    is_loss:       bool,
) -> str:
    """
    Deterministic action type from financial thresholds.
    Maps directly to the combination of margin + expense + growth signals.
    """
    nm  = net_margin    if net_margin    is not None else 0.0
    er  = expense_ratio if expense_ratio is not None else 50.0
    mom = revenue_mom   if revenue_mom   is not None else 0.0

    # CLOSE: persistent loss AND cost structure broken
    if is_loss and er >= Th.EXP_CRITICAL:
        return "CLOSE"

    # RESTRUCTURE: loss or near-zero margin + high expenses
    if nm < Th.MARGIN_CRITICAL or (nm < Th.MARGIN_WEAK and er >= Th.EXP_HIGH):
        return "RESTRUCTURE"

    # SCALE_UP: strong margin AND positive growth
    if nm >= Th.MARGIN_STRONG and mom >= Th.GROWTH_POSITIVE:
        return "SCALE_UP"

    # COST_REDUCTION: expenses eating margin
    if er >= Th.EXP_HIGH or (er >= Th.EXP_ELEVATED and nm < Th.MARGIN_HEALTHY):
        return "COST_REDUCTION"

    # MONITOR: declining growth, otherwise stable
    if mom <= Th.GROWTH_DECLINING:
        return "MONITOR"

    # Default: OPTIMIZE (mid-range, targeted improvements possible)
    return "OPTIMIZE"


def _estimate_impact(action_type: str, nm: float, er: float, rev: float) -> dict:
    """
    Estimate financial impact of recommended action.
    Pure arithmetic on known values — no forecasting model.
    """
    if action_type == "COST_REDUCTION":
        # Reducing expense ratio by 5pp improves net margin
        target_er     = max(er - 5.0, Th.EXP_CONTROLLED)
        margin_uplift = (er - target_er) * (rev / 100.0) if rev else 0
        return {
            "action":      "Reduce expense ratio by ~5pp",
            "target_er":   round(target_er, 1),
            "profit_uplift_estimate": round(margin_uplift, 0),
            "confidence":  "medium",
        }
    elif action_type == "SCALE_UP":
        # At current margin, 10% revenue increase → incremental profit
        incremental_rev    = rev * 0.10
        incremental_profit = incremental_rev * (nm / 100.0)
        return {
            "action":               "Grow revenue by 10%",
            "incremental_revenue":  round(incremental_rev, 0),
            "incremental_profit":   round(incremental_profit, 0),
            "confidence":           "medium",
        }
    elif action_type == "RESTRUCTURE":
        # Bringing expense ratio to 70% from current
        target_er     = min(er, 70.0)
        margin_uplift = max(0.0, (er - target_er)) * (rev / 100.0) if rev else 0
        return {
            "action":               "Restructure cost base to target ER ≤ 70%",
            "cost_reduction_target": round(margin_uplift, 0),
            "confidence":           "low",   # restructuring outcome uncertain
        }
    elif action_type == "CLOSE":
        return {
            "action":     "Assess closure or divestiture",
            "current_loss": round(abs(nm / 100.0 * rev) if rev else 0, 0),
            "confidence": "high",   # loss is confirmed
        }
    elif action_type == "OPTIMIZE":
        target_er     = max(er - 3.0, Th.EXP_CONTROLLED)
        margin_uplift = (er - target_er) * (rev / 100.0) if rev else 0
        return {
            "action":               "Optimize operations — target ER reduction of 3pp",
            "profit_uplift_estimate": round(margin_uplift, 0),
            "confidence":           "medium",
        }
    else:  # MONITOR
        return {
            "action":     "Monitor trend for 2 more periods before action",
            "confidence": "low",
        }


def _build_decision(
    name:          str,
    net_margin:    Optional[float],
    expense_ratio: Optional[float],
    revenue_mom:   Optional[float],
    revenue:       Optional[float],
    period:        str,
    entity_type:   str,   # "company" | "branch"
) -> dict:
    """
    Build a single decision object for one entity (company or branch).
    All logic is deterministic — threshold-based.
    """
    nm      = net_margin    if net_margin    is not None else 0.0
    er      = expense_ratio if expense_ratio is not None else 50.0
    mom     = revenue_mom   if revenue_mom   is not None else 0.0
    rev     = revenue       if revenue       is not None else 0.0
    is_loss = nm < 0.0

    risk_score  = _compute_risk_score(net_margin, expense_ratio, revenue_mom, is_loss)
    action_type = _choose_action_type(net_margin, expense_ratio, revenue_mom, is_loss)
    priority    = _priority_label(risk_score)
    impact      = _estimate_impact(action_type, nm, er, rev)

    # Build rationale from the specific thresholds that triggered this decision
    rationale_parts = []
    if net_margin is not None:
        if nm < Th.MARGIN_CRITICAL:
            rationale_parts.append(f"net margin {nm:.1f}% (loss territory)")
        elif nm < Th.MARGIN_WEAK:
            rationale_parts.append(f"net margin {nm:.1f}% (below {Th.MARGIN_WEAK}% threshold)")
        elif nm >= Th.MARGIN_STRONG:
            rationale_parts.append(f"net margin {nm:.1f}% (above {Th.MARGIN_STRONG}% target)")
    if expense_ratio is not None:
        if er >= Th.EXP_CRITICAL:
            rationale_parts.append(f"expense ratio {er:.1f}% (critical — above {Th.EXP_CRITICAL}%)")
        elif er >= Th.EXP_HIGH:
            rationale_parts.append(f"expense ratio {er:.1f}% (high — above {Th.EXP_HIGH}%)")
        elif er >= Th.EXP_ELEVATED:
            rationale_parts.append(f"expense ratio {er:.1f}% (elevated)")
    if revenue_mom is not None:
        if mom >= Th.GROWTH_STRONG:
            rationale_parts.append(f"revenue MoM {mom:+.1f}% (strong growth)")
        elif mom <= Th.GROWTH_DECLINING:
            rationale_parts.append(f"revenue MoM {mom:+.1f}% (declining)")

    rationale = (
        "; ".join(rationale_parts)
        if rationale_parts
        else "No significant threshold breach detected"
    )

    return {
        "entity":       name,
        "entity_type":  entity_type,
        "period":       period,
        "action_type":  action_type,
        "priority":     priority,
        "risk_score":   risk_score,
        "rationale":    rationale,
        "financials": {
            "net_margin_pct":  round(nm,  2),
            "expense_ratio":   round(er,  2) if expense_ratio is not None else None,
            "revenue_mom_pct": round(mom, 2) if revenue_mom is not None else None,
            "revenue":         round(rev, 0),
            "is_loss":         is_loss,
        },
        "impact":       impact,
    }


# ── Company-level decision ────────────────────────────────────────────────────

def build_company_decision(
    company_name:   str,
    analysis:       dict,   # output of run_analysis()
    snapshot:       dict,   # quick_metrics from executive endpoint or board report
    period:         str,
) -> dict:
    """
    Build a decision for the consolidated company entity.

    Reads from:
      - analysis["latest"]["profitability"]["net_margin_pct"]
      - analysis["latest"]["profitability"]["gross_margin_pct"]
      - snapshot["expense_ratio"]
      - analysis["trends"]["revenue"]["mom_pct"]  (last value)

    Does NOT recalculate any of these values.
    """
    latest   = analysis.get("latest", {})
    prof     = latest.get("profitability", {})
    trends   = analysis.get("trends", {})

    nm       = prof.get("net_margin_pct")
    er       = snapshot.get("expense_ratio")
    rev      = snapshot.get("revenue")
    mom_list = trends.get("revenue", {}).get("mom_pct", []) or []
    mom      = _lv(mom_list)

    decision = _build_decision(
        name          = company_name,
        net_margin    = nm,
        expense_ratio = er,
        revenue_mom   = mom,
        revenue       = rev,
        period        = period,
        entity_type   = "company",
    )

    return {
        "decisions":  [decision],
        "causal_items": [_causal_item_for_ai_decision(decision)],
        "risk_score": decision["risk_score"],
        "priority":   decision["priority"],
    }


# ── Branch-level decisions ────────────────────────────────────────────────────

def build_branch_decisions(
    branch_ranking: list[dict],   # from branch_comparison["ranking"]
    period:         str,
) -> dict:
    """
    Build a decision for each branch.

    Reads from branch_comparison ranking items:
      - branch["branch_name"]
      - branch["net_margin"]        (or net_margin_pct)
      - branch["expense_ratio"]     (from kpis sub-dict if present)
      - branch["mom_revenue_pct"]   (or revenue_mom_pct)
      - branch["revenue"]

    Does NOT recalculate any financial values.
    """
    decisions   = []
    high_risk   = []

    for branch in (branch_ranking or []):
        name    = branch.get("branch_name") or branch.get("name") or "Unknown"
        kpis    = branch.get("kpis", {})

        nm      = branch.get("net_margin") or branch.get("net_margin_pct") or kpis.get("net_margin_pct")
        er      = branch.get("expense_ratio") or kpis.get("expense_ratio")
        rev     = branch.get("revenue") or kpis.get("revenue")
        mom     = (branch.get("mom_revenue_pct") or
                   branch.get("revenue_mom_pct") or
                   kpis.get("revenue_mom_pct"))

        dec = _build_decision(
            name          = name,
            net_margin    = nm,
            expense_ratio = er,
            revenue_mom   = mom,
            revenue       = rev,
            period        = period,
            entity_type   = "branch",
        )
        decisions.append(dec)
        if dec["priority"] == "HIGH":
            high_risk.append(name)

    # Sort by risk_score descending — highest risk first
    decisions.sort(key=lambda d: -d["risk_score"])
    branch_causal = [_causal_item_for_ai_decision(d) for d in decisions]

    return {
        "decisions":        decisions,
        "causal_items":     branch_causal,
        "branch_count":     len(decisions),
        "high_risk_count":  len(high_risk),
        "high_risk_branches": high_risk,
    }


# ── Combined entry point ──────────────────────────────────────────────────────

def build_cfo_decision_pack(
    company_name:   str,
    analysis:       dict,      # run_analysis() output
    snapshot:       dict,      # quick_metrics / board_report snapshot
    branch_ranking: list[dict],# branch_comparison["ranking"]
    period:         str,
) -> dict:
    """
    Build the full CFO decision pack for one company:
      - Company-level decision
      - Per-branch decisions
      - Aggregated risk summary

    Input: only existing analysis output — no new calculations.
    Output:
    {
      "company":   { decisions, risk_score, priority },
      "branches":  { decisions, branch_count, high_risk_count },
      "summary": {
        "overall_risk_score": int,
        "overall_priority":   str,
        "top_action":         str,
        "period":             str,
      }
    }
    """
    company_pack = build_company_decision(company_name, analysis, snapshot, period)
    branch_pack  = build_branch_decisions(branch_ranking, period)

    # Overall risk = max of company + all branches
    all_scores = [company_pack["risk_score"]] + [
        d["risk_score"] for d in branch_pack["decisions"]
    ]
    overall_risk = max(all_scores) if all_scores else 0
    overall_priority = _priority_label(overall_risk)
    top_action = (
        company_pack["decisions"][0]["action_type"]
        if company_pack["decisions"] else "MONITOR"
    )

    merged_causal = list(company_pack.get("causal_items") or [])
    merged_causal.extend(branch_pack.get("causal_items") or [])

    return {
        "company":  company_pack,
        "branches": branch_pack,
        "causal_items": merged_causal,
        "summary": {
            "overall_risk_score": overall_risk,
            "overall_priority":   overall_priority,
            "top_action":         top_action,
            "period":             period,
            "branch_count":       branch_pack["branch_count"],
            "high_risk_branches": branch_pack["high_risk_branches"],
        },
    }
