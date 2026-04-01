"""
deep_intelligence.py — Phase 47
Deterministic deep intelligence layer for VCFO.

Goal:
- Produce CFO-grade drivers/anomalies/signals using ONLY real data
  already produced by statement_engine → analysis_engine outputs.
- No placeholders, no fabricated causes.
- Extend existing API payloads (do not break contracts).

Primary outputs:
{
  "expense_intelligence": {...},
  "trend_intelligence": {...},
  "profitability_intelligence": {...},
}
"""
from __future__ import annotations

from typing import Any, Optional
import statistics

from app.services.metric_definitions import total_cost_ratio_pct


def _r2(v) -> Optional[float]:
    try:
        return round(float(v), 2)
    except Exception:
        return None


def _safe_pct(n, d) -> Optional[float]:
    try:
        n = float(n)
        d = float(d)
        if abs(d) < 0.001:
            return None
        return round(n / d * 100, 2)
    except Exception:
        return None


def _stdev(vals: list[float]) -> Optional[float]:
    v = [float(x) for x in (vals or []) if x is not None]
    if len(v) < 2:
        return None
    return round(statistics.stdev(v), 4)


def _mean(vals: list[float]) -> Optional[float]:
    v = [float(x) for x in (vals or []) if x is not None]
    if not v:
        return None
    return round(statistics.mean(v), 4)


def _cv(vals: list[float]) -> Optional[float]:
    """Coefficient of variation (stdev/abs(mean))."""
    m = _mean(vals)
    sd = _stdev(vals)
    if m is None or sd is None or abs(m) < 0.001:
        return None
    return round(sd / abs(m), 4)


def _accel(mom: list[float]) -> Optional[float]:
    """Acceleration = avg(last2) - avg(prev2) over MoM% series."""
    v = [x for x in (mom or []) if x is not None]
    if len(v) < 4:
        return None
    last2 = v[-2:]
    prev2 = v[-4:-2]
    a = _mean(last2)
    b = _mean(prev2)
    if a is None or b is None:
        return None
    return round(a - b, 2)


def build_expense_intelligence_deep(period_statements: list[dict], lang: str = "en") -> dict:
    """
    Deep expense drivers/anomalies using the existing expense_engine output.
    No duplicate classification logic here.
    """
    from app.services.expense_engine import build_expense_intelligence

    raw = build_expense_intelligence(period_statements, branch_financials=None, lang=lang) or {}
    groups: dict = raw.get("groups") or {}
    summary: dict = raw.get("summary") or {}

    # Denominator for share-of-cost: full cost base (COGS + OpEx + unclassified), not OpEx alone.
    total_exp = summary.get("total_cost_amount")
    if total_exp is None:
        total_exp = summary.get("total_expenses")

    structure = []
    for ck, g in groups.items():
        curr = g.get("current")
        contr = _safe_pct(curr, total_exp) if (total_exp is not None) else None
        structure.append({
            "category_key": ck,
            "label_key":    g.get("label_key"),
            "icon":         g.get("icon"),
            "amount":       curr,
            "ratio_pct":    g.get("ratio_pct"),
            "share_of_total_cost_pct": contr,
            "contribution_pct": contr,
            "mom_change_pct":   g.get("variance_pct"),
            "mom_amount_delta": g.get("variance"),
            "heatmap":      g.get("heatmap"),
            "top_items":    g.get("top_items") or [],
        })
    structure.sort(key=lambda x: (x.get("ratio_pct") is None, -(x.get("ratio_pct") or 0), -(x.get("amount") or 0)))

    top_drivers = structure[:3]

    anomalies = []
    # Abnormal increase rule: MoM > +15% and ratio of revenue is meaningful (>0.5%)
    for s in structure:
        mom = s.get("mom_change_pct")
        ratio = s.get("ratio_pct")
        if mom is not None and mom > 15 and (ratio is None or ratio >= 0.5):
            anomalies.append({
                "type": "expense_abnormal_increase",
                "category_key": s.get("category_key"),
                "label_key": s.get("label_key"),
                "mom_change_pct": mom,
                "ratio_pct": ratio,
                "amount_delta": s.get("mom_amount_delta"),
                "evidence": {
                    "threshold_pct": 15,
                    "basis": "group_mom_change_pct",
                },
            })

    # Also include engine insights with explicit linkage to metrics (already data-based)
    for ins in (raw.get("insights") or []):
        sev = ins.get("severity")
        if sev in ("high", "warning", "critical"):
            anomalies.append({
                "type": ins.get("type"),
                "severity": sev,
                "what_happened": ins.get("what_happened"),
                "why_it_matters": ins.get("why_it_matters"),
                "what_to_do": ins.get("what_to_do"),
                "source_metrics": ins.get("source_metrics") or [],
            })

    # Deterministic cost pressure from aligned summary + thresholds
    thr = raw.get("thresholds") or {}
    tc_thr = (thr.get("total_cost_ratio_pct") or thr.get("expense_ratio_pct") or {})
    tc_st = tc_thr.get("status") or "unknown"
    ox_thr = thr.get("opex_ratio_pct") or {}
    ox_st = ox_thr.get("status") or "unknown"
    tc_val = summary.get("total_cost_ratio_pct")
    ox_val = summary.get("opex_ratio_pct")
    prim = summary.get("primary_pressure")

    flags: list[dict] = []
    if tc_st in ("critical", "warning", "elevated"):
        flags.append({
            "type": "total_cost_pressure",
            "severity": "high" if tc_st == "critical" else "medium",
            "metric": "total_cost_ratio_pct",
            "value": tc_val,
            "threshold_status": tc_st,
        })
    if ox_st in ("critical", "warning", "elevated"):
        flags.append({
            "type": "opex_pressure",
            "severity": "high" if ox_st == "critical" else "medium",
            "metric": "opex_ratio_pct",
            "value": ox_val,
            "threshold_status": ox_st,
        })
    for s in structure[:5]:
        m = s.get("mom_change_pct")
        if m is not None and m > 8:
            flags.append({
                "type": "category_mom_spike",
                "severity": "medium",
                "metric": "group_amount_mom_pct",
                "category_key": s.get("category_key"),
                "value": m,
            })

    if tc_val is not None and ox_val is not None and ox_val > 0 and tc_val > ox_val + 1:
        press_note = "COGS-inclusive cost base is material relative to OpEx alone — review gross margin and direct costs alongside operating spend."
    elif ox_st in ("critical", "warning"):
        press_note = "Operating expense load vs revenue is elevated relative to internal targets."
    elif tc_st in ("critical", "warning"):
        press_note = "Full cost load (COGS + OpEx + unclassified P&L debits) vs revenue is elevated."
    else:
        press_note = "Cost ratios are within neutral bands versus default SME thresholds; continue monitoring category movers."

    pressure_level = "high" if tc_st == "critical" or ox_st == "critical" else (
        "medium" if tc_st in ("warning", "elevated") or ox_st in ("warning", "elevated") else "low"
    )

    return {
        "latest_period": raw.get("latest_period"),
        "periods": raw.get("periods") or [],
        "summary": summary,
        "top_drivers": top_drivers,
        "anomalies": anomalies[:12],
        "structure": structure,
        "pressure_assessment": {
            "pressure_level": pressure_level,
            "primary_pressure_category": prim,
            "headline_metrics": {
                "total_cost_ratio_pct": tc_val,
                "opex_ratio_pct": ox_val,
                "cogs_ratio_pct": summary.get("cogs_ratio_pct"),
            },
            "interpretation": press_note,
            "flags": flags[:8],
        },
    }


def build_trend_intelligence_deep(analysis: dict) -> dict:
    """
    Trend intelligence using analysis_engine trend series (no new statements).
    Signals include acceleration, volatility, and consistent decline flags.
    """
    tr = (analysis or {}).get("trends") or {}
    rev_mom = tr.get("revenue_mom_pct") or []
    np_mom  = tr.get("net_profit_mom_pct") or []
    exp_mom = tr.get("expenses_mom_pct") or []

    rev_cv = _cv(rev_mom[-6:])
    np_cv  = _cv(np_mom[-6:])
    exp_cv = _cv(exp_mom[-6:]) if exp_mom else None

    signals = []

    ra = _accel(rev_mom)
    if ra is not None and abs(ra) >= 5:
        signals.append({
            "type": "revenue_acceleration" if ra > 0 else "revenue_deceleration",
            "metric": "revenue_mom_pct",
            "value": ra,
            "evidence": {"method": "avg(last2)-avg(prev2)", "threshold": 5},
        })

    na = _accel(np_mom)
    if na is not None and abs(na) >= 5:
        signals.append({
            "type": "profit_acceleration" if na > 0 else "profit_deceleration",
            "metric": "net_profit_mom_pct",
            "value": na,
            "evidence": {"method": "avg(last2)-avg(prev2)", "threshold": 5},
        })

    if rev_cv is not None and rev_cv >= 1.0:
        signals.append({
            "type": "revenue_high_volatility",
            "metric": "revenue_mom_pct",
            "value": rev_cv,
            "evidence": {"method": "cv(last6)", "threshold": 1.0},
        })
    if np_cv is not None and np_cv >= 1.0:
        signals.append({
            "type": "profit_high_volatility",
            "metric": "net_profit_mom_pct",
            "value": np_cv,
            "evidence": {"method": "cv(last6)", "threshold": 1.0},
        })

    # Consistent decline (last 3 MoM below -0.5)
    def _decline3(m):
        v = [x for x in (m or []) if x is not None][-3:]
        return len(v) == 3 and all(x < -0.5 for x in v)
    if _decline3(rev_mom):
        signals.append({"type": "revenue_consistent_decline", "metric": "revenue_mom_pct", "value": None,
                        "evidence": {"rule": "last3 < -0.5"}})
    if _decline3(np_mom):
        signals.append({"type": "profit_consistent_decline", "metric": "net_profit_mom_pct", "value": None,
                        "evidence": {"rule": "last3 < -0.5"}})

    # Unstable series: high coefficient of variation on MoM % changes
    if rev_cv is not None and rev_cv >= 1.25:
        signals.append({
            "type": "unstable_revenue",
            "metric": "revenue_mom_pct",
            "value": rev_cv,
            "evidence": {"method": "cv(last6)", "threshold": 1.25, "meaning": "high_month_to_month_variability"},
        })
    if np_cv is not None and np_cv >= 1.25:
        signals.append({
            "type": "unstable_profit",
            "metric": "net_profit_mom_pct",
            "value": np_cv,
            "evidence": {"method": "cv(last6)", "threshold": 1.25, "meaning": "high_month_to_month_variability"},
        })
    if (
        rev_cv is not None and np_cv is not None
        and np_cv >= 1.0 and rev_cv < 0.85
        and len([x for x in np_mom if x is not None]) >= 4
    ):
        signals.append({
            "type": "profit_volatility_exceeds_revenue",
            "metric": "net_profit_mom_pct_vs_revenue_mom_pct",
            "value": round(np_cv - rev_cv, 4),
            "evidence": {
                "np_cv": np_cv,
                "revenue_cv": rev_cv,
                "meaning": "earnings_less_predictable_than_sales",
            },
        })

    exp_accel = _accel(exp_mom)
    if exp_accel is not None and abs(exp_accel) >= 5:
        signals.append({
            "type": "operating_cost_momentum_shift",
            "metric": "expenses_mom_pct",
            "value": exp_accel,
            "evidence": {"method": "avg(last2)-avg(prev2)", "threshold": 5},
        })

    return {
        "signals": signals,
        "series_stats": {
            "revenue_mom_cv_6": rev_cv,
            "net_profit_mom_cv_6": np_cv,
            "expenses_mom_cv_6": exp_cv,
        },
    }


def build_profitability_intelligence_deep(
    period_statements: list[dict],
    analysis: Optional[dict] = None,
    trend_signals: Optional[list] = None,
) -> dict:
    """
    Margin deltas and a deterministic decomposition of net profit change.
    Uses statement_engine outputs only (income_statement totals).
    """
    if not period_statements:
        return {"available": False}
    latest = period_statements[-1].get("income_statement", {}) or {}
    prior  = period_statements[-2].get("income_statement", {}) if len(period_statements) >= 2 else {}
    prior  = prior or {}

    r1 = (latest.get("revenue", {}) or {}).get("total")
    c1 = (latest.get("cogs", {}) or {}).get("total")
    o1 = (latest.get("expenses", {}) or {}).get("total")
    t1 = (latest.get("tax", {}) or {}).get("total")
    n1 = latest.get("net_profit")

    r0 = (prior.get("revenue", {}) or {}).get("total")
    c0 = (prior.get("cogs", {}) or {}).get("total")
    o0 = (prior.get("expenses", {}) or {}).get("total")
    t0 = (prior.get("tax", {}) or {}).get("total")
    n0 = prior.get("net_profit")

    gm1 = latest.get("gross_margin_pct")
    nm1 = latest.get("net_margin_pct")
    gm0 = prior.get("gross_margin_pct")
    nm0 = prior.get("net_margin_pct")

    gm_pp = round(gm1 - gm0, 2) if (gm1 is not None and gm0 is not None) else None
    nm_pp = round(nm1 - nm0, 2) if (nm1 is not None and nm0 is not None) else None

    # Decomposition of ΔNP
    drivers = []
    if r1 is not None and r0 is not None and n0 is not None and r0 not in (None, 0):
        prev_nm = _safe_pct(n0, r0)
        if prev_nm is not None:
            rev_effect = _r2((r1 - r0) * (prev_nm / 100))
            drivers.append({"driver": "revenue_effect", "amount": rev_effect, "basis": "ΔRevenue × prior net margin"})

    if r1 not in (None, 0) and c1 is not None and c0 is not None and r0 not in (None, 0) and c0 is not None:
        cogs_pct0 = _safe_pct(c0, r0)
        cogs_pct1 = _safe_pct(c1, r1)
        if cogs_pct0 is not None and cogs_pct1 is not None:
            delta_pp = round(cogs_pct1 - cogs_pct0, 2)
            drivers.append({"driver": "cogs_ratio_change_pp", "value_pp": delta_pp, "basis": "COGS%_t - COGS%_{t-1}"})

    if r1 not in (None, 0) and o1 is not None and o0 is not None and r0 not in (None, 0):
        opex_pct0 = _safe_pct(o0, r0)
        opex_pct1 = _safe_pct(o1, r1)
        if opex_pct0 is not None and opex_pct1 is not None:
            delta_pp = round(opex_pct1 - opex_pct0, 2)
            drivers.append({"driver": "opex_ratio_change_pp", "value_pp": delta_pp, "basis": "OpEx%_t - OpEx%_{t-1}"})

    u0 = float((prior.get("unclassified_pnl_debits") or {}).get("total") or 0)
    u1 = float((latest.get("unclassified_pnl_debits") or {}).get("total") or 0)
    tc0 = total_cost_ratio_pct(c0, o0, r0, u0) if r0 not in (None, 0) else None
    tc1 = total_cost_ratio_pct(c1, o1, r1, u1) if r1 not in (None, 0) else None
    tc_pp = round(tc1 - tc0, 2) if (tc0 is not None and tc1 is not None) else None
    if tc_pp is not None:
        drivers.append({
            "driver": "total_cost_ratio_change_pp",
            "value_pp": tc_pp,
            "basis": "total_cost_ratio_t - total_cost_ratio_{t-1}",
        })

    # Operating pressure & earnings quality (deterministic labels only when rules fire)
    opex_pp = next((d.get("value_pp") for d in drivers if d.get("driver") == "opex_ratio_change_pp"), None)
    cogs_pp_d = next((d.get("value_pp") for d in drivers if d.get("driver") == "cogs_ratio_change_pp"), None)
    op_press = "low"
    if opex_pp is not None and opex_pp > 2.0:
        op_press = "high"
    elif opex_pp is not None and opex_pp > 0.75:
        op_press = "medium"
    elif cogs_pp_d is not None and cogs_pp_d > 2.0:
        op_press = "high"
    elif cogs_pp_d is not None and cogs_pp_d > 0.75:
        op_press = "medium"

    earn_quality = "neutral"
    tr_signals: list[dict] = list(trend_signals or [])
    types = {s.get("type") for s in tr_signals}
    if not tr_signals and analysis:
        tr_signals = (build_trend_intelligence_deep(analysis) or {}).get("signals") or []
        types = {s.get("type") for s in tr_signals}
    if "profit_volatility_exceeds_revenue" in types or (
        "unstable_profit" in types and "unstable_revenue" not in types
    ):
        earn_quality = "volatile_earnings_vs_sales"
    elif "profit_consistent_decline" in types:
        earn_quality = "deteriorating_earnings_trend"
    elif nm_pp is not None and nm_pp >= 1.0 and (r1 is not None and r0 is not None and r1 > r0):
        earn_quality = "margin_expanding_with_revenue"

    rev_eff = next((d.get("amount") for d in drivers if d.get("driver") == "revenue_effect"), None)
    interpretation: dict[str, Any] = {
        "operating_pressure": op_press,
        "earnings_quality": earn_quality,
        "margin_change_pp": {"gross": gm_pp, "net": nm_pp},
        "total_cost_ratio_change_pp": tc_pp,
        "revenue_bridge_effect_units": rev_eff,
        "notes": [],
    }
    if op_press == "high":
        interpretation["notes"].append(
            "Cost ratios worsened materially vs prior period — prioritize gross margin and OpEx levers."
        )
    if earn_quality == "volatile_earnings_vs_sales":
        interpretation["notes"].append(
            "Profit month-to-month volatility exceeds revenue volatility — investigate one-off items, mix, or timing."
        )
    elif earn_quality == "deteriorating_earnings_trend":
        interpretation["notes"].append("Several consecutive profit MoM readings are weak — confirm cost and price discipline.")

    return {
        "available": True,
        "latest_period": (period_statements[-1].get("period") if period_statements else None),
        "margin_change_pp": {
            "gross_margin_pp": gm_pp,
            "net_margin_pp": nm_pp,
        },
        "delta": {
            "revenue": _r2(r1 - r0) if (r1 is not None and r0 is not None) else None,
            "net_profit": _r2(n1 - n0) if (n1 is not None and n0 is not None) else None,
            "cogs": _r2(c1 - c0) if (c1 is not None and c0 is not None) else None,
            "opex": _r2(o1 - o0) if (o1 is not None and o0 is not None) else None,
            "tax": _r2(t1 - t0) if (t1 is not None and t0 is not None) else None,
        },
        "drivers": drivers,
        "interpretation": interpretation,
        "trend_signal_types": [s.get("type") for s in tr_signals],
    }


_EXEC_PI_TEXT = {
    "strong_but_heavy": {
        "en": "Profitability is strong but cost structure is heavy.",
        "ar": "الربحية قوية لكن هيكل التكاليف مرتفع.",
        "tr": "Karlılık güçlü ancak maliyet yapısı ağır.",
    },
    "margins_declining_expenses": {
        "en": "Margins are declining due to rising expenses.",
        "ar": "الهوامش في تراجع بسبب ارتفاع المصروفات.",
        "tr": "Marjlar, giderlerin artmasıyla düşüyor.",
    },
    "rev_not_profit": {
        "en": "Revenue growth is not translating into profit.",
        "ar": "نمو الإيرادات لا يتحول إلى ربح.",
        "tr": "Gelir büyümesi kara dönmüyor.",
    },
    "neutral": {
        "en": "Profitability metrics are within the current observed range; monitor margin and cost ratios.",
        "ar": "مؤشرات الربحية ضمن النطاق الملاحظ حالياً؛ تابع نسب الهامش والتكاليف.",
        "tr": "Karlılık göstergeleri gözlenen aralıkta; marj ve maliyet oranlarını izleyin.",
    },
}

_EXEC_TREND_TEXT = {
    "rev_up_profit_down": {
        "en": "Revenue growing but profitability declining.",
        "ar": "الإيرادات في نمو لكن الربحية تتراجع.",
        "tr": "Gelir büyüyor ancak karlılık düşüyor.",
    },
    "strong_upward": {
        "en": "Strong upward trend.",
        "ar": "اتجاه صاعد قوي.",
        "tr": "Güçlü yukarı yönlü trend.",
    },
    "volatility": {
        "en": "Volatility detected.",
        "ar": "تم رصد تقلبات.",
        "tr": "Oynaklık tespit edildi.",
    },
}


def build_executive_trend_analysis(
    windowed: list[dict],
    analysis: dict,
    lang: str = "en",
) -> dict:
    """
    Trend Analysis (Phase 1): current vs previous period deltas + volatility signal.
    Deterministic; uses windowed statements + run_analysis() trends only.
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"
    if not windowed:
        return {"available": False, "reason": "no_statements"}
    if len(windowed) < 2:
        return {"available": False, "reason": "need_prev_period"}

    cur_is = (windowed[-1].get("income_statement") or {})
    prev_is = (windowed[-2].get("income_statement") or {})

    r1 = (cur_is.get("revenue", {}) or {}).get("total")
    r0 = (prev_is.get("revenue", {}) or {}).get("total")
    n1 = cur_is.get("net_profit")
    n0 = prev_is.get("net_profit")
    nm1 = cur_is.get("net_margin_pct")
    nm0 = prev_is.get("net_margin_pct")

    def _pct(curr, prev):
        try:
            curr = float(curr); prev = float(prev)
            if abs(prev) < 0.001:
                return None
            return round((curr - prev) / abs(prev) * 100, 2)
        except Exception:
            return None

    rev_growth = _pct(r1, r0)
    profit_growth = _pct(n1, n0)
    try:
        margin_change_pp = round(float(nm1) - float(nm0), 2) if (nm1 is not None and nm0 is not None) else None
    except Exception:
        margin_change_pp = None

    trend_block = build_trend_intelligence_deep(analysis or {})
    sig_types = {s.get("type") for s in (trend_block.get("signals") or [])}
    vol = (
        "unstable_revenue" in sig_types
        or "unstable_profit" in sig_types
        or "revenue_high_volatility" in sig_types
        or "profit_high_volatility" in sig_types
    )

    insights: list[str] = []
    signals: dict[str, bool] = {}

    if rev_growth is not None and rev_growth > 0 and (
        (profit_growth is not None and profit_growth < 0) or (margin_change_pp is not None and margin_change_pp < -0.5)
    ):
        insights.append(_EXEC_TREND_TEXT["rev_up_profit_down"][lang])
        signals["revenue_up_profitability_down"] = True

    if rev_growth is not None and profit_growth is not None and rev_growth >= 5 and profit_growth >= 5 and (margin_change_pp is None or margin_change_pp >= 0):
        insights.append(_EXEC_TREND_TEXT["strong_upward"][lang])
        signals["strong_upward_trend"] = True

    if vol:
        insights.append(_EXEC_TREND_TEXT["volatility"][lang])
        signals["volatility_detected"] = True

    # Dedupe in order
    seen = set()
    uniq = []
    for x in insights:
        if x not in seen:
            seen.add(x); uniq.append(x)

    return {
        "available": True,
        "current_period": windowed[-1].get("period"),
        "previous_period": windowed[-2].get("period"),
        "metrics": {
            "revenue_growth_pct": rev_growth,
            "profit_growth_pct": profit_growth,
            "margin_change_pp": margin_change_pp,
        },
        "volatility": {
            "detected": vol,
            "series_stats": trend_block.get("series_stats") or {},
            "signal_types": sorted([t for t in sig_types if t]),
        },
        "interpretation": {
            "insights": uniq[:5],
            "signals": signals,
        },
    }


_EXEC_FC_TEXT = {
    "growth": {
        "en": "Expected growth continues.",
        "ar": "من المتوقع استمرار النمو.",
        "tr": "Beklenen büyüme devam ediyor.",
    },
    "slowdown": {
        "en": "Potential slowdown ahead.",
        "ar": "قد يكون هناك تباطؤ قادم.",
        "tr": "Önümüzde olası bir yavaşlama var.",
    },
    "neutral": {
        "en": "Next-period outlook is broadly stable based on recent trend.",
        "ar": "توقع الفترة القادمة مستقر بشكل عام وفقاً للاتجاه الأخير.",
        "tr": "Son trende göre bir sonraki dönem görünümü genel olarak stabil.",
    },
}

_EXEC_FC_INSUFFICIENT = {
    "en": "Not enough historical periods to project next revenue and profit.",
    "ar": "لا توجد فترات تاريخية كافية لتقدير الإيرادات وصافي الربح للفترة التالية.",
    "tr": "Bir sonraki dönem gelir ve net kar için yeterli geçmiş yok.",
}

_EXEC_FC_ENGINE = {
    "en": "Forecast could not be computed from the current analysis state.",
    "ar": "تعذر حساب التوقع من حالة التحليل الحالية.",
    "tr": "Mevcut analiz durumundan tahmin hesaplanamadı.",
}

_EXEC_FC_PROFIT_GAP = {
    "en": " Net profit projection is omitted due to missing profit history in the window.",
    "ar": " تم حذف توقع صافي الربح لعدم توفر سلسلة أرباح كافية في النافذة.",
    "tr": " Net kar tahmini pencerede yeterli kar geçmişi olmadığı için çıkarılmadı.",
}


def build_executive_forecast_unavailable(
    lang: str = "en",
    *,
    reason: str = "insufficient_data",
) -> dict:
    """
    Canonical 5-field forecast shell when projection is not possible.
    reason: insufficient_data | unavailable
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"
    if reason == "unavailable":
        insight = _EXEC_FC_ENGINE[lang]
        method = "unavailable"
    else:
        insight = _EXEC_FC_INSUFFICIENT[lang]
        method = "insufficient_data"
    return {
        "next_revenue": None,
        "next_profit": None,
        "method_used": method,
        "confidence_level": 0,
        "insight": insight,
    }


def _fc_confidence_score(
    rev_tail: list[float],
    np_tail: list[float],
    rev_method: str,
    np_method: str,
    next_np_is_none: bool,
) -> int:
    """Deterministic 0–100 from sample depth and revenue coefficient of variation."""
    if rev_method == "insufficient_data":
        return 0
    n = len(rev_tail)
    if n <= 0:
        return 0
    if n == 1:
        base = 34
    elif n == 2:
        base = 56
    else:
        base = min(100, 48 + n * 14)
    cv = _cv(rev_tail)
    if cv is not None:
        if cv > 0.40:
            base -= 30
        elif cv > 0.22:
            base -= 18
        elif cv > 0.10:
            base -= 8
    if next_np_is_none:
        base -= 18
    elif np_method == "single_period_baseline" and rev_method == "linear_trend":
        base -= 6
    elif np_method == "insufficient_data":
        base -= 14
    return max(0, min(100, int(base)))


def _fc_project_series(tail: list[float]) -> tuple[float | None, str]:
    """
    One-step ahead from the last n levels.
    Returns (point_forecast, method_tag).
    - 2+ points: linear trend — mean of the last one or two period-on-period deltas, applied to last level.
    - 1 point: single-period baseline (next step equals last observation; degenerate moving average of window 1).
    """
    if not tail:
        return None, "insufficient_data"
    if len(tail) >= 2:
        d1 = tail[-1] - tail[-2]
        if len(tail) >= 3:
            d2 = tail[-2] - tail[-3]
            delta = (d1 + d2) / 2.0
        else:
            delta = d1
        return _r2(tail[-1] + delta), "linear_trend"
    return _r2(tail[-1]), "single_period_baseline"


def build_executive_basic_forecast(
    windowed: list[dict],
    analysis: dict,
    lang: str = "en",
    n: int = 3,
) -> dict:
    """
    Phase 5 — mandatory executive forecast block (deterministic).

    Output keys (fixed contract):
      next_revenue, next_profit, method_used, confidence_level, insight
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"
    if not windowed:
        return build_executive_forecast_unavailable(lang, reason="insufficient_data")

    tr = (analysis or {}).get("trends") or {}

    def _fallback_series(key: str) -> list[float]:
        out: list[float] = []
        for s in windowed:
            is_ = (s.get("income_statement") or {})
            if key == "revenue":
                v = (is_.get("revenue") or {}).get("total")
            else:
                v = is_.get("net_profit")
            try:
                if v is not None:
                    out.append(float(v))
            except Exception:
                pass
        return out

    rev_full = [float(x) for x in (tr.get("revenue_series") or []) if x is not None]
    if not rev_full:
        rev_full = _fallback_series("revenue")
    np_full = [float(x) for x in (tr.get("net_profit_series") or []) if x is not None]
    if not np_full:
        np_full = _fallback_series("net_profit")

    if not rev_full:
        return build_executive_forecast_unavailable(lang, reason="insufficient_data")

    rev_tail = rev_full[-n:] if len(rev_full) > n else rev_full[:]
    np_tail = np_full[-n:] if len(np_full) > n else np_full[:]

    next_rev, rev_m = _fc_project_series(rev_tail)
    next_np, np_m = _fc_project_series(np_tail) if np_tail else (None, "insufficient_data")

    # Revenue rule is the declared method; profit uses the same logic when history exists.
    method_used = rev_m

    last_rev = _r2(rev_full[-1])
    insight = _EXEC_FC_TEXT["neutral"][lang]
    if last_rev is not None and next_rev is not None and abs(last_rev) > 0.001:
        pct = (next_rev - last_rev) / abs(last_rev) * 100
        if pct >= 1.0:
            insight = _EXEC_FC_TEXT["growth"][lang]
        elif pct <= -1.0:
            insight = _EXEC_FC_TEXT["slowdown"][lang]

    if next_np is None and rev_m != "insufficient_data":
        insight = (insight.rstrip() + _EXEC_FC_PROFIT_GAP[lang]).strip()

    conf = _fc_confidence_score(
        rev_tail, np_tail, rev_m, np_m, next_np is None,
    )

    return {
        "next_revenue": next_rev,
        "next_profit": next_np,
        "method_used": method_used,
        "confidence_level": conf,
        "insight": insight,
    }


def build_executive_profitability_intelligence(
    windowed: list[dict],
    analysis: dict,
    lang: str = "en",
) -> dict:
    """
    Financial Brain Phase 1 — compact profitability block for executive payload.
    Deterministic; uses windowed statements + run_analysis() output only.
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"
    if not windowed:
        return {"available": False, "reason": "no_statements"}

    deep_pi = build_profitability_intelligence_deep(windowed, analysis, trend_signals=None)
    latest = windowed[-1].get("income_statement", {}) or {}
    r = (latest.get("revenue", {}) or {}).get("total")
    cogs = (latest.get("cogs", {}) or {}).get("total")
    opex = (latest.get("expenses", {}) or {}).get("total")
    np_val = latest.get("net_profit")

    gm_stmt = latest.get("gross_margin_pct")
    nm_stmt = latest.get("net_margin_pct")
    try:
        r_f = float(r) if r is not None else None
    except (TypeError, ValueError):
        r_f = None
    try:
        c_f = float(cogs) if cogs is not None else None
    except (TypeError, ValueError):
        c_f = None
    try:
        o_f = float(opex) if opex is not None else None
    except (TypeError, ValueError):
        o_f = None

    gm_pct = _r2(gm_stmt) if gm_stmt is not None else None
    if gm_pct is None and r_f is not None and abs(r_f) > 0.001 and c_f is not None:
        gm_pct = _safe_pct(r_f - c_f, r_f)

    contrib_available = r_f is not None and abs(r_f) > 0.001 and c_f is not None
    contrib_pct = _safe_pct(r_f - c_f, r_f) if contrib_available else None

    cogs_pct = _safe_pct(c_f, r_f) if (r_f is not None and abs(r_f) > 0.001 and c_f is not None) else None
    opex_pct = _safe_pct(o_f, r_f) if (r_f is not None and abs(r_f) > 0.001 and o_f is not None) else None
    net_margin_pct = _r2(nm_stmt) if nm_stmt is not None else _safe_pct(np_val, r_f)

    total_cost_share = None
    if cogs_pct is not None and opex_pct is not None:
        total_cost_share = round(cogs_pct + opex_pct, 2)

    interp = (deep_pi.get("interpretation") or {}) if deep_pi.get("available") else {}
    nm_pp = (interp.get("margin_change_pp") or {}).get("net")
    opex_pp_driver = next(
        (d.get("value_pp") for d in (deep_pi.get("drivers") or []) if d.get("driver") == "opex_ratio_change_pp"),
        None,
    )

    prior = windowed[-2].get("income_statement", {}) if len(windowed) >= 2 else {}
    r0 = (prior.get("revenue", {}) or {}).get("total") if prior else None
    n0 = prior.get("net_profit") if prior else None
    rev_up_period = False
    try:
        if r_f is not None and r0 is not None and float(r0) != 0:
            rev_up_period = r_f > float(r0)
    except (TypeError, ValueError):
        rev_up_period = False

    tr = analysis.get("trends") or {}
    rev_dir = (tr.get("revenue") or {}).get("direction", "insufficient_data")
    np_dir = (tr.get("net_profit") or {}).get("direction", "insufficient_data")

    insights: list[str] = []
    signals: dict[str, bool] = {}

    # Rule 1: strong net margin but heavy cost load vs revenue
    if (
        net_margin_pct is not None
        and net_margin_pct >= 8.0
        and total_cost_share is not None
        and total_cost_share >= 72.0
    ):
        insights.append(_EXEC_PI_TEXT["strong_but_heavy"][lang])
        signals["strong_profit_heavy_cost_structure"] = True

    # Rule 2: margin compression from expenses (period-over-period + trend)
    if opex_pp_driver is not None and opex_pp_driver > 0.5 and nm_pp is not None and nm_pp < -0.5:
        insights.append(_EXEC_PI_TEXT["margins_declining_expenses"][lang])
        signals["margin_decline_expense_pressure"] = True
    elif np_dir == "down" and rev_dir in ("up", "stable") and opex_pp_driver is not None and opex_pp_driver > 0.25:
        insights.append(_EXEC_PI_TEXT["margins_declining_expenses"][lang])
        signals["margin_decline_expense_pressure"] = True

    # Rule 3: revenue up, profit not following
    if rev_up_period:
        try:
            n1f = float(np_val) if np_val is not None else None
            n0f = float(n0) if n0 is not None else None
        except (TypeError, ValueError):
            n1f = n0f = None
        if n1f is not None and n0f is not None and (n1f <= n0f or (nm_pp is not None and nm_pp < 0)):
            insights.append(_EXEC_PI_TEXT["rev_not_profit"][lang])
            signals["revenue_growth_not_flowing_to_profit"] = True
    if rev_dir == "up" and np_dir == "down" and _EXEC_PI_TEXT["rev_not_profit"][lang] not in insights:
        insights.append(_EXEC_PI_TEXT["rev_not_profit"][lang])
        signals["revenue_growth_not_flowing_to_profit"] = True

    # Dedupe while preserving order
    seen: set[str] = set()
    uniq_insights: list[str] = []
    for x in insights:
        if x not in seen:
            seen.add(x)
            uniq_insights.append(x)
    insights = uniq_insights[:5]

    headline = insights[0] if insights else _EXEC_PI_TEXT["neutral"][lang]

    return {
        "available": True,
        "latest_period": windowed[-1].get("period"),
        "lang": lang,
        "margins": {
            "gross_margin_pct": gm_pct,
            "contribution_margin_pct": contrib_pct,
            "contribution_margin_available": contrib_available,
            "contribution_margin_basis": (
                "revenue_minus_cogs_over_revenue"
                if contrib_available
                else None
            ),
            "net_margin_pct": net_margin_pct,
        },
        "expense_ratio_breakdown": {
            "cogs_pct": cogs_pct,
            "operating_expenses_pct": opex_pct,
            "net_margin_pct": net_margin_pct,
            "cogs_plus_opex_pct": total_cost_share,
        },
        "interpretation": {
            "headline": headline,
            "insights": insights if insights else [headline],
            "signals": signals,
        },
    }


def build_deep_intelligence(
    period_statements: list[dict],
    analysis: dict,
    lang: str = "en",
) -> dict:
    trend_block = build_trend_intelligence_deep(analysis)
    sigs = (trend_block or {}).get("signals") or []
    return {
        "expense_intelligence": build_expense_intelligence_deep(period_statements, lang=lang),
        "trend_intelligence": trend_block,
        "profitability_intelligence": build_profitability_intelligence_deep(
            period_statements, analysis, trend_signals=sigs
        ),
    }

