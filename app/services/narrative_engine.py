"""
narrative_engine.py — Phase 17
Deterministic, template-based narrative engine.
Converts structured analysis data into business-readable text.

Design rules:
  - Pure function — no DB, no HTTP, no LLM
  - Deterministic: same inputs → same output
  - Language-aware: en | ar | tr via parallel template tables (no silent EN substitution)
  - Never crashes on missing data — every path is null-safe
  - No internal keys or technical variable names in output text
"""
from __future__ import annotations

from typing import Any, Optional

NARRATIVE_LANGS = frozenset({"en", "ar", "tr"})


def normalize_narrative_lang(lang: Optional[str]) -> str:
    """Map request to a supported narrative locale; callers should set API locale_fallback when needed."""
    raw = (lang or "en").strip().lower()
    return raw if raw in NARRATIVE_LANGS else "en"


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
    """Format a narrative template for lang. No cross-locale string fallback."""
    bundle = _TEMPLATES.get(lang)
    if bundle is None:
        return f"[narrative_unsupported_lang:{lang}]"
    tpl = bundle.get(key)
    if tpl is None:
        return f"[narrative_missing_template:{lang}:{key}]"
    try:
        return tpl.format(**kwargs)
    except (KeyError, ValueError, IndexError):
        return f"[narrative_format_error:{lang}:{key}]"


def format_narrative_warning_item(item: dict, lang: str) -> str:
    """Resolve a structured warning {key, params} to localized prose."""
    k = item.get("key") or item.get("template_key")
    if not k:
        return "[narrative_warning_invalid_item]"
    params = item.get("params") if isinstance(item.get("params"), dict) else {}
    return _t(str(k), normalize_narrative_lang(lang), **params)


def format_narrative_warning_items(items: list[dict], lang: str) -> list[str]:
    return [format_narrative_warning_item(x, lang) for x in (items or []) if x]


def collect_default_narrative_warning_items(annual_layer: Optional[dict]) -> list[dict]:
    """Structured warnings derived from annual_layer (YTD gaps, incomplete current FY)."""
    out: list[dict] = []
    al = annual_layer or {}
    ytd = al.get("ytd") or {}
    if ytd.get("has_gaps"):
        out.append({
            "key": "warn_ytd_missing_months",
            "params": {"missing_count": ytd.get("missing_count", "?")},
        })
    fy_list = al.get("full_years") or []
    if fy_list and not fy_list[0].get("complete", True):
        fy0 = fy_list[0]
        out.append({
            "key": "warn_fy_partial_calendar",
            "params": {
                "year": fy0.get("year", "?"),
                "month_count": fy0.get("month_count", "?"),
            },
        })
    return out


def collect_period_block_warning_items(
    block: Optional[dict],
    *,
    period_kind: str,
    what_if_mode: bool = False,
) -> list[dict]:
    """Warnings for a single YTD / full_year / latest_month block (decisions / what-if style)."""
    out: list[dict] = []
    b = block or {}
    if b.get("has_gaps"):
        if period_kind == "full_year":
            out.append({
                "key": "warn_fy_has_gaps",
                "params": {"year": b.get("year", "?")},
            })
        else:
            out.append({
                "key": "warn_ytd_missing_months",
                "params": {"missing_count": b.get("missing_count", "?")},
            })
    if period_kind == "full_year" and not b.get("complete", True):
        pk = "warn_fy_partial_what_if" if what_if_mode else "warn_fy_partial_calendar"
        out.append({
            "key": pk,
            "params": {
                "year": b.get("year", "?"),
                "month_count": b.get("month_count", "?"),
            },
        })
    return out


def format_prev_comparison_label(window_code: str, lang: str) -> str:
    return _t("prev_comparison_vs_window", normalize_narrative_lang(lang), window=window_code)


def format_simple_narrative(template_key: str, lang: str, **kwargs: Any) -> str:
    """Single-template line without a warning-item wrapper."""
    return _t(template_key, normalize_narrative_lang(lang), **kwargs)


def trend_direction_template_key(code: Optional[str]) -> str:
    m = {
        "improving": "trend_direction_improving",
        "declining": "trend_direction_declining",
        "stable": "trend_direction_stable",
    }
    return m.get((code or "").lower(), "trend_direction_stable")


def trend_quality_template_key(code: Optional[str]) -> str:
    m = {
        "volatile": "trend_quality_volatile",
        "stable": "trend_quality_stable",
    }
    return m.get((code or "").lower(), "trend_quality_stable")


def enrich_trend_object(trend: Optional[dict], lang: str) -> None:
    """Add direction_label, direction_key, trend_quality_label, trend_quality_key (mutates dict)."""
    if not trend or not isinstance(trend, dict):
        return
    lg = normalize_narrative_lang(lang)
    d = trend.get("direction")
    if isinstance(d, str):
        dk = trend_direction_template_key(d)
        trend["direction_key"] = dk
        trend["direction_label"] = _t(dk, lg)
    q = trend.get("trend_quality")
    if isinstance(q, str):
        qk = trend_quality_template_key(q)
        trend["trend_quality_key"] = qk
        trend["trend_quality_label"] = _t(qk, lg)


def reconciliation_warning_payload(
    *,
    lang: str,
    rev_warn: bool,
    np_warn: bool,
    main_rev_fmt: str,
    branch_rev_fmt: str,
    rev_gap_pct: Optional[float],
    main_np_fmt: str,
    branch_np_fmt: str,
    np_gap_pct: Optional[float],
) -> dict:
    """Localized MAIN vs branch reconciliation block (analysis-summary transparency layer)."""
    lg = normalize_narrative_lang(lang)

    def _pct_disp(p: Optional[float]) -> str:
        if p is None:
            return ""
        return f"+{p}" if p > 0 else f"{p}"

    items: list[dict] = []
    if rev_warn and rev_gap_pct is not None:
        items.append({
            "key": "reconcile_revenue_gap",
            "params": {
                "main_fmt": main_rev_fmt,
                "branch_fmt": branch_rev_fmt,
                "gap_pct_display": _pct_disp(rev_gap_pct),
            },
        })
    if np_warn and np_gap_pct is not None:
        items.append({
            "key": "reconcile_net_profit_gap",
            "params": {
                "main_fmt": main_np_fmt,
                "branch_fmt": branch_np_fmt,
                "gap_pct_display": _pct_disp(np_gap_pct),
            },
        })

    parts = [format_narrative_warning_item(x, lg) for x in items]
    reason = "; ".join(parts) if parts else ""
    note = _t("reconcile_footnote", lg)

    return {
        "consolidation_warning": True,
        "consolidation_reason": reason,
        "consolidation_note": note,
        "consolidation_reason_items": items,
        "consolidation_note_key": "reconcile_footnote",
        "consolidation_note_params": {},
    }


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

        "warn_ytd_missing_months": "YTD has {missing_count} missing month(s) — reported totals may be incomplete.",
        "warn_fy_partial_calendar": "Year {year} is partial ({month_count}/12 months available).",
        "warn_fy_partial_what_if": "Year {year} is partial ({month_count}/12 months) — simulation results are indicative only.",
        "warn_fy_has_gaps": "Year {year} has data gaps — reported totals may be understated.",
        "warn_whatif_clamp_max": "Input {field} was {from_value}; upper bound applied → {to_value}.",
        "warn_whatif_clamp_min": "Input {field} was {from_value}; lower bound applied → {to_value}.",
        "warn_tax_not_in_source": "Tax set to 0 — not present in source data.",
        "whatif_cashflow_collection_note": "Estimated from net profit baseline adjusted by the collection improvement rate.",
        "reconcile_revenue_gap": "MAIN revenue {main_fmt} vs branch aggregate {branch_fmt} ({gap_pct_display}% variance).",
        "reconcile_net_profit_gap": "MAIN net profit {main_fmt} vs branch aggregate {branch_fmt} ({gap_pct_display}% variance).",
        "reconcile_footnote": "Variance may reflect intercompany eliminations, holding entries, or incomplete branch uploads. Reported figures are unchanged.",
        "trend_direction_improving": "Improving",
        "trend_direction_declining": "Declining",
        "trend_direction_stable": "Stable",
        "trend_quality_volatile": "Volatile",
        "trend_quality_stable": "Stable",
        "prev_comparison_vs_window": "vs previous {window}",
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

        "warn_ytd_missing_months": "منذ بداية العام يوجد {missing_count} شهراً مفقوداً — قد تكون الإجماليات ناقصة.",
        "warn_fy_partial_calendar": "عام {year} جزئي ({month_count}/12 شهراً متاحاً).",
        "warn_fy_partial_what_if": "عام {year} جزئي ({month_count}/12 شهراً) — نتائج المحاكاة إرشادية فقط.",
        "warn_fy_has_gaps": "عام {year} فيه فجوات بيانات — قد تكون الإجماليات أقل من المُبلغ عنها.",
        "warn_whatif_clamp_max": "المدخل {field} كان {from_value}؛ طُبّق الحد الأعلى → {to_value}.",
        "warn_whatif_clamp_min": "المدخل {field} كان {from_value}؛ طُبّق الحد الأدنى → {to_value}.",
        "warn_tax_not_in_source": "الضريبة صفر افتراضياً — غير موجودة في بيانات المصدر.",
        "whatif_cashflow_collection_note": "تقدير من خط أساس صافي الربح مع تعديل بمعدل تحسين التحصيل.",
        "reconcile_revenue_gap": "إيرادات الرئيسي {main_fmt} مقابل مجموع الفروع {branch_fmt} (انحراف {gap_pct_display}٪).",
        "reconcile_net_profit_gap": "صافي ربح الرئيسي {main_fmt} مقابل مجموع الفروع {branch_fmt} (انحراف {gap_pct_display}٪).",
        "reconcile_footnote": "الانحراف قد يعكس إلغاءات داخل المجموعة أو قيوداً على مستوى القابضة أو بيانات فروع ناقصة. الأرقام المُبلغ عنها دون تعديل.",
        "trend_direction_improving": "في تحسن",
        "trend_direction_declining": "في تراجع",
        "trend_direction_stable": "مستقر",
        "trend_quality_volatile": "متقلب",
        "trend_quality_stable": "مستقر",
        "prev_comparison_vs_window": "مقارنة بالفترة السابقة {window}",
    },

    "tr": {
        "summary_excellent":  "İşletme güçlü performans gösteriyor. {period_label} gelir {revenue}, net marj {net_margin}.",
        "summary_good":       "İşletme sağlıklı konumda. {period_label} geliri {revenue}, net marj {net_margin}.",
        "summary_warning":    "İşletme dikkat gerektiriyor. {period_label} geliri {revenue}; kârlılık baskısı var, net marj {net_margin}.",
        "summary_critical":   "İşletme ciddi finansal streste. {period_label} net marj {net_margin}; acil müdahale gerekir.",
        "summary_neutral":    "{period_label} finansal performans: gelir {revenue}, net kâr {net_profit}, net marj {net_margin}.",

        "ytd_vs_prior_up":    "YTD gelir {ytd_rev} (önceki yıla göre {ytd_rev_chg}), net kâr {ytd_np} ({ytd_np_chg}).",
        "ytd_vs_prior_down":  "YTD gelir {ytd_rev} (önceki yıla göre {ytd_rev_chg}). Net kâr {ytd_np} seviyesine geriledi ({ytd_np_chg}).",
        "ytd_no_prior":       "{period} itibarıyla YTD: gelir {ytd_rev}, net kâr {ytd_np}, net marj {ytd_nm}.",

        "fy_complete":        "Tam yıl {year}: gelir {rev}, net kâr {np}, net marj {nm}.",
        "fy_partial":         "{year} yılı kısmi ({months}/12 ay): bugüne kadar gelir {rev}, net kâr {np}.",
        "fy_gap":             "Not: {year} yılında eksik aylar var — raporlanan toplamlar düşük kalabilir.",

        "tk_revenue_up":      "Gelir büyüyor — {period_label} önceki döneme göre {chg}.",
        "tk_revenue_down":    "Gelir önceki döneme göre {chg} geriledi — gelir sürücülerini inceleyin.",
        "tk_margin_up":       "Net marj {pp} iyileşerek {nm} oldu — maliyet disiplini işliyor.",
        "tk_margin_down":     "Net marj {pp} düşerek {nm} oldu — maliyet yapısını gözden geçirin.",
        "tk_margin_flat":     "Net marj {nm} seviyesinde stabil.",
        "tk_ytd_ahead":       "YTD performansı geçen yılın aynı dönemine göre {chg} önde.",
        "tk_ytd_behind":      "YTD performansı geçen yılın aynı dönemine göre {chg} geride.",
        "tk_partial_year":    "Cari yıl kısmi — {months} ay veri mevcut. Tam yıl sonuçları için temkinli olun.",
        "tk_gaps":            "{year} için veri boşlukları — {n} ay eksik. Raporlanan tutarlar eksik olabilir.",

        "risk_negative_profit":    "Net kâr negatif; işletme şu an zararda.",
        "risk_low_margin":         "Net marj %5’in altında ({nm}) — maliyet veya gelir şoku için tampon sınırlı.",
        "risk_declining_revenue":  "Gelir düşüyor — süregelen trend nakit akışını tehdit edebilir.",
        "risk_partial_basis":      "Anlatım kısmi yıl verisine dayanıyor; yıl sonu sonuçları farklı olabilir.",
        "risk_no_prior":           "Önceki yıl verisi yok — trend analizi sınırlı.",
        "risk_data_gaps":          "Raporlama döneminde veri boşlukları toplamların doğruluğunu etkileyebilir.",

        "action_combined":         "Öncelikli eylem: Büyümeyi hızlandırın — geliri %5 artırın, SMM ve faaliyet giderlerini her biri %2 azaltın. Net kârın {np_delta} ({np_pct}), net marjın {mm_pp} iyileşmesi öngörülür.",
        "action_increase_revenue": "Öncelikli eylem: Geliri büyütün — %5 gelir artışının net kâra {np_delta} ({np_pct}) katkısı öngörülür (maliyet yapısı sabit).",
        "action_reduce_cogs":      "Öncelikli eylem: SMM’yi optimize edin — %2 azaltımın net kâra {np_delta} ({np_pct}) eklemesi öngörülür.",
        "action_reduce_opex":      "Öncelikli eylem: Faaliyet giderlerini düşürün — %2 azaltımın net kâra {np_delta} ({np_pct}) eklemesi öngörülür.",
        "action_none":             "Henüz öneri yok. Veri yükleyip Finansal Zekâ analizini çalıştırın.",

        "warn_ytd_missing_months": "YTD’de {missing_count} eksik ay var — raporlanan toplamlar eksik olabilir.",
        "warn_fy_partial_calendar": "{year} yılı kısmi ({month_count}/12 ay mevcut).",
        "warn_fy_partial_what_if": "{year} yılı kısmi ({month_count}/12 ay) — simülasyon sonuçları gösterge niteliğindedir.",
        "warn_fy_has_gaps": "{year} yılında veri boşlukları var — raporlanan toplamlar eksik kalabilir.",
        "warn_whatif_clamp_max": "{field} girdisi {from_value} idi; üst sınır uygulandı → {to_value}.",
        "warn_whatif_clamp_min": "{field} girdisi {from_value} idi; alt sınır uygulandı → {to_value}.",
        "warn_tax_not_in_source": "Vergi 0 alındı — kaynak veride yok.",
        "whatif_cashflow_collection_note": "Net kâr baz çizgisi × tahsilat iyileştirme oranı ile tahmini etki.",
        "reconcile_revenue_gap": "ANA gelir {main_fmt} vs şube toplamı {branch_fmt} ({gap_pct_display}% sapma).",
        "reconcile_net_profit_gap": "ANA net kâr {main_fmt} vs şube toplamı {branch_fmt} ({gap_pct_display}% sapma).",
        "reconcile_footnote": "Sapma şirketler arası eliminasyon, holding kayıtları veya eksik şube verisinden kaynaklanabilir. Raporlanan tutarlar değiştirilmedi.",
        "trend_direction_improving": "İyileşen",
        "trend_direction_declining": "Bozulan",
        "trend_direction_stable": "Stabil",
        "trend_quality_volatile": "Oynak",
        "trend_quality_stable": "Stabil",
        "prev_comparison_vs_window": "önceki {window} dönemine göre",
    },
}


def _assert_narrative_template_parity() -> None:
    keys_en = set(_TEMPLATES["en"])
    for loc in ("ar", "tr"):
        if set(_TEMPLATES[loc]) != keys_en:
            raise RuntimeError(
                f"narrative_engine: template keys mismatch en vs {loc}: "
                f"{sorted(keys_en - set(_TEMPLATES[loc]))[:8]} / "
                f"{sorted(set(_TEMPLATES[loc]) - keys_en)[:8]}"
            )


_assert_narrative_template_parity()


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_narrative(
    annual_layer:    dict,
    analysis:        dict = None,
    best_scenario:   dict = None,
    warnings:        list = None,
    warning_items:   Optional[list] = None,
    currency:        str  = "",
    lang:            str  = "en",
) -> dict:
    """
    Build executive narrative from structured analysis data.

    Args:
        annual_layer:  output of period_aggregation.build_annual_layer()
        analysis:      output of analysis_engine.run_analysis() (optional)
        best_scenario: output of scenario_ranker.rank_scenarios()["best_scenario"] (optional)
        warnings:      legacy list of raw strings (merged into risks only when lang is en)
        warning_items: optional list of {key, params} dicts; if None, derived from annual_layer
        currency:      e.g. "SAR", "USD"
        lang:          "en" | "ar" | "tr" (invalid values normalized by caller; see normalize_narrative_lang)

    Returns:
        Same keys as before, plus narrative_warning_items (structured items merged into risks).
    """
    lang = normalize_narrative_lang(lang)

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

    if warning_items is None:
        merged_warning_items: list[dict] = collect_default_narrative_warning_items(al)
    else:
        merged_warning_items = [x for x in (warning_items or []) if isinstance(x, dict)]

    for item in merged_warning_items:
        line = format_narrative_warning_item(item, lang)
        if line and line not in risks:
            risks.append(line)

    for w in warnings:
        if isinstance(w, dict) and (w.get("key") or w.get("template_key")):
            line = format_narrative_warning_item(w, lang)
            if line and line not in risks:
                risks.append(line)
        elif isinstance(w, str) and lang == "en":
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
        "narrative_warning_items": merged_warning_items,
    }
