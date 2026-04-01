"""
decision_engine.py — Phase 6
Rule-based decision engine. Interprets Phase 5 analysis output.

Responsibilities:
  - Generate business insights
  - Raise warnings
  - Produce recommendations

Design rules:
  - NO external AI APIs
  - Deterministic if/else logic only
  - Input: analysis dict from run_analysis()
  - Output: {insights, warnings, recommendations}
  - Never crashes on missing data (all rules null-safe)
"""
from __future__ import annotations
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  Threshold constants — single source of truth
# ══════════════════════════════════════════════════════════════════════════════

class T:
    # Liquidity
    CURRENT_RATIO_DANGER  = 1.0
    CURRENT_RATIO_CAUTION = 1.5
    QUICK_RATIO_DANGER    = 0.8

    # Profitability
    GROSS_MARGIN_LOW      = 20.0   # %
    NET_MARGIN_NEGATIVE   = 0.0    # %
    NET_MARGIN_LOW        = 5.0    # %
    OPERATING_MARGIN_LOW  = 5.0    # %

    # Leverage
    DEBT_TO_EQUITY_HIGH   = 2.0
    DEBT_TO_EQUITY_DANGER = 3.0

    # Efficiency
    CCC_HIGH              = 60     # days
    DIO_HIGH              = 45     # days
    DPO_LOW               = 15     # days

    # Trends
    DECLINE_STREAK        = 2      # consecutive months of decline → flag
    MOM_DROP_SHARP        = -15.0  # % drop in single month → sharp decline


# ══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get(d: dict, *keys, default=None):
    """Safe nested dict access."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
        if cur is None:
            return default
    return cur


def _insight(msg: str, severity: str = "info", metric: str = "") -> dict:
    return {"message": msg, "severity": severity, "metric": metric}


def _warning(msg: str, metric: str = "") -> dict:
    return {"message": msg, "metric": metric}


def _recommendation(msg: str, priority: str = "medium", metric: str = "") -> dict:
    return {"message": msg, "priority": priority, "metric": metric}


# ══════════════════════════════════════════════════════════════════════════════
#  Rule sets
# ══════════════════════════════════════════════════════════════════════════════

def _liquidity_rules(latest: dict, insights: list, warnings: list, recs: list):
    cr = _get(latest, "liquidity", "current_ratio")
    qr = _get(latest, "liquidity", "quick_ratio")
    wc = _get(latest, "liquidity", "working_capital")

    if cr is not None:
        if cr < T.CURRENT_RATIO_DANGER:
            warnings.append(_warning(
                f"Current ratio is {cr:.2f} — below 1.0. "
                "Current liabilities exceed current assets. Immediate liquidity risk.",
                metric="current_ratio"
            ))
            recs.append(_recommendation(
                "Improve cash position: accelerate collections, reduce short-term debt, "
                "or secure a revolving credit facility.",
                priority="high", metric="current_ratio"
            ))
        elif cr < T.CURRENT_RATIO_CAUTION:
            warnings.append(_warning(
                f"Current ratio is {cr:.2f} — below 1.5. Liquidity is tight.",
                metric="current_ratio"
            ))
            recs.append(_recommendation(
                "Monitor cash flow weekly. Consider extending payables or accelerating receivables.",
                priority="medium", metric="current_ratio"
            ))
        else:
            insights.append(_insight(
                f"Current ratio is healthy at {cr:.2f}.",
                severity="positive", metric="current_ratio"
            ))

    if qr is not None and qr < T.QUICK_RATIO_DANGER:
        warnings.append(_warning(
            f"Quick ratio is {qr:.2f} — below 0.8. "
            "Excluding inventory, liquid assets may not cover short-term obligations.",
            metric="quick_ratio"
        ))
        recs.append(_recommendation(
            "Review inventory levels relative to current liabilities. "
            "Avoid relying on inventory liquidation to meet short-term obligations.",
            priority="high", metric="quick_ratio"
        ))

    if wc is not None and wc < 0:
        warnings.append(_warning(
            f"Negative working capital: {wc:,.0f}. "
            "The company may struggle to fund day-to-day operations.",
            metric="working_capital"
        ))


def _profitability_rules(latest: dict, insights: list, warnings: list, recs: list):
    nm  = _get(latest, "profitability", "net_margin_pct")
    gm  = _get(latest, "profitability", "gross_margin_pct")
    om  = _get(latest, "profitability", "operating_margin_pct")
    np_ = _get(latest, "profitability", "net_profit")

    if np_ is not None and np_ < 0:
        warnings.append(_warning(
            f"Company is losing money. Net loss: {abs(np_):,.0f}",
            metric="net_profit"
        ))
        recs.append(_recommendation(
            "Conduct immediate cost review. Identify largest expense categories "
            "and evaluate pricing strategy to restore profitability.",
            priority="high", metric="net_profit"
        ))
    elif nm is not None:
        if nm < T.NET_MARGIN_LOW:
            warnings.append(_warning(
                f"Net margin is low at {nm:.1f}%. Profitability is thin.",
                metric="net_margin_pct"
            ))
            recs.append(_recommendation(
                "Examine COGS and operating expenses for reduction opportunities. "
                "Even a 1–2% improvement in margin significantly impacts bottom line.",
                priority="medium", metric="net_margin_pct"
            ))
        else:
            insights.append(_insight(
                f"Net margin is {nm:.1f}% — within acceptable range.",
                severity="positive", metric="net_margin_pct"
            ))

    if gm is not None and gm < T.GROSS_MARGIN_LOW:
        warnings.append(_warning(
            f"Gross margin is {gm:.1f}% — below 20%. "
            "Cost of goods sold is consuming most of revenue.",
            metric="gross_margin_pct"
        ))
        recs.append(_recommendation(
            "Review supplier contracts and direct production costs. "
            "Consider pricing adjustments or product mix optimisation.",
            priority="medium", metric="gross_margin_pct"
        ))

    if om is not None and om < T.OPERATING_MARGIN_LOW:
        insights.append(_insight(
            f"Operating margin is {om:.1f}% — below 5%. "
            "Operating expenses are compressing profitability.",
            severity="warning", metric="operating_margin_pct"
        ))


def _leverage_rules(latest: dict, insights: list, warnings: list, recs: list):
    de = _get(latest, "leverage", "debt_to_equity")

    if de is not None:
        if de > T.DEBT_TO_EQUITY_DANGER:
            warnings.append(_warning(
                f"Debt-to-equity ratio is {de:.2f} — very high. "
                "The company is heavily leveraged.",
                metric="debt_to_equity"
            ))
            recs.append(_recommendation(
                "Prioritise debt reduction. High leverage increases financial risk "
                "and limits future borrowing capacity.",
                priority="high", metric="debt_to_equity"
            ))
        elif de > T.DEBT_TO_EQUITY_HIGH:
            insights.append(_insight(
                f"Debt-to-equity is {de:.2f} — elevated. Monitor debt levels.",
                severity="warning", metric="debt_to_equity"
            ))
        elif de < 0:
            warnings.append(_warning(
                "Negative debt-to-equity ratio indicates negative equity. "
                "The company's liabilities exceed its assets.",
                metric="debt_to_equity"
            ))
        else:
            insights.append(_insight(
                f"Debt-to-equity is {de:.2f} — within manageable range.",
                severity="positive", metric="debt_to_equity"
            ))


def _efficiency_rules(latest: dict, insights: list, warnings: list, recs: list):
    ccc = _get(latest, "efficiency", "ccc_days")
    dio = _get(latest, "efficiency", "dio_days")
    dpo = _get(latest, "efficiency", "dpo_days")
    dso = _get(latest, "efficiency", "dso_days")

    if ccc is not None:
        if ccc > T.CCC_HIGH:
            warnings.append(_warning(
                f"Cash Conversion Cycle is {ccc:.0f} days — above 60 days. "
                "Capital is tied up for too long before being recovered.",
                metric="ccc_days"
            ))
            recs.append(_recommendation(
                "Optimise the cash cycle: reduce days inventory outstanding, "
                "accelerate customer collections, and negotiate longer supplier payment terms.",
                priority="medium", metric="ccc_days"
            ))
        else:
            insights.append(_insight(
                f"Cash Conversion Cycle is {ccc:.0f} days — within acceptable range.",
                severity="positive", metric="ccc_days"
            ))

    if dio is not None and dio > T.DIO_HIGH:
        insights.append(_insight(
            f"Days Inventory Outstanding is {dio:.0f} days — above 45 days. "
            "Inventory may be slow-moving.",
            severity="warning", metric="dio_days"
        ))
        recs.append(_recommendation(
            "Review inventory management. Identify slow-moving SKUs and consider "
            "promotions or order quantity reductions.",
            priority="medium", metric="dio_days"
        ))

    if dpo is not None and dpo < T.DPO_LOW:
        insights.append(_insight(
            f"Days Payable Outstanding is {dpo:.0f} days — very short. "
            "The company is paying suppliers quickly.",
            severity="info", metric="dpo_days"
        ))
        recs.append(_recommendation(
            "Negotiate extended payment terms with key suppliers to improve cash flow.",
            priority="low", metric="dpo_days"
        ))


def _trend_rules(trends: dict, insights: list, warnings: list, recs: list):
    rev_streak = _get(trends, "revenue_decline_streak") or 0
    np_streak  = _get(trends, "net_profit_decline_streak") or 0
    rev_series = _get(trends, "revenue_series") or []
    np_series  = _get(trends, "net_profit_series") or []
    rev_mom    = _get(trends, "revenue_mom_pct") or []
    yoy_rev    = _get(trends, "yoy_revenue_pct")
    yoy_np     = _get(trends, "yoy_net_profit_pct")

    # Revenue decline streak
    if rev_streak >= T.DECLINE_STREAK:
        warnings.append(_warning(
            f"Revenue has declined for {rev_streak} consecutive months.",
            metric="revenue_trend"
        ))
        recs.append(_recommendation(
            "Investigate root cause of revenue decline: market conditions, pricing, "
            "or loss of key customers. Consider sales strategy review.",
            priority="high", metric="revenue_trend"
        ))
    elif len(rev_series) >= 3:
        # Check if upward trend in last 3 months
        if all(rev_series[i] >= rev_series[i-1] for i in range(len(rev_series)-2, len(rev_series))):
            insights.append(_insight(
                "Revenue shows a consistent upward trend over the last periods.",
                severity="positive", metric="revenue_trend"
            ))

    # Net profit decline streak
    if np_streak >= T.DECLINE_STREAK:
        insights.append(_insight(
            f"Net profit has declined for {np_streak} consecutive months.",
            severity="warning", metric="net_profit_trend"
        ))

    # Sharp single-month revenue drop
    for i, mom in enumerate(rev_mom):
        if mom is not None and mom <= T.MOM_DROP_SHARP:
            period = (_get(trends, "periods") or [])[i] if i < len(_get(trends, "periods") or []) else f"period {i}"
            insights.append(_insight(
                f"Sharp revenue drop of {mom:.1f}% detected in {period}.",
                severity="warning", metric="revenue_mom"
            ))

    # YoY insights
    if yoy_rev is not None:
        if yoy_rev > 0:
            insights.append(_insight(
                f"Year-over-year revenue growth: +{yoy_rev:.1f}%.",
                severity="positive", metric="yoy_revenue"
            ))
        else:
            warnings.append(_warning(
                f"Year-over-year revenue declined by {abs(yoy_rev):.1f}%.",
                metric="yoy_revenue"
            ))

    if yoy_np is not None:
        if yoy_np > 0:
            insights.append(_insight(
                f"Year-over-year net profit growth: +{yoy_np:.1f}%.",
                severity="positive", metric="yoy_net_profit"
            ))
        else:
            insights.append(_insight(
                f"Year-over-year net profit declined by {abs(yoy_np):.1f}%.",
                severity="warning", metric="yoy_net_profit"
            ))


# ══════════════════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def run_decision(analysis: dict) -> dict:
    """
    Generate insights, warnings, and recommendations from Phase 5 analysis.

    Input:  dict from run_analysis()
    Output: {
              "insights":        [...],
              "warnings":        [...],
              "recommendations": [...],
              "summary": {
                "total_warnings":        int,
                "total_insights":        int,
                "total_recommendations": int,
                "health_score":          int   (0–100, simple composite)
              }
            }
    """
    insights: list[dict] = []
    warnings: list[dict] = []
    recs:     list[dict] = []

    latest = analysis.get("latest") or {}
    trends = analysis.get("trends") or {}

    if latest:
        _liquidity_rules(latest,     insights, warnings, recs)
        _profitability_rules(latest, insights, warnings, recs)
        _leverage_rules(latest,      insights, warnings, recs)
        _efficiency_rules(latest,    insights, warnings, recs)

    if trends:
        _trend_rules(trends, insights, warnings, recs)

    # ── Health score: simple composite 0–100 ─────────────────────────────────
    # Start at 100, deduct for high-priority warnings and low-priority issues
    score = 100
    for w in warnings:
        score -= 15
    for r in recs:
        penalty = {"high": 10, "medium": 5, "low": 2}.get(r.get("priority", "medium"), 5)
        score -= penalty
    for ins in insights:
        if ins.get("severity") == "warning":
            score -= 5
        elif ins.get("severity") == "positive":
            score += 3
    score = max(0, min(100, score))

    return {
        "insights":        insights,
        "warnings":        warnings,
        "recommendations": recs,
        "summary": {
            "total_warnings":        len(warnings),
            "total_insights":        len(insights),
            "total_recommendations": len(recs),
            "health_score":          score,
        },
    }
