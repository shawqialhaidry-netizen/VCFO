"""
intelligence_engine.py — Phase 8
CFO Intelligence Layer.

LEGACY / NON-CANONICAL FOR PRODUCT (Phase 3): ``run_intelligence`` feeds only the
historical GET /{company_id} aggregate response. Product Command Center / executive
use ``fin_intelligence.build_intelligence`` + ``build_cfo_decisions`` instead.

Sits ABOVE the existing decision_engine.py.
Takes the full analysis + trends and produces CFO-grade intelligence:
  - Structured insights with what/why/impact
  - Financial reasoning (margin compression, cost pressure, revenue root cause)
  - Forecast in ``run_intelligence`` uses ``forecast_engine.build_forecast`` only (not ad-hoc series)

Design rules:
  - NO external AI APIs — pure deterministic logic
  - NO financial recalculation — reads from analysis dict only
  - Backward compatible — run_decision() still works unchanged
  - Each signal carries: what, why, impact (low/medium/high), recommendation
"""
from __future__ import annotations

import math
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  Thresholds
# ══════════════════════════════════════════════════════════════════════════════

class I:
    # Margin compression
    GM_COMPRESSION_THRESHOLD   = -2.0    # gross margin MoM % pts drop
    GM_COMPRESSION_STREAK      = 2       # consecutive months
    NM_COMPRESSION_THRESHOLD   = -3.0    # net margin MoM % pts drop
    COGS_RATIO_HIGH            = 65.0    # COGS/Revenue % — cost pressure
    COGS_GROWTH_VS_REV_DELTA   = 3.0     # COGS growing faster than revenue by this %

    # Revenue
    REV_DECLINE_STREAK_WARN    = 2
    REV_DECLINE_STREAK_DANGER  = 3
    REV_DROP_SHARP             = -15.0   # single month MoM %
    REV_RECOVERY_THRESHOLD     = 5.0     # MoM after decline — recovery signal

    # Profit
    NP_DROP_SEVERE             = -40.0   # NP MoM % — severe contraction
    NP_MARGIN_BELOW_REV_GROWTH = True    # flag if revenue grows but NP shrinks

    # Expense pressure
    OPEX_GROWING_FASTER        = 2.0     # OpEx MoM > Revenue MoM by this %
    OPEX_TO_REVENUE_HIGH       = 35.0    # OpEx/Revenue %

    # (Legacy forecast constants removed — run_intelligence uses forecast_engine only.)


# ══════════════════════════════════════════════════════════════════════════════
#  Structured signal constructors
# ══════════════════════════════════════════════════════════════════════════════

def _signal(
    category:    str,
    key:         str,
    impact:      str,
    rec_key:     str,
    why_key:     str     = "",
    metric:      str     = "",
    data:        dict | None = None,
    # Legacy: kept for backward compat — ignored if key is provided
    what:        str     = "",
    why:         str     = "",
    recommendation: str  = "",
) -> dict:
    """
    Structured CFO-level signal.
    Emits key + data — frontend translates using tSignal(key, data).
    The 'what'/'why'/'recommendation' fields contain English fallback text
    for consumers that have not yet migrated to key-based translation.
    """
    return {
        "category":       category,
        "key":            key,
        "why_key":        why_key,
        "rec_key":        rec_key,
        "impact":         impact,
        "metric":         metric,
        "data":           data or {},
        # English fallback (built from data at signal creation time)
        "what":           what,
        "why":            why,
        "recommendation": recommendation,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _g(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
        if cur is None:
            return default
    return cur


def _pct_pts_change(series: list[Optional[float]], n: int = 1) -> Optional[float]:
    """Change in percentage points between last two elements."""
    valid = [v for v in series if v is not None]
    if len(valid) < n + 1:
        return None
    return round(valid[-1] - valid[-(n + 1)], 2)


def _slope(series: list[Optional[float]], window: int = 3) -> Optional[float]:
    """
    Simple linear slope over last `window` points.
    Positive = upward trend, negative = downward.
    Returns None if insufficient data.
    """
    vals = [v for v in (series or []) if v is not None][-window:]
    if len(vals) < 2:
        return None
    n = len(vals)
    x_mean = (n - 1) / 2
    y_mean = sum(vals) / n
    num = sum((i - x_mean) * (vals[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return round(num / den, 4) if den else 0.0


def _mom_pts_declining(series: list[Optional[float]], n: int = 2) -> bool:
    """True if last n MoM values are all negative."""
    vals = [v for v in (series or []) if v is not None]
    return len(vals) >= n and all(v < 0 for v in vals[-n:])


def _safe_pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return round((a - b) / abs(b) * 100, 2)


def _fmtK(v: Optional[float]) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.0f}K"
    return f"{v:.0f}"


# ══════════════════════════════════════════════════════════════════════════════
#  Analysis modules
# ══════════════════════════════════════════════════════════════════════════════

def _margin_compression_analysis(trends: dict, latest: dict) -> list[dict]:
    """
    Detects gross margin and net margin compression patterns.
    Distinguishes between COGS-driven vs OpEx-driven compression.
    """
    signals = []
    gm_series  = _g(trends, "gross_margin_series")   or []
    nm_pct     = _g(latest, "profitability", "net_margin_pct")
    gm_pct     = _g(latest, "profitability", "gross_margin_pct")
    rev_series = _g(trends, "revenue_series")         or []
    cogs_series= _g(trends, "cogs_series")            or []
    exp_series = _g(trends, "expenses_series")        or []
    gm_mom     = _g(trends, "gross_margin_mom_pct")   or []
    periods    = _g(trends, "periods")                or []

    # ── GM compression streak ──────────────────────────────────────────────────
    gm_compression_months = 0
    for v in reversed(gm_mom):
        if v is not None and v < 0:
            gm_compression_months += 1
        else:
            break

    if gm_compression_months >= I.GM_COMPRESSION_STREAK:
        # Determine cause: COGS or OpEx?
        cogs_growth = _safe_pct(cogs_series[-1], cogs_series[-2]) if len(cogs_series) >= 2 else None
        rev_growth  = _safe_pct(rev_series[-1],  rev_series[-2])  if len(rev_series)  >= 2 else None
        cogs_faster = (cogs_growth is not None and rev_growth is not None
                       and cogs_growth > rev_growth + I.COGS_GROWTH_VS_REV_DELTA)

        if cogs_faster:
            why = (f"COGS grew {cogs_growth:.1f}% vs revenue growth of "
                   f"{rev_growth:.1f}% — cost of goods sold is outpacing revenue.")
            rec = ("Renegotiate supplier terms. Review product mix: shift toward higher-margin "
                   "offerings. Audit procurement costs for hidden inefficiencies.")
        else:
            why = (f"Gross margin declined for {gm_compression_months} consecutive months. "
                   f"Revenue growth is not translating into proportional profit.")
            rec = ("Review pricing power. If volume is growing but margin shrinking, "
                   "consider selective price increases on highest-demand products.")

        gm_delta = _pct_pts_change(gm_series, gm_compression_months) or 0
        signals.append(_signal(
            category="margin_compression",
            key="sig_gm_compression_cogs_what" if cogs_faster else "sig_gm_compression_what",
            why_key="sig_gm_compression_cogs_why" if cogs_faster else "sig_gm_compression_why",
            rec_key="sig_gm_compression_cogs_rec" if cogs_faster else "sig_gm_compression_rec",
            impact="high" if abs(gm_delta) > 3 else "medium",
            metric="gross_margin_pct",
            data={"gm_current": gm_pct, "gm_delta": abs(gm_delta), "months": gm_compression_months,
                  "prev": round(gm_pct - gm_delta, 1), "current": gm_pct,
                  "delta": abs(gm_delta), "cogs_faster": cogs_faster,
                  "cogs_growth": cogs_growth if cogs_faster else 0,
                  "rev_growth":  rev_growth  if cogs_faster else 0},
            what=f"Gross margin compressed {abs(gm_delta):.1f} pts over {gm_compression_months} months (now {gm_pct:.1f}%).",
            why=why, recommendation=rec,
        ))

    # ── Single-period sharp GM drop ────────────────────────────────────────────
    elif gm_mom and gm_mom[-1] is not None and gm_mom[-1] < I.GM_COMPRESSION_THRESHOLD:
        period = periods[-1] if periods else "latest"
        signals.append(_signal(
            category="margin_compression",
            key="sig_gm_drop_what",
            why_key="sig_gm_drop_why",
            rec_key="sig_gm_drop_rec",
            impact="medium",
            metric="gross_margin_pct",
            data={"mom": gm_mom[-1], "period": period},
            what=f"Gross margin dropped {gm_mom[-1]:.1f}% in {period}.",
            why="Sudden increase in COGS or decrease in selling price.",
            recommendation="Investigate specific cost drivers. Check for one-off purchases or unusual discounts.",
        ))

    return signals


def _revenue_root_analysis(trends: dict, latest: dict) -> list[dict]:
    """
    Analyses revenue decline with root-cause decomposition.
    Distinguishes: volume-driven vs margin-driven vs seasonal.
    """
    signals = []
    rev_series  = _g(trends, "revenue_series")   or []
    rev_mom     = _g(trends, "revenue_mom_pct")  or []
    np_mom      = _g(trends, "net_profit_mom_pct") or []
    gm_mom      = _g(trends, "gross_margin_mom_pct") or []
    rev_streak  = _g(trends, "revenue_decline_streak") or 0
    periods     = _g(trends, "periods")          or []
    yoy_rev     = _g(trends, "yoy_revenue_pct")

    # ── Consecutive decline analysis ──────────────────────────────────────────
    if rev_streak >= I.REV_DECLINE_STREAK_WARN:
        # Collect the decline amounts
        decline_pcts = [v for v in rev_mom[-rev_streak:] if v is not None]
        avg_decline  = sum(decline_pcts) / len(decline_pcts) if decline_pcts else 0
        total_decline= _safe_pct(rev_series[-1], rev_series[-(rev_streak+1)]) if len(rev_series) > rev_streak else None

        # Is this seasonal? Check if same periods last year were also negative
        # (we can infer if YoY is also negative — double confirmation)
        seasonal_flag = yoy_rev is not None and yoy_rev < -5

        impact = "critical" if rev_streak >= I.REV_DECLINE_STREAK_DANGER else "high"
        why_parts = [f"Revenue declined for {rev_streak} consecutive months."]
        if total_decline is not None:
            why_parts.append(f"Cumulative decline: {total_decline:.1f}% from peak.")
        if seasonal_flag:
            why_parts.append("Year-over-year comparison also negative — may indicate structural decline, not just seasonality.")
        elif yoy_rev is not None and yoy_rev > 0:
            why_parts.append("Year-over-year comparison is still positive — suggests seasonal pattern rather than structural issue.")

        rec_parts = ["Review customer retention and churn rates."]
        if rev_streak >= I.REV_DECLINE_STREAK_DANGER:
            rec_parts = ["URGENT: Activate revenue recovery plan.",
                         "Identify top-5 accounts at risk.",
                         "Review pricing and competitive positioning immediately."]
        else:
            rec_parts.append("Analyse whether decline is concentrated in specific products or channels.")

        _why_key = "sig_rev_decline_why_struct" if seasonal_flag else ("sig_rev_decline_why_seasonal" if (yoy_rev is not None and yoy_rev > 0) else "sig_rev_decline_why_basic")
        _rec_key = "sig_rev_decline_rec_urgent" if rev_streak >= I.REV_DECLINE_STREAK_DANGER else "sig_rev_decline_rec_normal"
        signals.append(_signal(
            category="revenue_decline",
            key="sig_rev_decline_what",
            why_key=_why_key,
            rec_key=_rec_key,
            impact=impact,
            metric="revenue_trend",
            data={"streak": rev_streak, "current": _fmtK(rev_series[-1] if rev_series else None),
                  "total": total_decline or 0, "avg_mom_pct": round(avg_decline, 2), "yoy_pct": yoy_rev},
            what=f"Revenue declined {rev_streak} consecutive months.",
            why=" ".join(why_parts), recommendation=" ".join(rec_parts),
        ))

    # ── Sharp single-month drop ────────────────────────────────────────────────
    elif rev_mom and rev_mom[-1] is not None and rev_mom[-1] <= I.REV_DROP_SHARP:
        period = periods[-1] if periods else "latest"
        prev_rev = rev_series[-2] if len(rev_series) >= 2 else None
        curr_rev = rev_series[-1] if rev_series else None

        # Was NP drop proportional or larger? (if larger → margin also hurt)
        np_hurt = (np_mom and np_mom[-1] is not None and
                   np_mom[-1] < rev_mom[-1] - 10)

        signals.append(_signal(
            category="revenue_decline",
            key="sig_rev_drop_what",
            why_key="sig_rev_drop_why_np" if np_hurt else "sig_rev_drop_why",
            rec_key="sig_rev_drop_rec",
            impact="high",
            metric="revenue_mom",
            data={"mom": rev_mom[-1], "period": period, "prev": _fmtK(prev_rev), "curr": _fmtK(curr_rev), "np_hurt": np_hurt},
            what=f"Sharp revenue drop {rev_mom[-1]:.1f}% in {period} ({_fmtK(prev_rev)} → {_fmtK(curr_rev)}).",
            why="Revenue fell sharply." + (" Profit fell even harder." if np_hurt else " Profit decline was proportional."),
            recommendation="Identify whether this is a one-off event or start of a trend.",
        ))

    # ── Recovery signal ────────────────────────────────────────────────────────
    if (len(rev_mom) >= 2
            and rev_mom[-2] is not None and rev_mom[-2] < 0
            and rev_mom[-1] is not None and rev_mom[-1] >= I.REV_RECOVERY_THRESHOLD):
        period = periods[-1] if periods else "latest"
        signals.append(_signal(
            category="revenue_recovery",
            key="sig_rev_recovery_what",
            why_key="sig_rev_recovery_why",
            rec_key="sig_rev_recovery_rec",
            impact="low",
            metric="revenue_trend",
            data={"mom": rev_mom[-1], "period": period, "prior_mom": rev_mom[-2]},
            what=f"Revenue recovered +{rev_mom[-1]:.1f}% in {period} after prior decline.",
            why="Positive reversal following a down period.",
            recommendation="Monitor for 2 more months to confirm sustained recovery.",
        ))

    return signals


def _cost_pressure_analysis(trends: dict, latest: dict) -> list[dict]:
    """
    Detects cost pressure: COGS ratio, OpEx growing faster than revenue.
    """
    signals = []
    rev_series  = _g(trends, "revenue_series")   or []
    cogs_series = _g(trends, "cogs_series")       or []
    exp_series  = _g(trends, "expenses_series")   or []
    rev_mom     = _g(trends, "revenue_mom_pct")   or []
    exp_mom     = _g(trends, "expenses_mom_pct")  or []
    gm_pct      = _g(latest, "profitability", "gross_margin_pct")
    om_pct      = _g(latest, "profitability", "operating_margin_pct")

    # ── COGS ratio check ──────────────────────────────────────────────────────
    if rev_series and cogs_series and rev_series[-1] and rev_series[-1] > 0:
        cogs_ratio = round(cogs_series[-1] / rev_series[-1] * 100, 1)
        if cogs_ratio > I.COGS_RATIO_HIGH:
            signals.append(_signal(
                category="cost_pressure",
                key="sig_cogs_ratio_what",
                why_key="sig_cogs_ratio_why",
                rec_key="sig_cogs_ratio_rec",
                impact="high" if cogs_ratio > 70 else "medium",
                metric="cogs_ratio",
                data={"ratio": cogs_ratio, "threshold": I.COGS_RATIO_HIGH},
                what=f"COGS {cogs_ratio:.1f}% of revenue — above {I.COGS_RATIO_HIGH}% threshold.",
                why="High COGS leaves insufficient gross margin.",
                recommendation="Conduct cost-per-unit analysis.",
            ))

    # ── OpEx growing faster than revenue ──────────────────────────────────────
    if rev_mom and exp_mom and rev_mom[-1] is not None and exp_mom[-1] is not None:
        delta = exp_mom[-1] - rev_mom[-1]
        if delta > I.OPEX_GROWING_FASTER:
            periods_data = _g(trends, "periods") or []
            period = periods_data[-1] if periods_data else "latest"
            signals.append(_signal(
                category="cost_pressure",
                key="sig_opex_faster_what",
                why_key="sig_opex_faster_why",
                rec_key="sig_opex_faster_rec",
                impact="medium",
                metric="opex_vs_revenue",
                data={"opex_mom": exp_mom[-1], "rev_mom": rev_mom[-1], "delta": round(delta, 2), "period": period},
                what=f"OpEx grew {exp_mom[-1]:.1f}% vs revenue {rev_mom[-1]:.1f}% in {period}.",
                why="Operating expenses outpacing revenue.",
                recommendation="Review discretionary spending.",
            ))

    # ── OpEx ratio to revenue ─────────────────────────────────────────────────
    if rev_series and exp_series and rev_series[-1] and rev_series[-1] > 0:
        opex_ratio = round(exp_series[-1] / rev_series[-1] * 100, 1)
        if opex_ratio > I.OPEX_TO_REVENUE_HIGH:
            signals.append(_signal(
                category="cost_pressure",
                key="sig_opex_ratio_what",
                why_key="sig_opex_ratio_why",
                rec_key="sig_opex_ratio_rec",
                impact="medium",
                metric="opex_ratio",
                data={"ratio": opex_ratio},
                what=f"Operating expenses are {opex_ratio:.1f}% of revenue.",
                why="High OpEx ratio reduces profitability.",
                recommendation="Benchmark against industry standards.",
            ))

    return signals


def _profitability_trend_analysis(trends: dict, latest: dict) -> list[dict]:
    """
    Tracks profitability trajectory: improving, stable, deteriorating.
    Flags revenue-profit divergence (revenue grows but profit shrinks).
    """
    signals = []
    rev_series = _g(trends, "revenue_series")          or []
    np_series  = _g(trends, "net_profit_series")        or []
    rev_mom    = _g(trends, "revenue_mom_pct")          or []
    np_mom     = _g(trends, "net_profit_mom_pct")       or []
    np_streak  = _g(trends, "net_profit_decline_streak") or 0
    periods    = _g(trends, "periods")                  or []

    # ── Revenue-profit divergence ──────────────────────────────────────────────
    if (len(rev_mom) >= 2 and len(np_mom) >= 2
            and rev_mom[-1] is not None and np_mom[-1] is not None):
        rev_growing    = rev_mom[-1] > 1.0
        profit_shrinking = np_mom[-1] < -5.0

        if rev_growing and profit_shrinking:
            period = periods[-1] if periods else "latest"
            signals.append(_signal(
                category="profitability_trend",
                key="sig_rev_profit_div_what",
                why_key="sig_rev_profit_div_why",
                rec_key="sig_rev_profit_div_rec",
                impact="high",
                metric="revenue_profit_divergence",
                data={"rev_mom": rev_mom[-1], "np_mom": abs(np_mom[-1]), "period": period},
                what=f"Revenue grew {rev_mom[-1]:.1f}% but NP fell {abs(np_mom[-1]):.1f}% in {period}.",
                why="More revenue but less profit.",
                recommendation="Investigate which cost line absorbs the revenue gain.",
            ))

    # ── Severe profit contraction ──────────────────────────────────────────────
    if np_mom and np_mom[-1] is not None and np_mom[-1] <= I.NP_DROP_SEVERE:
        period = periods[-1] if periods else "latest"
        prev_np = np_series[-2] if len(np_series) >= 2 else None
        curr_np = np_series[-1] if np_series else None
        signals.append(_signal(
            category="profitability_trend",
            key="sig_np_severe_what",
            why_key="sig_np_severe_why",
            rec_key="sig_np_severe_rec",
            impact="critical",
            metric="net_profit_contraction",
            data={"mom": np_mom[-1], "period": period, "prev": _fmtK(prev_np), "curr": _fmtK(curr_np)},
            what=f"Net profit contracted severely: {np_mom[-1]:.1f}% in {period} ({_fmtK(prev_np)} → {_fmtK(curr_np)}).",
            why="Severe profit drop in a single period.",
            recommendation="Immediate CFO review required.",
        ))

    # ── Sustained profitability improvement ───────────────────────────────────
    elif (len(np_mom) >= 3
          and all(v is not None and v > 2 for v in np_mom[-3:])):
        signals.append(_signal(
            category="profitability_trend",
            key="sig_np_growth_what",
            why_key="sig_np_growth_why",
            rec_key="sig_np_growth_rec",
            impact="low",
            metric="net_profit_growth",
            data={"mom_values": np_mom[-3:]},
            what="Net profit has grown for 3+ consecutive months.",
            why="Sustained profit improvement indicates positive momentum.",
            recommendation="Identify driving factors and protect them.",
        ))

    return signals


# ══════════════════════════════════════════════════════════════════════════════
#  Legacy internal forecast helpers (Phase 1.1)
#  REMOVED: former _build_forecast / narrative helpers. Product + GET /analysis
#  decision.forecast both use forecast_engine.build_forecast via run_intelligence().
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
#  Health score (upgraded)
# ══════════════════════════════════════════════════════════════════════════════

def _compute_health_score(
    structured_insights: list[dict],
    warnings_raw:        list[dict],
    recs_raw:            list[dict],
) -> int:
    """
    Weighted health score incorporating signal impact levels.

    Deductions (from 100):
      critical: -20, high: -12, medium: -5, low: -2
      legacy warning: -10, legacy high-priority rec: -5

    Positive signals add back: +3 each.

    Floor: score is clamped to [10, 100].
    A score of 0 is reserved for complete system failure, not normal operation.
    """
    score = 100
    impact_penalty  = {"critical": 20, "high": 12, "medium": 5, "low": 2}

    for sig in structured_insights:
        impact = sig.get("impact", "medium")
        if sig.get("category") in ("cashflow", "cost_structure", "efficiency",
                                    "operating_leverage", "profitability"):
            # Informational/advisory signals — smaller penalty
            score -= min(impact_penalty.get(impact, 5), 5)
        else:
            score -= impact_penalty.get(impact, 5)

    for w in warnings_raw:
        score -= 10

    for r in recs_raw:
        penalty = {"high": 5, "medium": 2, "low": 1}.get(r.get("priority", "medium"), 2)
        score -= penalty

    # Positive insights restore some score
    positive_count = sum(
        1 for s in structured_insights
        if s.get("impact") == "low" and s.get("category") in
           ("cashflow", "efficiency", "profitability")
    )
    score += positive_count * 3

    # Clamp: never below 10 for a company with data
    return max(10, min(100, score))



# ══════════════════════════════════════════════════════════════════════════════
#  Advanced metric rules (Phase 8 upgrade)
# ══════════════════════════════════════════════════════════════════════════════

def _advanced_profitability_rules(adv: dict, insights: list, warnings: list, recs: list):
    prof = adv.get("profitability") or {}

    # Operating Leverage
    dol = prof.get("operating_leverage_dol")
    if dol is not None:
        if dol > 3.0:
            insights.append(_signal(
                category="operating_leverage",
                key="sig_dol_high_what",
                why_key="sig_dol_high_why",
                rec_key="sig_dol_high_rec",
                impact="medium",
                metric="operating_leverage_dol",
                data={"dol": dol, "dol_abs": abs(dol)},
                what=f"Operating leverage (DOL) is {dol:.2f}x.",
                why=f"1% revenue change produces {abs(dol):.1f}% change in operating profit.",
                recommendation="Ensure revenue forecasts are conservative.",
            ))
        elif dol < 0:
            warnings.append({"message": f"Negative operating leverage (DOL={dol:.2f}): "
                              "operating profit moved opposite to revenue — investigate cost structure.",
                              "metric": "operating_leverage_dol"})

    # EBITDA margin vs operating margin gap (D&A significance)
    ebitda_m = prof.get("ebitda_margin_pct")
    avg_nm   = prof.get("avg_net_margin_pct")
    if ebitda_m is not None and avg_nm is not None:
        gap = ebitda_m - avg_nm
        if gap > 5:
            insights.append(_signal(
                category="profitability",
                key="sig_ebitda_gap_what",
                why_key="sig_ebitda_gap_why",
                rec_key="sig_ebitda_gap_rec",
                impact="low",
                metric="ebitda_vs_net_margin",
                data={"ebitda": ebitda_m, "nm": avg_nm, "gap": gap},
                what=f"EBITDA margin ({ebitda_m:.1f}%) exceeds net margin ({avg_nm:.1f}%) by {gap:.1f} pts.",
                why="Large EBITDA-NP gap indicates D&A, interest, or tax burden.",
                recommendation="Review financing costs and tax planning.",
            ))

    # Incremental margin insight
    inc_m = prof.get("incremental_margin_pct")
    if inc_m is not None:
        if inc_m > 20:
            insights.append(_signal(
                category="profitability",
                key="sig_inc_margin_what",
                why_key="sig_inc_margin_why",
                rec_key="sig_inc_margin_rec",
                impact="low",
                metric="incremental_margin_pct",
                data={"pct": inc_m},
                what=f"Incremental margin is {inc_m:.1f}% — highly profitable.",
                why="Revenue growth translating efficiently to profit.",
                recommendation="Prioritise revenue growth.",
            ))
        elif inc_m < 0:
            warnings.append({"message": f"Negative incremental margin ({inc_m:.1f}%): "
                              "additional revenue is costing more than it earns.",
                              "metric": "incremental_margin_pct"})


def _advanced_risk_rules(adv: dict, insights: list, warnings: list, recs: list):
    risk = adv.get("risk") or {}

    # Risk rating
    risk_rating  = risk.get("risk_rating", "unknown")
    risk_factors = risk.get("risk_factor_count", 0)

    if risk_rating == "critical":
        warnings.append({"message": f"Risk profile is CRITICAL ({risk_factors} risk factors). "
                          "Multiple financial stability metrics are deteriorating simultaneously.",
                          "metric": "risk_rating"})
        recs.append({"message": "Immediate board-level review required. Prepare a risk mitigation plan "
                     "addressing cost structure, revenue volatility, and earnings consistency.",
                     "priority": "high", "metric": "risk_rating"})
    elif risk_rating == "high":
        warnings.append({"message": f"Risk profile is HIGH ({risk_factors} risk factors). "
                          "Financial metrics show elevated volatility.",
                          "metric": "risk_rating"})

    # Margin volatility
    mv  = risk.get("margin_volatility") or {}
    gm_std = mv.get("gross_margin_std_dev")
    if gm_std is not None and gm_std > 3.0:
                                insights.append(_signal(
                    category="risk",
                    key="sig_rev_vol_what",
                    why_key="sig_rev_vol_why",
                    rec_key="sig_rev_vol_rec",
                    impact="medium",
                    metric="revenue_stability",
                    data={"score": stab_score, "cv": rev_cv},
                    what=f"Gross margin volatility is {gm_std:.2f} percentage points std dev over {adv.get('period_count',0)} periods.",
                    why="",
                    recommendation="",
                ))

    # Earnings consistency
    ec = risk.get("earnings_consistency") or {}
    score = ec.get("consistency_score", 100)
    rating = ec.get("consistency_rating", "unknown")
    if rating == "inconsistent":
                    insights.append(_signal(
                category="risk",
                key="sig_earnings_incons_what",
                why_key="sig_earnings_incons_why",
                rec_key="sig_earnings_incons_rec",
                impact="high",
                metric="earnings_consistency",
                data={"score": score, "pos": ec.get("positive_np_pct",0), "grow": ec.get("growing_np_pct",0)},
                what=f"Earnings consistency score is {score:.0f}/100 — profit is unpredictable.",
                why="", recommendation="",
            ))
    # Cost structure
    cs = risk.get("cost_structure") or {}
    cogs_pct = cs.get("avg_cogs_pct")
    opex_pct = cs.get("avg_opex_pct")
    struct   = cs.get("cost_structure_type", "")
    if cogs_pct is not None and opex_pct is not None:
                insights.append(_signal(
            category="cost_structure",
            key="sig_cost_struct_what",
            why_key="sig_cost_struct_why_product",
            rec_key="sig_cost_struct_rec_product",
            impact="low",
            metric="cost_structure",
            data={"cogs": cogs_pct, "opex": opex_pct, "type": struct},
            what=(f"Cost structure: COGS averages {cogs_pct:.1f}% of revenue, "
                  f"OpEx {opex_pct:.1f}% — classified as '{struct}'."),
            why="",
            recommendation="",
        ))

    # Revenue stability
    rs = risk.get("revenue_stability") or {}
    stab_score  = rs.get("stability_score")
    stab_rating = rs.get("stability_rating", "unknown")
    rev_cv      = rs.get("revenue_cv")
    if stab_rating == "volatile" and stab_score is not None:
                    insights.append(_signal(
                category="risk",
                key="sig_rev_vol_what",
                why_key="sig_rev_vol_why",
                rec_key="sig_rev_vol_rec",
                impact="medium",
                metric="revenue_stability",
                data={"score": stab_score, "cv": rev_cv},
                what=f"Revenue stability score is {stab_score}/100 (CV={rev_cv:.2f}) — high volatility.",
                why="", recommendation="",
            ))

def _advanced_efficiency_rules(adv: dict, insights: list, warnings: list, recs: list):
    eff = adv.get("efficiency") or {}

    asset_turnover = eff.get("asset_turnover")
    rec_turnover   = eff.get("receivables_turnover")
    pay_turnover   = eff.get("payables_turnover")
    inv_turnover   = eff.get("inventory_turnover")
    ccc            = eff.get("ccc_days")

    # Asset turnover: < 0.5 = under-utilising assets
    if asset_turnover is not None and asset_turnover < 0.5:
                                                                insights.append(_signal(
                                    category="efficiency",
                                    key="sig_ccc_good_what",
                                    why_key="sig_ccc_good_why",
                                    rec_key="sig_ccc_good_rec",
                                    impact="medium",
                                    metric="ccc_days",
                                    data={"ccc": ccc},
                                    what=f"Asset turnover is {asset_turnover:.2f}x — assets generating low revenue relative to their value.",
                                    why="",
                                    recommendation="",
                                ))

    # Receivables turnover: low = slow collections
    if rec_turnover is not None and rec_turnover < 2.0:
        dso = eff.get("dso_days")
        insights.append(_signal(
            category="efficiency",
            key="sig_rec_turn_what",
            why_key="sig_rec_turn_why",
            rec_key="sig_rec_turn_rec",
            impact="medium",
            metric="receivables_turnover",
            data={"rt": rec_turnover, "dso": dso or 0},
            what=f"Receivables turnover is {rec_turnover:.2f}x ({dso:.0f} days).",
            why="", recommendation="",
        ))
    # CCC summary insight (positive = good)
    if ccc is not None and ccc < 20:
                    insights.append(_signal(
                category="efficiency",
                key="sig_ccc_good_what",
                why_key="sig_ccc_good_why",
                rec_key="sig_ccc_good_rec",
                impact="low",
                metric="ccc_days",
                data={"ccc": ccc},
                what=f"Cash Conversion Cycle of {ccc:.0f} days is efficient.",
                why="", recommendation="",
            ))


def _cashflow_rules(cf: dict, insights: list, warnings: list, recs: list):
    """Phase 9 cash flow intelligence rules — key+data output."""
    ocf     = cf.get("operating_cashflow")
    np_     = cf.get("debug", {}).get("net_profit")
    burn    = cf.get("burn_rate", 0)
    runway  = cf.get("runway_months")
    fcf     = cf.get("free_cashflow")
    quality = cf.get("quality", {})
    wc      = cf.get("working_capital_change", {})
    cash    = cf.get("cash_balance")
    q_label = quality.get("cash_conversion_quality", "")
    q_ratio = quality.get("cash_conversion_ratio")
    gap     = quality.get("profit_vs_cash_gap")

    fmtK = lambda v: f"{v/1000:.0f}K" if v and abs(v) >= 1000 else (f"{v:.0f}" if v else "—")

    # 1. Strong cash conversion
    if q_label == "strong" and ocf is not None and ocf > 0:
        insights.append(_signal(
            category="cashflow",
            key="sig_cf_strong_what",
            why_key="sig_cf_strong_why",
            rec_key="sig_cf_strong_rec",
            impact="low",
            metric="cash_conversion_quality",
            data={"ocf": fmtK(ocf), "np": fmtK(np_), "ratio": q_ratio or 0},
            what=f"Strong cash conversion: OCF {fmtK(ocf)} vs NP {fmtK(np_)}.",
            why="", recommendation="",
        ))

    # 2. Weak cash conversion
    elif q_label == "weak" and np_ and np_ > 0:
        insights.append(_signal(
            category="cashflow",
            key="sig_cf_weak_what",
            why_key="sig_cf_weak_why",
            rec_key="sig_cf_weak_rec",
            impact="high",
            metric="cash_conversion_quality",
            data={"np": fmtK(np_), "ocf": fmtK(ocf), "gap": fmtK(gap)},
            what=f"Earnings quality risk: NP {fmtK(np_)} but OCF only {fmtK(ocf)}.",
            why="", recommendation="",
        ))
        warnings.append({
            "message": f"Earnings quality risk: profit {fmtK(np_)} not converting to cash (OCF {fmtK(ocf)}).",
            "metric": "cash_conversion_quality",
        })

    # 3. Negative OCF
    if ocf is not None and ocf < 0:
        insights.append(_signal(
            category="cashflow",
            key="sig_cf_neg_what",
            why_key="sig_cf_neg_why",
            rec_key="sig_cf_neg_rec",
            impact="high" if ocf < -50000 else "medium",
            metric="operating_cashflow",
            data={"ocf": fmtK(ocf)},
            what=f"Negative operating cash flow: {fmtK(ocf)}.",
            why="", recommendation="",
        ))
        warnings.append({
            "message": f"Negative operating cash flow ({fmtK(ocf)}).",
            "metric": "operating_cashflow",
        })

    # 4. Rising receivables stress
    delta_rec = wc.get("receivables", 0) or 0
    if delta_rec > 50000:
        insights.append(_signal(
            category="cashflow",
            key="sig_rec_stress_what",
            why_key="sig_rec_stress_why",
            rec_key="sig_rec_stress_rec",
            impact="medium",
            metric="delta_receivables",
            data={"delta": fmtK(delta_rec)},
            what=f"Receivables increased by {fmtK(delta_rec)} — working capital stress.",
            why="", recommendation="",
        ))

    # 5. Burn rate
    if burn > 0:
        rec_key = "sig_burn_rec_urgent" if (runway and runway < 3) else "sig_burn_rec_normal"
        insights.append(_signal(
            category="cashflow",
            key="sig_burn_what",
            why_key="sig_burn_why",
            rec_key=rec_key,
            impact="critical" if (runway and runway < 3) else "high" if (runway and runway < 6) else "medium",
            metric="burn_rate",
            data={
                "burn":   fmtK(burn),
                "runway": f"{runway:.1f} months" if runway else "unknown",
                "cash":   fmtK(cash),
            },
            what=f"Cash burn rate: {fmtK(burn)}/month.",
            why="", recommendation="",
        ))
        warnings.append({
            "message": f"Cash burn {fmtK(burn)}/month. Runway: {f'{runway:.1f} months' if runway else 'unknown'}.",
            "metric": "burn_rate",
        })
        recs.append({
            "message": "Reduce monthly cash burn through cost controls and revenue acceleration.",
            "priority": "high" if (not runway or runway < 6) else "medium",
            "metric": "burn_rate",
        })

    # 6. Negative FCF
    if fcf is not None and fcf < 0:
        insights.append(_signal(
            category="cashflow",
            key="sig_fcf_neg_what",
            why_key="sig_fcf_neg_why",
            rec_key="sig_fcf_neg_rec",
            impact="medium",
            metric="free_cashflow",
            data={"fcf": fmtK(fcf)},
            what=f"Negative free cash flow: {fmtK(fcf)}.",
            why="", recommendation="",
        ))



def _root_cause_rules(rc: dict, insights: list, warnings: list, recs: list):
    rev = rc.get('revenue') or {}
    pft = rc.get('profit') or {}
    cst = rc.get('cost_structure') or {}
    trd = rc.get('trends') or {}

    for section, section_key, title_key in [
        (rev, 'rc_revenue_title', 'rc_revenue_title'),
        (pft, 'rc_profit_title',  'rc_profit_title'),
    ]:
        key = section.get('key', '')
        sev = section.get('severity', 'low')
        if key and sev in ('high', 'medium'):
            insights.append(_signal(
                category='root_cause',
                key=key,
                why_key=title_key,
                rec_key='',
                impact=sev,
                metric='root_cause',
                data=section.get('data', {}),
                what='', why='', recommendation='',
            ))

    if cst.get('key') == 'rc_cost_structure_deteriorating':
        insights.append(_signal(
            category='root_cause',
            key='rc_cost_structure_deteriorating',
            why_key='rc_cost_title',
            rec_key='',
            impact='medium',
            metric='cost_structure_root_cause',
            data=cst.get('data', {}),
            what='', why='', recommendation='',
        ))

    overall = trd.get('overall', 'stable')
    if overall == 'deteriorating':
        warnings.append({
            'message': 'Multiple metrics deteriorating simultaneously.',
            'metric': 'overall_trend',
        })
    elif overall in ('improving', 'mixed_positive'):
        insights.append(_signal(
            category='root_cause',
            key='rc_trend_improving',
            why_key='rc_trends_title',
            rec_key='rc_trend_improving',
            impact='low',
            metric='overall_trend',
            data={'overall': overall},
            what='', why='', recommendation='',
        ))


def run_intelligence(analysis: dict, advanced_metrics: dict | None = None, cashflow: dict | None = None, root_cause: dict | None = None) -> dict:
    """
    Phase 8 CFO Intelligence Layer.

    Input:  dict from run_analysis() (Phase 5)
            advanced_metrics: optional dict from compute_advanced_metrics()
    Output:
    {
      "insights":         [structured CFO signals],
      "warnings":         [legacy format — backward compatible],
      "recommendations":  [legacy format — backward compatible],
      "forecast":         { next-period projections },
      "summary": {
        "total_insights":        int,
        "total_warnings":        int,
        "total_recommendations": int,
        "health_score":          int,
        "top_risk":              str | None,
        "top_opportunity":       str | None,
      }
    }
    """
    latest  = analysis.get("latest")  or {}
    trends  = analysis.get("trends")  or {}

    # ── Run all intelligence modules ──────────────────────────────────────────
    structured: list[dict] = []

    structured.extend(_margin_compression_analysis(trends, latest))
    structured.extend(_revenue_root_analysis(trends, latest))
    structured.extend(_cost_pressure_analysis(trends, latest))
    structured.extend(_profitability_trend_analysis(trends, latest))

    # ── Phase 8: Advanced metric rules (require advanced_metrics) ──────────────
    if advanced_metrics and not advanced_metrics.get("error"):
        _advanced_profitability_rules(advanced_metrics, structured, [], [])
        _advanced_risk_rules(advanced_metrics, structured, [], [])
        _advanced_efficiency_rules(advanced_metrics, structured, [], [])

    # ── Sort by impact ─────────────────────────────────────────────────────────
    _impact_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    structured.sort(key=lambda x: _impact_order.get(x.get("impact", "medium"), 2))

    # ── Backward-compatible warnings / recommendations ─────────────────────────
    # Convert structured insights to legacy format so existing consumers still work
    warnings_compat:  list[dict] = []
    recs_compat:      list[dict] = []

    for sig in structured:
        impact = sig.get("impact", "medium")
        if impact in ("critical", "high"):
            warnings_compat.append({
                "message": f"{sig['what']} {sig['why']}",
                "metric":  sig.get("metric", ""),
            })
        recs_compat.append({
            "message":  sig["recommendation"],
            "priority": "high" if impact in ("critical", "high") else
                        "medium" if impact == "medium" else "low",
            "metric":   sig.get("metric", ""),
        })

    # ── Phase 9: Cash flow rules (after compat lists are initialized) ──────────
    if cashflow and not cashflow.get("error"):
        _cashflow_rules(cashflow, structured, warnings_compat, recs_compat)

    # ── Phase 10: Root cause rules ────────────────────────────────────────────
    if root_cause and not root_cause.get("error"):
        _root_cause_rules(root_cause, structured, warnings_compat, recs_compat)

    # ── Forecast (canonical engine — same as GET /forecast; lang defaults EN here) ─
    from app.services.forecast_engine import build_forecast as _canonical_forecast

    forecast = _canonical_forecast(analysis, lang="en")

    # ── Health score ──────────────────────────────────────────────────────────
    health_score = _compute_health_score(structured, warnings_compat, [])

    # ── Top risk / opportunity ────────────────────────────────────────────────
    top_risk = structured[0]["what"] if structured else None
    top_opp  = None
    if forecast.get("available"):
        sm = forecast.get("summary") or {}
        mom_rev = sm.get("trend_mom_revenue")
        risk = sm.get("risk_level")
        try:
            mom_ok = mom_rev is not None and float(mom_rev) > 0
        except (TypeError, ValueError):
            mom_ok = False
        if mom_ok and risk != "high":
            br = ((forecast.get("scenarios") or {}).get("base") or {}).get("revenue") or []
            pt = br[0].get("point") if br and isinstance(br[0], dict) else None
            if pt is not None:
                top_opp = (
                    f"Base scenario Month-1 revenue ~{_fmtK(float(pt))} "
                    f"(MoM trend {float(mom_rev):+.1f}%, risk {risk})."
                )

    return {
        "insights":        structured,
        "warnings":        warnings_compat,
        "recommendations": recs_compat,
        "forecast":        forecast,
        "summary": {
            "total_insights":        len(structured),
            "total_warnings":        len(warnings_compat),
            "total_recommendations": len(recs_compat),
            "health_score":          health_score,
            "top_risk":              top_risk,
            "top_opportunity":       top_opp,
        },
    }
