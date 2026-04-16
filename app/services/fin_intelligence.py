"""
fin_intelligence.py — Phase 21 / Phase 3

CANONICAL product intelligence (ratios, trends, anomalies, health_score_v2) for all
executive-aligned endpoints. Every product surface must use this on the same
scoped ``windowed`` statements as GET /executive.

``intelligence_engine.run_intelligence`` is legacy-only (GET /{company_id} aggregate)
and must not be treated as a second product brain.
"""
from __future__ import annotations
from app.services.financial_ratios import extract_ratios
from app.services.trend_analysis   import build_trends
from app.services.anomaly_detector  import detect_anomalies


# ── Health score v2 ───────────────────────────────────────────────────────────

def _health_score_v2(ratios: dict, trends: dict, anomalies: list) -> int:
    """
    0–100 composite score — single source of truth (Phase 23 recalibrated).

    Calibration: SME financial performance reality.
    Goal: good performance != perfect, no crisis != excellent.

    Components:
      Profitability  30 pts — net margin (15), gross margin (15)
      Liquidity      25 pts — current ratio (15), quick ratio (10)
      Trend          25 pts — revenue direction (13), NP direction (12)
      Anomaly deductions (20 max)

    Recalibrated vs prior version:
      Net Margin:    >=12% for full 15pts  (was >=15%)
      Gross Margin:  >=38% for full 15pts  (was >=40%)
      Current Ratio: >=1.8x for full 15pts (was >=2.0x)
      CR mid tier:   >=1.2x -> 11pts       (was >=1.5x)
      Quick Ratio:   >=0.9x for full 10pts (was >=1.0x)
      Trend stable:  +8/+7 pts             (was +7/+6)
    """
    score = 0

    # ── Profitability (30) ────────────────────────────────────────────────────
    prof = ratios.get("profitability", {})
    nm   = (prof.get("net_margin_pct")  or {}).get("value")
    gm   = (prof.get("gross_margin_pct") or {}).get("value")

    if nm is not None:
        if nm >= 12:   score += 15   # recal: was >=15
        elif nm >= 7:  score += 10   # recal: was >=8
        elif nm >= 3:  score += 5
        elif nm >= 0:  score += 2

    if gm is not None:
        if gm >= 38:   score += 15   # recal: was >=40
        elif gm >= 25: score += 10
        elif gm >= 15: score += 5

    # ── Liquidity (25) ────────────────────────────────────────────────────────
    liq = ratios.get("liquidity", {})
    cr  = (liq.get("current_ratio") or {}).get("value")
    qr  = (liq.get("quick_ratio")   or {}).get("value")

    if cr is not None:
        if cr >= 1.8:  score += 15   # recal: was >=2.0
        elif cr >= 1.2:score += 11   # recal: was >=1.5
        elif cr >= 1.0:score += 6
        elif cr > 0:   score += 2

    if qr is not None:
        if qr >= 0.9:  score += 10   # recal: was >=1.0
        elif qr >= 0.6:score += 6    # recal: was >=0.7
        elif qr > 0:   score += 2

    # ── Trend (25) ────────────────────────────────────────────────────────────
    rev_dir = (trends.get("revenue")    or {}).get("direction", "insufficient_data")
    np_dir  = (trends.get("net_profit") or {}).get("direction", "insufficient_data")

    if rev_dir == "up":       score += 13
    elif rev_dir == "stable": score += 8    # recal: was +7
    elif rev_dir == "down":   score += 0

    if np_dir == "up":        score += 12
    elif np_dir == "stable":  score += 7    # recal: was +6
    elif np_dir == "down":    score += 0

    # ── Anomaly deductions (20 max) ───────────────────────────────────────────
    deductions = {"critical": 8, "high": 5, "medium": 2}
    total_ded = min(20, sum(deductions.get(a.get("severity", "medium"), 2)
                             for a in anomalies))
    score = max(0, score - total_ded)

    return min(100, max(0, score))


def _status(score: int) -> str:
    if score >= 80: return "excellent"
    if score >= 60: return "good"
    if score >= 40: return "warning"
    return "risk"


# ── Public API ────────────────────────────────────────────────────────────────

def build_intelligence(
    analysis:      dict,
    annual_layer:  dict,
    currency:      str = "",
) -> dict:
    """
    Build the Phase 21 intelligence response.

    Args:
        analysis:     output of run_analysis()
        annual_layer: output of build_annual_layer()
        currency:     company currency string

    Returns:
        { ratios, trends, anomalies, health_score_v2, status }
    """
    latest         = analysis.get("latest") or {}
    analysis_trends= analysis.get("trends") or {}

    ratios    = extract_ratios(latest, currency)
    trends    = build_trends(analysis_trends, annual_layer)
    anomalies = detect_anomalies(analysis_trends, annual_layer)
    score     = _health_score_v2(ratios, trends, anomalies)

    return {
        "ratios":          ratios,
        "trends":          trends,
        "anomalies":       anomalies,
        "anomaly_count":   len(anomalies),
        "health_score_v2": score,
        "status":          _status(score),
    }
def build_branch_intelligence(branches: list[dict]) -> dict:
    """
    Builds:
    - classifications (leaders / weakest / growth / cost)
    - company insights
    - prevents duplicate dominance
    """

    if not branches:
        return {}

    # ── Sorting layers ─────────────────────────────────
    by_revenue = sorted(branches, key=lambda x: x.get("revenue", 0), reverse=True)
    by_margin  = sorted(branches, key=lambda x: x.get("net_margin", 0), reverse=True)
    by_growth  = sorted(branches, key=lambda x: x.get("growth", 0), reverse=True)
    by_cost    = sorted(branches, key=lambda x: x.get("expense_ratio", 0), reverse=True)

    used = set()

    def pick_unique(sorted_list):
        for b in sorted_list:
            if b["branch_name"] not in used:
                used.add(b["branch_name"])
                return b
        return sorted_list[0] if sorted_list else None

    # ── Classifications (NO DUPLICATION) ─────────────────
    revenue_leader = pick_unique(by_revenue)
    margin_leader  = pick_unique(by_margin)
    growth_leader  = pick_unique(by_growth)
    cost_outlier   = pick_unique(by_cost)

    weakest = sorted(branches, key=lambda x: x.get("net_margin", 0))[0]

    # ── Company insights ────────────────────────────────
    insights = []

    if revenue_leader:
        rev = revenue_leader.get("revenue")
        nm = revenue_leader.get("net_margin")
        insights.append({
            "type": "leader",
            "branch": revenue_leader["branch_name"],
            "message": (
                f"{revenue_leader['branch_name']} leads branch revenue at {rev:.0f}"
                + (f" with net margin {nm:.1f}%." if nm is not None else ".")
            ),
        })

    if weakest:
        nm = weakest.get("net_margin")
        growth = weakest.get("growth")
        insights.append({
            "type": "risk",
            "branch": weakest["branch_name"],
            "message": (
                f"{weakest['branch_name']} is the weakest profitability point"
                + (f" at {nm:.1f}% net margin" if nm is not None else "")
                + (f" with growth at {growth:.1f}%." if growth is not None else ".")
            ),
        })

    if cost_outlier:
        exp_r = cost_outlier.get("expense_ratio")
        insights.append({
            "type": "cost",
            "branch": cost_outlier["branch_name"],
            "message": (
                f"{cost_outlier['branch_name']} carries the highest expense pressure"
                + (f" at {exp_r:.1f}% of revenue." if exp_r is not None else ".")
            ),
        })

    # ── Final output ────────────────────────────────────
    return {
        "classifications": {
            "revenue_leader": revenue_leader,
            "margin_leader": margin_leader,
            "growth_leader": growth_leader,
            "cost_outlier": cost_outlier,
            "weakest": weakest,
        },
        "company_insights": insights
    }
