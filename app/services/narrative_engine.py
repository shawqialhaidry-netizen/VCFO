"""
narrative_engine.py — Phase 17
Deterministic, template-based narrative engine.
Converts structured analysis data into business-readable text.

Design rules:
  - Pure function — no DB, no HTTP, no LLM
  - Deterministic: same inputs → same output
  - Language-aware: 'ar' produces Arabic text, else English
  - Never crashes on missing data — every path is null-safe
  - No internal keys or technical variable names in output text
"""
from __future__ import annotations
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
#  Formatting helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmtK(v: Optional[float], currency: str = "") -> str:
    if v is None:
        return "—"
    a = abs(v)
    s = "-" if v < 0 else ""
    if a >= 1_000_000:
        return f"{s}{a/1_000_000:.1f}M {currency}".strip()
    if a >= 1_000:
        return f"{s}{a/1_000:.0f}K {currency}".strip()
    return f"{s}{a:.0f} {currency}".strip()


def _fmtP(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"{v:.1f}%"


def _pchg(v: Optional[float]) -> str:
    if v is None:
        return ""
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


def _pp(v: Optional[float]) -> str:
    if v is None:
        return ""
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f} pp"


# ──────────────────────────────────────────────────────────────────────────────
#  Language templates
# ──────────────────────────────────────────────────────────────────────────────

def _t(key: str, lang: str, **kwargs) -> str:
    """
    Fetch a narrative template string and format with kwargs.
    Falls back to English if key not found in requested language.
    """
    templates = _TEMPLATES.get(lang, _TEMPLATES["en"])
    tpl = templates.get(key) or _TEMPLATES["en"].get(key, key)
    try:
        return tpl.format(**kwargs)
    except (KeyError, IndexError):
        return tpl


_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        # Executive summary openings
        "summary_excellent":  "The business is performing strongly. {period_label} shows revenue of {revenue} with a net margin of {net_margin}.",
        "summary_good":       "The business is in a healthy position. {period_label} revenue reached {revenue} with a net margin of {net_margin}.",
        "summary_warning":    "The business requires attention. {period_label} revenue was {revenue} but profitability pressures are present, with a net margin of {net_margin}.",
        "summary_critical":   "The business is under significant financial stress. {period_label} net margin stands at {net_margin}, requiring immediate action.",
        "summary_neutral":    "Financial performance for {period_label}: revenue {revenue}, net profit {net_profit}, net margin {net_margin}.",

        # YTD comparison
        "ytd_vs_prior_up":    "YTD revenue is {ytd_rev} ({ytd_rev_chg} vs prior year), with net profit of {ytd_np} ({ytd_np_chg} vs prior year).",
        "ytd_vs_prior_down":  "YTD revenue is {ytd_rev} ({ytd_rev_chg} vs prior year). Net profit has declined to {ytd_np} ({ytd_np_chg}).",
        "ytd_no_prior":       "YTD to {period}: revenue {ytd_rev}, net profit {ytd_np}, net margin {ytd_nm}.",

        # Full year
        "fy_complete":        "Full-year {year}: revenue {rev}, net profit {np}, net margin {nm}.",
        "fy_partial":         "Year {year} is partial ({months} of 12 months available): revenue to date {rev}, net profit {np}.",
        "fy_gap":             "Note: year {year} has missing months — reported totals may be understated.",

        # Takeaways
        "tk_revenue_up":      "Revenue is growing — {period_label} up {chg} compared to prior period.",
        "tk_revenue_down":    "Revenue declined {chg} compared to prior period — investigate Revenue Drivers.",
        "tk_margin_up":       "Net margin improved by {pp} to {nm} — cost discipline is working.",
        "tk_margin_down":     "Net margin declined by {pp} to {nm} — review cost structure.",
        "tk_margin_flat":     "Net margin is stable at {nm}.",
        "tk_ytd_ahead":       "YTD performance is ahead of the same period last year by {chg}.",
        "tk_ytd_behind":      "YTD performance is behind the same period last year by {chg}.",
        "tk_partial_year":    "Current year is partial — {months} months of data available. Full-year conclusions should be drawn cautiously.",
        "tk_gaps":            "Data gaps detected in {year} — {n} month(s) missing. Reported figures may be incomplete.",

        # Risks
        "risk_negative_profit":    "Net profit is negative. The business is currently operating at a loss.",
        "risk_low_margin":         "Net margin below 5% ({nm}) — limited buffer for cost increases or revenue shortfalls.",
        "risk_declining_revenue":  "Revenue is declining — sustained trend may threaten cash flow.",
        "risk_partial_basis":      "Narrative is based on partial-year data. Year-end results may differ significantly.",
        "risk_no_prior":           "No prior-year data available for comparison — trend analysis is limited.",
        "risk_data_gaps":          "Data gaps in the reporting period may affect the accuracy of reported totals.",

        # Recommended action
        "action_combined":         "Priority action: Accelerate Growth — increase Revenue by 5% while reducing Cost of Goods Sold and Operating Expenses by 2% each. This scenario is projected to improve Net Profit by {np_delta} ({np_pct}) and Net Margin by {mm_pp}.",
        "action_increase_revenue": "Priority action: Grow Revenue — a 5% revenue increase is projected to improve net profit by {np_delta} ({np_pct}) with no change to cost structure.",
        "action_reduce_cogs":      "Priority action: Optimize Cost of Goods Sold — reducing Cost of Goods Sold by 2% is projected to add {np_delta} ({np_pct}) to Net Profit.",
        "action_reduce_opex":      "Priority action: Reduce Operating Expenses — a 2% reduction in Operating Expenses is projected to add {np_delta} ({np_pct}) to Net Profit.",
        "action_none":             "No recommendation available yet. Upload financial data and run Financial Intelligence to generate a recommended action.",
    },

    "ar": {
        "summary_excellent":  "الأعمال تسير بقوة. {period_label} أظهر إيرادات بلغت {revenue} بهامش صافٍ {net_margin}.",
        "summary_good":       "الأعمال في وضع صحي. إيرادات {period_label} بلغت {revenue} بهامش صافٍ {net_margin}.",
        "summary_warning":    "الأعمال تستدعي الاهتمام. إيرادات {period_label} بلغت {revenue} مع ضغوط على الربحية، الهامش الصافي {net_margin}.",
        "summary_critical":   "الأعمال تواجه ضغطاً مالياً. الهامش الصافي في {period_label} هو {net_margin}، يستلزم تدخلاً فورياً.",
        "summary_neutral":    "الأداء المالي لـ {period_label}: إيرادات {revenue}، صافي ربح {net_profit}، هامش صافٍ {net_margin}.",

        "ytd_vs_prior_up":    "إيرادات منذ بداية العام {ytd_rev} ({ytd_rev_chg} مقارنة بالسنة السابقة)، صافي الربح {ytd_np} ({ytd_np_chg}).",
        "ytd_vs_prior_down":  "إيرادات منذ بداية العام {ytd_rev} ({ytd_rev_chg} مقارنة بالسنة السابقة). تراجع صافي الربح إلى {ytd_np} ({ytd_np_chg}).",
        "ytd_no_prior":       "حتى {period}: إيرادات {ytd_rev}، صافي ربح {ytd_np}، هامش صافٍ {ytd_nm}.",

        "fy_complete":        "السنة الكاملة {year}: إيرادات {rev}، صافي ربح {np}، هامش صافٍ {nm}.",
        "fy_partial":         "عام {year} جزئي ({months} من 12 شهراً): إيرادات حتى الآن {rev}، صافي ربح {np}.",
        "fy_gap":             "تنبيه: عام {year} يحتوي على أشهر مفقودة — الإجماليات قد تكون أقل من الواقع.",

        "tk_revenue_up":      "الإيرادات في نمو — {period_label} ارتفعت {chg} مقارنة بالفترة السابقة.",
        "tk_revenue_down":    "تراجعت الإيرادات {chg} مقارنة بالفترة السابقة — راجع محركات الإيرادات.",
        "tk_margin_up":       "تحسّن الهامش الصافي بمقدار {pp} ليصل إلى {nm}.",
        "tk_margin_down":     "تراجع الهامش الصافي بمقدار {pp} إلى {nm} — راجع هيكل التكاليف.",
        "tk_margin_flat":     "الهامش الصافي مستقر عند {nm}.",
        "tk_ytd_ahead":       "الأداء منذ بداية العام يفوق نفس الفترة من العام الماضي بنسبة {chg}.",
        "tk_ytd_behind":      "الأداء منذ بداية العام دون نفس الفترة من العام الماضي بنسبة {chg}.",
        "tk_partial_year":    "السنة الجارية جزئية — {months} أشهر من البيانات متاحة. استخلاص نتائج السنة الكاملة يستوجب الحذر.",
        "tk_gaps":            "رُصدت فجوات في البيانات لعام {year} — {n} شهر/أشهر مفقودة.",

        "risk_negative_profit":    "صافي الربح سالب. الشركة تعمل بخسارة حالياً.",
        "risk_low_margin":         "الهامش الصافي دون 5% ({nm}) — هامش محدود لتحمّل الزيادات في التكاليف.",
        "risk_declining_revenue":  "الإيرادات في تراجع — الاستمرار قد يؤثر على التدفق النقدي.",
        "risk_partial_basis":      "التقرير مبني على بيانات جزئية. النتائج النهائية قد تختلف.",
        "risk_no_prior":           "لا توجد بيانات للسنة السابقة للمقارنة.",
        "risk_data_gaps":          "فجوات في البيانات قد تؤثر على دقة الإجماليات المُبلَّغ عنها.",

        "action_combined":         "الإجراء ذو الأولوية: تسريع النمو — رفع الإيرادات 5% مع خفض تكلفة المبيعات والمصروفات التشغيلية 2% لكل منهما. يُتوقع أن يحسّن صافي الربح بمقدار {np_delta} ({np_pct}) والهامش بمقدار {mm_pp}.",
        "action_increase_revenue": "الإجراء ذو الأولوية: تنمية الإيرادات — زيادة الإيرادات 5% يُتوقع أن يضيف {np_delta} ({np_pct}) لصافي الربح.",
        "action_reduce_cogs":      "الإجراء ذو الأولوية: تحسين تكلفة المبيعات — خفض 2% يُتوقع أن يضيف {np_delta} ({np_pct}) لصافي الربح.",
        "action_reduce_opex":      "الإجراء ذو الأولوية: خفض المصاريف التشغيلية — خفض 2% يُتوقع أن يضيف {np_delta} ({np_pct}) لصافي الربح.",
        "action_none":             "شغّل تحليل الذكاء القراري للحصول على إجراء موصى به.",
    },
}


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_narrative(
    annual_layer:    dict,
    analysis:        dict = None,
    best_scenario:   dict = None,
    warnings:        list = None,
    currency:        str  = "",
    lang:            str  = "en",
) -> dict:
    """
    Build executive narrative from structured analysis data.

    Args:
        annual_layer:  output of period_aggregation.build_annual_layer()
        analysis:      output of analysis_engine.run_analysis() (optional)
        best_scenario: output of scenario_ranker.rank_scenarios()["best_scenario"] (optional)
        warnings:      list of warning strings from API layer
        currency:      e.g. "SAR", "USD"
        lang:          "en" | "ar"

    Returns:
        {
          "executive_summary": str,
          "key_takeaways":     [str],
          "risks":             [str],
          "recommended_action":str,
          "basis_period":      str,
          "lang":              str,
        }
    """
    if lang not in _TEMPLATES:
        lang = "en"

    warnings   = warnings or []
    analysis   = analysis  or {}
    al         = annual_layer or {}
    ytd        = al.get("ytd")         or {}
    ytd_prior  = al.get("ytd_prior")   or {}
    meta       = al.get("meta")        or {}
    comp       = al.get("comparisons") or {}
    fy_list    = al.get("full_years")  or []
    latest_m   = al.get("latest_month") or {}

    latest_per = meta.get("latest_period", "")
    latest_yr  = meta.get("latest_year",   "")
    ytd_months = len(ytd.get("months", []))
    has_gaps   = ytd.get("has_gaps", False)
    fy_current = fy_list[0] if fy_list else {}
    is_partial = not fy_current.get("complete", True)

    # Prefer YTD as primary basis if we have comparison data
    primary = ytd if ytd else latest_m
    ytd_comp = comp.get("ytd_vs_prior_ytd") or {}
    fy_comp  = comp.get("full_year_current_vs_prior") or {}

    rev        = primary.get("revenue")
    np_        = primary.get("net_profit")
    nm         = primary.get("net_margin_pct")
    period_lbl = f"YTD {ytd.get('year','')}" if ytd else latest_per

    # ── Executive status ──────────────────────────────────────────────────────
    if nm is None:     status = "neutral"
    elif nm >= 15:     status = "excellent"
    elif nm >= 8:      status = "good"
    elif nm >= 0:      status = "warning"
    else:              status = "critical"

    executive_summary = _t(f"summary_{status}", lang,
        period_label = period_lbl,
        revenue      = _fmtK(rev, currency),
        net_profit   = _fmtK(np_, currency),
        net_margin   = _fmtP(nm),
    )

    # Append YTD comparison sentence
    ytd_changes = ytd_comp.get("changes") or {}
    ytd_rev_chg = ytd_changes.get("revenue")
    ytd_np_chg  = ytd_changes.get("net_profit")
    if ytd_prior and ytd_comp.get("comparable"):
        key = "ytd_vs_prior_up" if (ytd_rev_chg or 0) >= 0 else "ytd_vs_prior_down"
        executive_summary += " " + _t(key, lang,
            ytd_rev     = _fmtK(ytd.get("revenue"), currency),
            ytd_rev_chg = _pchg(ytd_rev_chg),
            ytd_np      = _fmtK(ytd.get("net_profit"), currency),
            ytd_np_chg  = _pchg(ytd_np_chg),
        )
    else:
        executive_summary += " " + _t("ytd_no_prior", lang,
            period  = latest_per,
            ytd_rev = _fmtK(ytd.get("revenue") or rev, currency),
            ytd_np  = _fmtK(ytd.get("net_profit") or np_, currency),
            ytd_nm  = _fmtP(ytd.get("net_margin_pct") or nm),
        )

    # ── Key takeaways ─────────────────────────────────────────────────────────
    takeaways: list[str] = []

    # Revenue trend (YTD vs prior)
    if ytd_rev_chg is not None:
        key = "tk_revenue_up" if ytd_rev_chg >= 0 else "tk_revenue_down"
        takeaways.append(_t(key, lang, period_label=period_lbl, chg=_pchg(ytd_rev_chg)))

    # Margin trend (latest month vs prior month)
    mom_comp    = comp.get("latest_month_vs_prior_month") or {}
    mom_changes = mom_comp.get("changes") or {}
    mom_nm_pp   = mom_changes.get("net_margin_pct")
    if mom_nm_pp is not None:
        if abs(mom_nm_pp) < 0.2:
            takeaways.append(_t("tk_margin_flat", lang, nm=_fmtP(nm)))
        elif mom_nm_pp > 0:
            takeaways.append(_t("tk_margin_up",   lang, pp=_pp(mom_nm_pp), nm=_fmtP(nm)))
        else:
            takeaways.append(_t("tk_margin_down", lang, pp=_pp(abs(mom_nm_pp)), nm=_fmtP(nm)))

    # YTD vs prior YTD
    if ytd_comp.get("comparable") and ytd_rev_chg is not None:
        key = "tk_ytd_ahead" if ytd_rev_chg >= 0 else "tk_ytd_behind"
        takeaways.append(_t(key, lang, chg=_pchg(abs(ytd_rev_chg))))

    # Full year note
    if fy_list:
        fy = fy_list[0]
        if fy.get("complete"):
            takeaways.append(_t("fy_complete", lang,
                year=fy["year"], rev=_fmtK(fy.get("revenue"), currency),
                np=_fmtK(fy.get("net_profit"), currency),
                nm=_fmtP(fy.get("net_margin_pct"))))
        else:
            takeaways.append(_t("fy_partial", lang,
                year=fy["year"], months=fy.get("month_count","?"),
                rev=_fmtK(fy.get("revenue"), currency),
                np=_fmtK(fy.get("net_profit"), currency)))

    # Partial year / gaps
    if is_partial:
        takeaways.append(_t("tk_partial_year", lang, months=ytd_months))
    if has_gaps:
        takeaways.append(_t("tk_gaps", lang,
            year=ytd.get("year","?"), n=ytd.get("missing_count","?")))

    # ── Risks ─────────────────────────────────────────────────────────────────
    risks: list[str] = []

    if (np_ or 0) < 0:
        risks.append(_t("risk_negative_profit", lang))
    elif nm is not None and nm < 5:
        risks.append(_t("risk_low_margin", lang, nm=_fmtP(nm)))

    if ytd_rev_chg is not None and ytd_rev_chg < -3:
        risks.append(_t("risk_declining_revenue", lang))

    if is_partial:
        risks.append(_t("risk_partial_basis", lang))

    if not ytd_prior:
        risks.append(_t("risk_no_prior", lang))

    if has_gaps:
        risks.append(_t("risk_data_gaps", lang))

    for w in warnings:
        if w not in risks:
            risks.append(w)

    # ── Recommended action ────────────────────────────────────────────────────
    if best_scenario:
        sc_id    = best_scenario.get("id", "")
        impact   = best_scenario.get("impact") or {}
        key      = f"action_{sc_id}" if sc_id in ("combined","increase_revenue","reduce_cogs","reduce_opex") else "action_none"
        recommended = _t(key, lang,
            np_delta = _fmtK(impact.get("net_profit_delta"), currency),
            np_pct   = _pchg(impact.get("net_profit_pct_change")),
            mm_pp    = _pp(impact.get("net_margin_pp")),
        )
    else:
        recommended = _t("action_none", lang)

    return {
        "executive_summary":  executive_summary,
        "key_takeaways":      takeaways,
        "risks":              risks,
        "recommended_action": recommended,
        "basis_period":       period_lbl,
        "lang":               lang,
        "status":             status,
    }
