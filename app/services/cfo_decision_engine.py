"""
cfo_decision_engine.py — Phase 25
CFO Decision Engine: converts financial intelligence into top-3 prioritized actions.

Inputs:  health_score_v2, ratios, trends, alerts, anomalies
         (all from fin_intelligence.build_intelligence())

Logic:
  1. Score each financial domain (liquidity, profitability, efficiency, leverage, growth)
  2. Liquidity always prioritized if weak (cash survival > growth)
  3. Map domains to specific CFO-level actions
  4. Return top 3 decisions ranked by composite priority score

Rules:
  - Does NOT duplicate alerts_engine logic — operates at STRATEGY level
  - Each decision: domain, action, rationale, impact, urgency, confidence
  - Fully localized (EN / AR / TR)
  - Pure function — no DB, no HTTP
"""
from __future__ import annotations
from typing import Any, Optional

from app.services.cfo_decision_depth import (
    build_ratio_depth_context,
    depth_get,
)
from app.services.structured_profit_story import build_structured_profit_story_from_analysis

_REC_SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}


def _trend_mag_dict(trends: dict) -> dict[str, Any]:
    return {
        "rev_roll_3m": _get(trends, "revenue", "rolling_3m"),
        "np_roll_3m": _get(trends, "net_profit", "rolling_3m"),
        "rev_yoy": _get(trends, "revenue", "yoy_change"),
        "np_yoy": _get(trends, "net_profit", "yoy_change"),
        "rev_cagr": _get(trends, "revenue", "cagr_pct"),
        "rev_ytd": _get(trends, "revenue", "ytd_vs_prior"),
    }


def _anomaly_targets(an: dict) -> set[str]:
    m = str(an.get("metric") or "")
    if m == "revenue":
        return {"growth", "profitability"}
    if m == "net_profit":
        return {"profitability"}
    if m == "gross_margin":
        return {"profitability", "efficiency"}
    if m == "data_quality":
        return {"liquidity", "profitability", "efficiency", "leverage", "growth"}
    return {"profitability", "growth"}


def _build_decision_fingerprint(
    key: str,
    domain: str,
    ratios: dict,
    depth_ctx: dict,
    extra_metrics: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    sig: dict[str, Any] = {"key": key, "domain": domain, "metrics": {}}
    m = sig["metrics"]
    nm = _get(ratios, "profitability", "net_margin_pct", "value")
    if nm is not None:
        m["nm"] = round(float(nm), 2)
    gm = _get(ratios, "profitability", "gross_margin_pct", "value")
    if gm is not None:
        m["gm"] = round(float(gm), 2)
    cr = _get(ratios, "liquidity", "current_ratio", "value")
    if cr is not None:
        m["cr"] = round(float(cr), 3)
    ccc = _get(ratios, "efficiency", "ccc_days", "value")
    if ccc is not None:
        m["ccc"] = round(float(ccc), 1)
    de = _get(ratios, "leverage", "debt_to_equity", "value")
    if de is not None:
        m["de"] = round(float(de), 2)
    dso = _get(ratios, "efficiency", "dso_days", "value")
    if dso is not None:
        m["dso"] = round(float(dso), 1)
    if extra_metrics:
        for ek, ev in extra_metrics.items():
            if ev is not None:
                try:
                    m[str(ek)] = round(float(ev), 4) if isinstance(ev, (int, float)) else ev
                except (TypeError, ValueError):
                    m[str(ek)] = ev
    return sig


def _fingerprint_is_stale(
    fp: dict[str, Any],
    prior: list[dict],
) -> bool:
    if not prior:
        return False
    key, domain = fp.get("key"), fp.get("domain")
    cur_m = fp.get("metrics") or {}
    eps = {
        "nm": 0.45,
        "gm": 0.55,
        "cr": 0.09,
        "ccc": 4.0,
        "de": 0.12,
        "dso": 5.0,
    }
    for p in prior:
        if p.get("key") != key or p.get("domain") != domain:
            continue
        pm = p.get("metrics") or {}
        if not pm or not cur_m:
            return False
        stale = True
        for k, v in cur_m.items():
            if v is None or pm.get(k) is None:
                stale = False
                break
            e = eps.get(k, 0.02)
            if k in ("rev_g3", "rev_growth_3m"):
                e = 1.25
            if k == "er":
                e = 1.1
            if abs(float(v) - float(pm[k])) > e:
                stale = False
                break
        if stale:
            return True
    return False


def _branch_profitability_concentration(
    branch_context: Optional[dict],
    company_nm: Any,
) -> Optional[dict[str, Any]]:
    if not branch_context or company_nm is None:
        return None
    w = branch_context.get("weakest") or {}
    bid = w.get("branch_id")
    name = w.get("name")
    wnm = w.get("net_margin_pct")
    share = w.get("revenue_share_pct")
    if bid is None or name is None or wnm is None:
        return None
    try:
        cn = float(company_nm)
        sh = float(share) if share is not None else 0.0
        wn = float(wnm)
    except (TypeError, ValueError):
        return None
    if sh < 8.0:
        return None
    if (cn - wn) < 4.0:
        return None
    return {
        "scope": "branch",
        "branch_id": bid,
        "branch_name": name,
        "revenue_contribution_pct": round(sh, 2),
        "branch_net_margin_pct": round(wn, 2),
        "company_net_margin_pct": round(cn, 2),
        "gap_pp": round(cn - wn, 2),
    }


PARADOX_GROWTH_MARGIN_KEY = "paradox_growth_negative_operating_margin"
_PARADOX_DOMAIN_TOKEN = "__paradox_growth_margin__"


def _revenue_growth_trailing_3m_vs_prior_3m(analysis: Optional[dict]) -> Optional[float]:
    """Average revenue last 3 periods vs average of prior 3 periods (% change)."""
    if not analysis or not isinstance(analysis, dict):
        return None
    tr = analysis.get("trends") or {}
    rev = [float(x) for x in (tr.get("revenue_series") or []) if x is not None]
    if len(rev) < 6:
        return None
    last3 = sum(rev[-3:]) / 3.0
    prev3 = sum(rev[-6:-3]) / 3.0
    if prev3 <= 0:
        return None
    return round((last3 - prev3) / prev3 * 100, 2)


def _latest_total_cost_ratio_pct_from_trends(analysis: Optional[dict]) -> Optional[float]:
    """(COGS + OpEx) / revenue using latest non-null points in trend series."""
    if not analysis or not isinstance(analysis, dict):
        return None
    tr = analysis.get("trends") or {}

    def _last(series: list) -> Optional[float]:
        for x in reversed(series or []):
            if x is not None:
                return float(x)
        return None

    r = _last(tr.get("revenue_series") or [])
    if r is None or r <= 0:
        return None
    c = _last(tr.get("cogs_series") or []) or 0.0
    e = _last(tr.get("expenses_series") or []) or 0.0
    return round((c + e) / r * 100, 2)


def _mom_from_levels(series: list) -> Optional[float]:
    """Last period-over-period % change from absolute levels."""
    vals = [float(v) for v in (series or []) if v is not None]
    if len(vals) < 2:
        return None
    cur, prev = vals[-1], vals[-2]
    if prev == 0:
        return None
    return round((cur - prev) / abs(prev) * 100, 2)


def _tail_avg_mom(mom_series: list) -> Optional[float]:
    pts = [float(x) for x in (mom_series or []) if x is not None]
    if not pts:
        return None
    tail = pts[-3:]
    return round(sum(tail) / len(tail), 2)


def _opex_pct_revenue(tr: dict) -> Optional[float]:
    exp_s = tr.get("expenses_series") or []
    rev_s = tr.get("revenue_series") or []
    rev = next((v for v in reversed(rev_s) if v is not None), None)
    exp = next((v for v in reversed(exp_s) if v is not None), None)
    if rev is None or exp is None or float(rev) == 0:
        return None
    return round(float(exp) / float(rev) * 100, 2)


def _suggest_opex_cut_pct(opex_r: float, nm: Optional[float]) -> int:
    if opex_r >= 55 or (nm is not None and nm < 3):
        return 15
    if opex_r >= 45 or (nm is not None and nm < 8):
        return 10
    return 5


def _build_actionable_recommendations(
    intelligence: dict,
    alerts: list,
    lang: str,
    analysis: Optional[dict] = None,
    branch_context: Optional[dict] = None,
) -> list[dict]:
    """
    Short actionable one-liners derived from the same data as decisions (no LLM).
    Each item: recommendation, reason, priority (high|medium|low).
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"

    ratios = intelligence.get("ratios") or {}
    trends_intel = intelligence.get("trends") or {}
    tr = (analysis or {}).get("trends") or {}

    nm = _get(ratios, "profitability", "net_margin_pct", "value")
    gm_st = _get(ratios, "profitability", "gross_margin_pct", "status") or "neutral"
    nm_st = _get(ratios, "profitability", "net_margin_pct", "status") or "neutral"
    rev_dir = _get(trends_intel, "revenue", "direction") or "insufficient_data"
    np_dir = _get(trends_intel, "net_profit", "direction") or "insufficient_data"
    gm_dir = _get(trends_intel, "gross_margin", "direction") or "insufficient_data"

    opex_r = _opex_pct_revenue(tr)
    exp_mom_avg = _tail_avg_mom(tr.get("expenses_mom_pct") or [])
    last_cogs_mom = _mom_from_levels(tr.get("cogs_series") or [])

    alert_ids = {str(a.get("id") or "") for a in (alerts or [])}
    max_alert_sev = "low"
    for a in alerts or []:
        s = str(a.get("severity") or "low")
        if _REC_SEVERITY_ORDER.get(s, 0) > _REC_SEVERITY_ORDER.get(max_alert_sev, 0):
            max_alert_sev = s

    out: list[dict] = []
    kinds: set[str] = set()

    def _add(kind: str, rec: str, reason: str, pri: str) -> None:
        if kind in kinds:
            return
        kinds.add(kind)
        out.append({
            "recommendation": rec,
            "reason": reason,
            "priority": pri if pri in ("high", "medium", "low") else "medium",
        })

    # ── Operating expense reduction (levels + trend) ───────────────────────────
    if opex_r is not None and opex_r >= 32:
        rising_cost = exp_mom_avg is not None and exp_mom_avg > 1.5
        tight_nm = nm_st in ("warning", "risk") or (nm is not None and nm < 8)
        if tight_nm or rising_cost or opex_r >= 45:
            cut = _suggest_opex_cut_pct(opex_r, nm)
            pri = "high" if opex_r >= 55 or nm_st == "risk" or (nm is not None and nm < 0) else (
                "medium" if tight_nm or opex_r >= 40 else "low"
            )
            if lang == "ar":
                rec = f"خفض المصاريف التشغيلية بنسبة {cut}%"
                reason = (
                    f"مصاريف التشغيل تمثل {opex_r:.1f}% من الإيرادات والهامش الصافي {nm if nm is not None else 0:.1f}%."
                    + (" تسارع واضح في نمو المصاريف شهرياً." if rising_cost else "")
                )
            elif lang == "tr":
                rec = f"İşletme giderlerini %{cut} azaltın"
                reason = (
                    f"İşletme giderleri gelirin %{opex_r:.1f}'i ve net marj %{nm if nm is not None else 0:.1f}."
                    + (" Giderlerde MoM artış eğilimi var." if rising_cost else "")
                )
            else:
                rec = f"Reduce operating expenses by {cut}%"
                reason = (
                    f"Operating costs are {opex_r:.1f}% of revenue and net margin is {nm if nm is not None else 0:.1f}%."
                    + (" Expenses are trending up month over month." if rising_cost else "")
                )
            _add("reduce_opex", rec, reason.strip(), pri)

    # ── COGS investigation ────────────────────────────────────────────────────
    if last_cogs_mom is not None and last_cogs_mom >= 2.5:
        pri = (
            "high"
            if last_cogs_mom >= 8
            or any(str(aid).startswith("anomaly_profit") for aid in alert_ids)
            else "medium"
        )
        if lang == "ar":
            rec = "التحقيق في ارتفاع تكلفة البضاعة المباعة (COGS)"
            reason = f"COGS ارتفعت {last_cogs_mom:+.1f}% عن الفترة السابقة"
            if gm_dir == "down":
                reason += " والهامش الإجمالي تحت ضغط."
        elif lang == "tr":
            rec = "COGS maliyet artışını araştırın"
            reason = f"COGS bir önceki döneme göre %{last_cogs_mom:+.1f} değişti"
            if gm_dir == "down":
                reason += "; brüt marj baskı altında."
        else:
            rec = "Investigate cost spike in COGS"
            reason = f"COGS moved {last_cogs_mom:+.1f}% vs the prior period"
            if gm_dir == "down":
                reason += ", pressuring gross margin."
        _add("cogs_spike", rec, reason, pri)

    # ── Pricing / gross margin ────────────────────────────────────────────────
    if gm_st in ("warning", "risk") and rev_dir != "down":
        pri = "high" if gm_st == "risk" else "medium"
        if lang == "ar":
            rec = "تحسين استراتيجية التسعير وهامش الربح الإجمالي"
            reason = (
                f"الهامش الإجمالي في وضع {gm_st} مع اتجاه إيراد {rev_dir} — "
                "السعر أو مزيج المنتجات يحتاج ضبطاً."
            )
        elif lang == "tr":
            rec = "Fiyatlandırma stratejisini iyileştirin"
            reason = (
                f"Brüt marj durumu: {gm_st}, gelir trendi: {rev_dir} — "
                "fiyat veya ürün karması gözden geçirilmeli."
            )
        else:
            rec = "Improve pricing strategy"
            reason = (
                f"Gross margin is {gm_st} while revenue trend is {rev_dir} — "
                "pricing or Revenue mix likely needs adjustment."
            )
        _add("pricing", rec, reason, pri)

    # ── Branches: expansion / underperformance ────────────────────────────────
    bc = branch_context or {}
    leader = bc.get("revenue_leader") or {}
    weakest = bc.get("weakest") or {}
    lname = leader.get("name")
    lrev = leader.get("revenue")
    wname = weakest.get("name")
    wnm = weakest.get("net_margin_pct")

    if lname and rev_dir in ("up", "stable") and (np_dir != "down" or (nm is not None and nm >= 3)):
        pri = "medium" if rev_dir == "up" else "low"
        rev_bit = ""
        try:
            if lrev is not None and float(lrev) > 0:
                rev_bit = f" ({float(lrev):,.0f})" if lang == "en" else ""
        except (TypeError, ValueError):
            pass
        if lang == "ar":
            rec = f"التركيز على توسعة فرع {lname}"
            reason = f"{lname} يقود الإيرادات في المحفظة وظروف النمو تدعم استثماراً انتقائياً في التوسع."
        elif lang == "tr":
            rec = f"{lname} genişlemesine odaklanın"
            reason = (
                f"{lname} portföyde geliri önde taşıyor; büyüme koşulları seçici kapasite genişletmeyi destekliyor."
            )
        else:
            rec = f"Focus on {lname} expansion"
            reason = (
                f"{lname} leads portfolio revenue{rev_bit}; growth conditions support selective capacity expansion."
            )
        _add("branch_expand", rec, reason, pri)

    if wname and wnm is not None and float(wnm) < 5 and lname != wname:
        pri = "high" if float(wnm) < 0 else "medium"
        if lang == "ar":
            rec = f"معالجة ضعف الأداء في فرع {wname}"
            reason = f"هامش صافٍ تقريباً {float(wnm):.1f}% في {wname} مقارنة ببقية الفروع."
        elif lang == "tr":
            rec = f"{wname} şubesindeki düşük performansı giderin"
            reason = f"{wname} net marjı yaklaşık %{float(wnm):.1f}; portföyün geri kalanının altında."
        else:
            rec = f"Address underperformance at branch {wname}"
            reason = f"Net margin near {float(wnm):.1f}% at {wname}, below the rest of the portfolio."
        _add("branch_weak", rec, reason, pri)

    # ── Tight liquidity ────────────────────────────────────────────────────────
    if "current_ratio_low" in alert_ids or "working_capital_negative" in alert_ids:
        pri = "high"
        if lang == "ar":
            rec = "تسريع التحصيل وإعادة تقييم الالتزامات قصيرة الأجل"
            reason = "مؤشرات السيولة تستدعي إجراءً فوراً لتفادي ضغط نقدي."
        elif lang == "tr":
            rec = "Tahsilatı hızlandırın ve kısa vadeli yükümlülükleri yeniden değerlendirin"
            reason = "Likidite sinyalleri nakit baskısını önlemek için acil eylem gerektiriyor."
        else:
            rec = "Accelerate collections and renegotiate short-term obligations"
            reason = "Liquidity is under real pressure, with current-ratio or working-capital signals indicating the cash gap should be reduced before the next payment cycle."
        _add("liquidity", rec, reason, pri)

    # ── Net margin deterioration with rising costs ───────────────────────────
    if np_dir == "down" and rev_dir == "up" and (exp_mom_avg is not None and exp_mom_avg > 0):
        pri = "medium" if max_alert_sev != "high" else "high"
        if lang == "ar":
            rec = "احتواء زيادة المصاريف لدعم ربحية النمو الإيرادي"
            reason = "الإيرادات تنمو لكن صافي الربح يتراجع — ركز على كفاءة التكلفة."
        elif lang == "tr":
            rec = "Gelir büyürken artan giderleri kontrol altına alın"
            reason = "Gelir artıyor ancak net kar baskı altında — maliyet verimliliğine odaklanın."
        else:
            rec = "Contain expense growth to protect profitability"
            reason = f"Revenue is improving but net profit is falling, while average expense growth is running near {exp_mom_avg:.1f}% over recent periods; growth is not converting into profit because cost pressure is outpacing it."
        _add("rev_up_np_down", rec, reason, pri)

    out.sort(key=lambda x: -_REC_SEVERITY_ORDER.get(x.get("priority", "low"), 0))
    return out[:12]


# ──────────────────────────────────────────────────────────────────────────────
#  Domain score weights
# ──────────────────────────────────────────────────────────────────────────────

# How much of the total priority each domain can claim
DOMAIN_WEIGHTS = {
    "liquidity":     35,   # survival first
    "profitability": 30,
    "efficiency":    20,
    "leverage":      10,
    "growth":         5,
}

# Impact values for status
STATUS_SCORE = {"risk": 100, "warning": 60, "neutral": 20, "good": 0}


# ──────────────────────────────────────────────────────────────────────────────
#  Localized decision text
# ──────────────────────────────────────────────────────────────────────────────

_DT: dict[str, dict] = {

    # ── Liquidity decisions ────────────────────────────────────────────────────
    "liq_immediate_cashflow": {
        "en": {
            "title":     "Immediate Cash Flow Action Required",
            "rationale": "Current ratio {cr}x indicates the business cannot comfortably cover short-term obligations. Immediate action is needed to prevent liquidity crisis.",
            "action":    "1) Accelerate receivables collection — contact all overdue accounts within 48 hours. 2) Negotiate extended payment terms with top 3 suppliers. 3) Review and defer all non-critical capital expenditures. 4) Assess eligibility for short-term revolving credit facility.",
            "impact":    "Prevents potential payment default and maintains supplier trust.",
        },
        "ar": {
            "title":     "إجراء تدفق نقدي فوري مطلوب",
            "rationale": "نسبة التداول {cr} تشير إلى عدم قدرة الشركة على تغطية الالتزامات قصيرة الأجل بشكل مريح. الإجراء الفوري ضروري لمنع أزمة سيولة.",
            "action":    "1) تسريع تحصيل المستحقات — التواصل مع جميع الحسابات المتأخرة خلال 48 ساعة. 2) التفاوض على تمديد شروط الدفع مع أكبر 3 موردين. 3) مراجعة وتأجيل جميع النفقات الرأسمالية غير الحرجة. 4) تقييم الأهلية للحصول على تسهيل ائتماني متجدد قصير الأجل.",
            "impact":    "يمنع التخلف المحتمل عن السداد ويحافظ على ثقة الموردين.",
        },
        "tr": {
            "title":     "Acil Nakit Akışı Aksiyonu Gerekli",
            "rationale": "Cari oran {cr}x, işletmenin kısa vadeli yükümlülüklerini rahatça karşılayamayacağını gösteriyor.",
            "action":    "1) Alacak tahsilatını hızlandırın — 48 saat içinde tüm gecikmiş hesaplarla iletişime geçin. 2) İlk 3 tedarikçiyle uzatılmış ödeme koşulları müzakere edin. 3) Kritik olmayan sermaye harcamalarını erteleyin. 4) Kısa vadeli kredi imkânlarını değerlendirin.",
            "impact":    "Olası ödeme temerrüdünü önler ve tedarikçi güvenini korur.",
        },
    },

    "liq_strengthen_working_capital": {
        "en": {
            "title":     "Strengthen Working Capital Position",
            "rationale": "Current ratio {cr}x vs 6M rolling avg {cr_roll6m}x (Δ {delta_cr_vs_roll6m}); quick ratio {qr}x; WC {wc}. Liquidity is softer than recent baseline — build a buffer before volatility hits cash.",
            "action":    "1) Implement 30-day payment terms for all new customer contracts. 2) Set up automated invoice reminders at 15, 30, and 45 days. 3) Consider factoring receivables to unlock trapped cash. 4) Target working capital ratio of 1.5x within 2 quarters.",
            "impact":    "Improves operational resilience and reduces reliance on credit lines.",
        },
        "ar": {
            "title":     "تعزيز موقف رأس المال العامل",
            "rationale": "النسبة الجارية {cr} مقارنة بمتوسط 6 أشهر {cr_roll6m} (التغير {delta_cr_vs_roll6m})؛ السريعة {qr}؛ رأس المال العامل {wc}. السيولة أضعف من خط الأساس الأخير — عزّز الهامش قبل ضغط النقد.",
            "action":    "1) تطبيق شروط دفع 30 يوماً لجميع عقود العملاء الجديدة. 2) إعداد تذكيرات فاتورة آلية في 15 و30 و45 يوماً. 3) النظر في خصم الفواتير لتحرير النقد المحتجز. 4) استهداف نسبة رأس مال عامل 1.5x خلال ربعين.",
            "impact":    "يحسن المرونة التشغيلية ويقلل الاعتماد على خطوط الائتمان.",
        },
        "tr": {
            "title":     "İşletme Sermayesini Güçlendirin",
            "rationale": "Cari oran {cr} (6 aylık ort. {cr_roll6m}, Δ {delta_cr_vs_roll6m}); asit-test {qr}; işletme sermayesi {wc}. Likidite son dönem ortalamasının altında — nakit şoklarından önce tampon oluşturun.",
            "action":    "1) Tüm yeni müşteri sözleşmeleri için 30 günlük ödeme koşulları uygulayın. 2) 15, 30 ve 45. günlerde otomatik fatura hatırlatmaları kurun. 3) Alacakların faktoring yoluyla nakde çevrilmesini değerlendirin.",
            "impact":    "Operasyonel dayanıklılığı artırır ve kredi limitlerine bağımlılığı azaltır.",
        },
    },

    # ── Profitability decisions ────────────────────────────────────────────────
    "prof_margin_recovery": {
        "en": {
            "title":     "Margin Recovery Programme",
            "rationale": "Net margin {nm}% vs 6M rolling avg {nm_roll6m}% (Δ {delta_nm_vs_roll6m} pp) — below a sustainable range; sustained pressure erodes equity.",
            "action":    "1) Run unit economics analysis (cost per unit/service line) — identify margin leakage. 2) Review the largest Cost Drivers (COGS and Operating Expenses) and their allocation logic. 3) Update pricing and customer segmentation for low-margin segments. 4) Target a minimum 12% Net Margin within 3 quarters.",
            "impact":    "Each 1pp margin improvement on current revenue ≈ {per_pp} additional annual profit.",
        },
        "ar": {
            "title":     "برنامج استعادة الهوامش",
            "rationale": "الهامش الصافي {nm}% مقارنة بمتوسط 6 أشهر {nm_roll6m}% (Δ {delta_nm_vs_roll6m} نقطة) — دون نطاق مستدام؛ الضغط المستمر يآكل حقوق الملكية.",
            "action":    "1) إجراء تحليل اقتصاديات الوحدة (التكلفة لكل وحدة/خط خدمة) لتحديد تسرب الهوامش. 2) مراجعة أكبر محركات التكاليف (تكلفة المبيعات والمصروفات التشغيلية) ومنهجية توزيعها. 3) تحديث التسعير وتقسيم العملاء لشرائح الهامش المنخفض. 4) استهداف هامش صافي لا يقل عن 12% خلال 3 أرباع.",
            "impact":    "كل تحسن بنسبة 1 نقطة مئوية في الهامش على الإيرادات الحالية ≈ {per_pp} ربح إضافي سنوي.",
        },
        "tr": {
            "title":     "Marj İyileştirme Programı",
            "rationale": "Net marj %{nm} (6 aylık ort. %{nm_roll6m}, Δ {delta_nm_vs_roll6m} pp) — sürdürülebilir bandın altında; baskı sürerse özkaynak aşınır.",
            "action":    "1) Birim ekonomisi analizi (birim/hizmet hattı başına maliyet) yapın ve marj kaçaklarını bulun. 2) En büyük maliyet etkenlerini (COGS ve işletme giderleri) ve tahsis mantığını gözden geçirin. 3) Düşük marjlı segmentler için fiyatlandırma ve müşteri segmentasyonunu güncelleyin.",
            "impact":    "Mevcut gelirde her 1 puanlık marj iyileşmesi ≈ {per_pp} ek yıllık kar.",
        },
    },

    "prof_cost_structure_review": {
        "en": {
            "title":     "Strategic Cost Structure Review",
            "rationale": "Gross margin {gm}% vs 6M rolling avg {gm_roll6m}% (Δ {delta_gm_vs_roll6m} pp) — room for structural COGS/pricing improvement; without action, profitability stays compressed.",
            "action":    "1) Map all cost centres by percentage of revenue — benchmark against peers. 2) Identify top 5 cost drivers and set 5% reduction targets. 3) Evaluate outsourcing non-core activities (maintenance, admin). 4) Implement monthly cost performance reviews with department heads.",
            "impact":    "Structural cost reduction improves both margins and long-term competitiveness.",
        },
        "ar": {
            "title":     "مراجعة هيكل التكاليف الاستراتيجية",
            "rationale": "هامش إجمالي {gm}% مقارنة بمتوسط 6 أشهر {gm_roll6m}% (Δ {delta_gm_vs_roll6m} نقطة) — مجال لتحسين هيكلي؛ بدون إجراء تبقى الربحية مضغوطة.",
            "action":    "1) رسم خريطة لجميع مراكز التكاليف كنسبة مئوية من الإيرادات — المقارنة مع النظراء. 2) تحديد أكبر 5 محركات للتكاليف وتحديد أهداف تخفيض 5%. 3) تقييم الاستعانة بمصادر خارجية للأنشطة غير الأساسية. 4) تطبيق مراجعات شهرية لأداء التكاليف مع رؤساء الأقسام.",
            "impact":    "تخفيض التكاليف الهيكلي يحسن الهوامش والقدرة التنافسية على المدى الطويل.",
        },
        "tr": {
            "title":     "Stratejik Maliyet Yapısı Gözden Geçirme",
            "rationale": "Brüt marj %{gm} (6 aylık ort. %{gm_roll6m}, Δ {delta_gm_vs_roll6m} pp) — yapısal SMM/fiyat iyileştirmesi gerekli.",
            "action":    "1) Tüm maliyet merkezlerini gelirin yüzdesi olarak haritalayın. 2) En büyük 5 maliyet etkenini belirleyin ve %5 azaltma hedefleri koyun. 3) Çekirdek dışı faaliyetler için dış kaynak kullanımını değerlendirin.",
            "impact":    "Yapısal maliyet azaltımı marjları ve uzun vadeli rekabetçiliği artırır.",
        },
    },

    # ── Financial paradox (Phase 5C) ───────────────────────────────────────────
    "paradox_growth_negative_operating_margin": {
        "en": {
            "title":     "Revenue is growing but profitability remains negative",
            "rationale": "Revenue is expanding, but the current cost base is still absorbing more value than the growth is creating, so operating margin remains negative.",
            "action":    "Reconcile the cost stack by COGS and OpEx, identify the break-even revenue level, and cut or reprice the lines preventing growth from translating into profit.",
            "impact":    "Evidence: trailing 3M revenue growth {revenue_growth_3m_pct}% vs prior 3M; operating margin {operating_margin_pct}%; (COGS+OpEx)/revenue {expense_ratio_pct}%.",
        },
        "ar": {
            "title":     "الإيرادات تنمو لكن الربحية لا تزال سالبة",
            "rationale": "هيكل التكاليف يتجاوز نمو الإيرادات",
            "action":    "حلّل تفصيل التكاليف (تكلفة البضاعة مقابل المصاريف التشغيلية) وحدد نقطة التعادل",
            "impact":    "أدلة: نمو إيراد متوسط 3 أشهر {revenue_growth_3m_pct}% مقابل الـ3 السابقة؛ هامش تشغيلي {operating_margin_pct}٪؛ (تكلفة البضاعة+مصاريف)/إيراد {expense_ratio_pct}٪.",
        },
        "tr": {
            "title":     "Gelir büyüyor ancak kârlılık hâlâ negatif",
            "rationale": "Maliyet yapısı gelir büyümesini aşıyor",
            "action":    "Maliyet dağılımını analiz edin (SMM vs faaliyet gideri) ve başabaş noktasını belirleyin",
            "impact":    "Kanıt: son 3 dönem ortalama gelir büyümesi {revenue_growth_3m_pct}% (önceki 3’e göre); faaliyet marjı %{operating_margin_pct}; (SMM+OpEx)/gelir %{expense_ratio_pct}.",
        },
    },

    # ── Structured profit bridge story (Phase STEP 4) — rationale fragments ─────
    "profit_story.paradox_growth_loss.what_changed": {
        "en": {
            "rationale": "Profit bridge ({previous_period} → {latest_period}): revenue moved {delta_rev_fmt} while net profit moved {delta_np_fmt}. COGS {delta_cogs_fmt}, OpEx {delta_opex_fmt}.",
        },
        "ar": {
            "rationale": "جسر الربح ({previous_period} → {latest_period}): تحرك الإيراد {delta_rev_fmt} بينما تحرك صافي الربح {delta_np_fmt}. تكلفة المبيعات {delta_cogs_fmt}، المصاريف التشغيلية {delta_opex_fmt}.",
        },
        "tr": {
            "rationale": "Kâr köprüsü ({previous_period} → {latest_period}): gelir {delta_rev_fmt}, net kâr {delta_np_fmt}. SMM {delta_cogs_fmt}, faaliyet gideri {delta_opex_fmt}.",
        },
    },
    "profit_story.paradox_growth_loss.why": {
        "en": {
            "rationale": "Revenue growth did not translate into profit — cost absorption exceeded the revenue gain (bridge primary mover: {primary_driver}).",
        },
        "ar": {
            "rationale": "نمو الإيرادات لم يتحول إلى ربح — استيعاب التكاليف تجاوز مكسب الإيرادات (المحرك الرئيسي في الجسر: {primary_driver}).",
        },
        "tr": {
            "rationale": "Gelir artışı kâra dönüşmedi — maliyetler gelir kazanımını aştı (köprüde birincil hareket: {primary_driver}).",
        },
    },
    "profit_story.paradox_growth_loss.action": {
        "en": {
            "rationale": "Reconcile the period bridge to COGS and OpEx accounts; executive review of {primary_driver} and pricing/cost pass-through.",
        },
        "ar": {
            "rationale": "طابق الجسر مع حسابات تكلفة المبيعات والمصاريف التشغيلية؛ مراجعة تنفيذية لـ {primary_driver} وتمرير التكلفة/التسعير.",
        },
        "tr": {
            "rationale": "Köprüyü SMM ve faaliyet gideri hesaplarıyla mutabık kılın; {primary_driver} ve fiyat/maliyet yansıtması için yönetici incelemesi.",
        },
    },
    "profit_story.cost_pressure.what_changed": {
        "en": {
            "rationale": "Profit bridge: net profit {delta_np_fmt} with OpEx {delta_opex_fmt} and revenue {delta_rev_fmt} ({previous_period} → {latest_period}).",
        },
        "ar": {
            "rationale": "جسر الربح: صافي الربح {delta_np_fmt} مع المصاريف التشغيلية {delta_opex_fmt} والإيراد {delta_rev_fmt} ({previous_period} → {latest_period}).",
        },
        "tr": {
            "rationale": "Kâr köprüsü: net kâr {delta_np_fmt}, faaliyet gideri {delta_opex_fmt}, gelir {delta_rev_fmt} ({previous_period} → {latest_period}).",
        },
    },
    "profit_story.cost_pressure.why": {
        "en": {
            "rationale": "Operating expense movement is the largest bridge driver versus revenue and COGS — OpEx pressure dominated the P&L path.",
        },
        "ar": {
            "rationale": "حركة المصاريف التشغيلية هي أكبر محرك في الجسر مقارنة بالإيراد وتكلفة المبيعات — ضغط المصاريف التشغيلية ساد مسار الأرباح والخسائر.",
        },
        "tr": {
            "rationale": "Faaliyet gideri hareketi, gelir ve SMM’ye kıyasla köprüde baskın sürücü — OpEx baskısı P&L yolunu belirledi.",
        },
    },
    "profit_story.cost_pressure.action": {
        "en": {
            "rationale": "Target OpEx categories with the largest period deltas; tie spend to revenue and margin guardrails.",
        },
        "ar": {
            "rationale": "استهدف فئات المصاريف التشغيلية ذات أكبر تغيرات الفترة؛ اربط الإنفاق بالإيراد وحدود الهامش.",
        },
        "tr": {
            "rationale": "Dönemde en büyük değişimi gösteren OpEx kalemlerini hedefleyin; harcamayı gelir ve marj sınırlarına bağlayın.",
        },
    },
    "profit_story.margin_compression.what_changed": {
        "en": {
            "rationale": "Profit bridge: net profit {delta_np_fmt}; COGS {delta_cogs_fmt}; gross profit {delta_gp_fmt}; revenue {delta_rev_fmt} ({previous_period} → {latest_period}).",
        },
        "ar": {
            "rationale": "جسر الربح: صافي الربح {delta_np_fmt}؛ تكلفة المبيعات {delta_cogs_fmt}؛ إجمالي الربح {delta_gp_fmt}؛ الإيراد {delta_rev_fmt} ({previous_period} → {latest_period}).",
        },
        "tr": {
            "rationale": "Kâr köprüsü: net kâr {delta_np_fmt}; SMM {delta_cogs_fmt}; brüt kâr {delta_gp_fmt}; gelir {delta_rev_fmt} ({previous_period} → {latest_period}).",
        },
    },
    "profit_story.margin_compression.why": {
        "en": {
            "rationale": "COGS movement is the dominant bridge lever — gross margin compressed before operating costs.",
        },
        "ar": {
            "rationale": "حركة تكلفة المبيعات هي الرافعة المهيمنة في الجسر — ضُغط الهامش الإجمالي قبل التكاليف التشغيلية.",
        },
        "tr": {
            "rationale": "SMM hareketi baskın köprü kolu — faaliyet öncesi brüt marj sıkıştı.",
        },
    },
    "profit_story.margin_compression.action": {
        "en": {
            "rationale": "Review COGS drivers (input prices, mix, waste); align pricing and procurement to recover gross margin.",
        },
        "ar": {
            "rationale": "راجع محركات تكلفة المبيعات (أسعار المدخلات، المزيج، الهدر)؛ وائم التسعير والمشتريات لاستعادة الهامش الإجمالي.",
        },
        "tr": {
            "rationale": "SMM sürücülerini gözden geçirin (girdi fiyatı, mix, fire); brüt marj için fiyat ve tedariki hizalayın.",
        },
    },
    "profit_story.healthy_growth.what_changed": {
        "en": {
            "rationale": "Profit bridge: net profit {delta_np_fmt} with revenue {delta_rev_fmt} as the primary driver ({previous_period} → {latest_period}).",
        },
        "ar": {
            "rationale": "جسر الربح: صافي الربح {delta_np_fmt} مع الإيراد {delta_rev_fmt} كالمحرك الأساسي ({previous_period} → {latest_period}).",
        },
        "tr": {
            "rationale": "Kâr köprüsü: net kâr {delta_np_fmt}, birincil sürücü gelir {delta_rev_fmt} ({previous_period} → {latest_period}).",
        },
    },
    "profit_story.healthy_growth.why": {
        "en": {
            "rationale": "Top-line expansion led the P&L improvement with net margin context {nm_pct}% — growth is funding profit.",
        },
        "ar": {
            "rationale": "توسع الإيرادات قاد تحسين قائمة الأرباح والخسائر مع هامش صافٍ {nm_pct}% — النمو يغذي الربح.",
        },
        "tr": {
            "rationale": "Üst hat genişlemesi P&L iyileşmesine öncülük etti; net marj bağlamı %{nm_pct} — büyüme kârı besliyor.",
        },
    },
    "profit_story.healthy_growth.action": {
        "en": {
            "rationale": "Protect gross and operating margin while scaling; monitor COGS and OpEx pass-through as revenue grows.",
        },
        "ar": {
            "rationale": "احم الهامش الإجمالي والتشغيلي أثناء التوسع؛ راقب تمرير تكلفة المبيعات والمصاريف مع نمو الإيراد.",
        },
        "tr": {
            "rationale": "Ölçeklenirken brüt ve faaliyet marjını koruyun; gelir büyürken SMM ve OpEx yansımasını izleyin.",
        },
    },
    "profit_story.profit_recovery.what_changed": {
        "en": {
            "rationale": "Profit bridge: net profit {delta_np_fmt} led by revenue {delta_rev_fmt}; latest net margin {nm_pct}% ({previous_period} → {latest_period}).",
        },
        "ar": {
            "rationale": "جسر الربح: صافي الربح {delta_np_fmt} بقيادة الإيراد {delta_rev_fmt}؛ أحدث هامش صافٍ {nm_pct}% ({previous_period} → {latest_period}).",
        },
        "tr": {
            "rationale": "Kâr köprüsü: net kâr {delta_np_fmt}, gelir {delta_rev_fmt} öncülüğünde; güncel net marj %{nm_pct} ({previous_period} → {latest_period}).",
        },
    },
    "profit_story.profit_recovery.why": {
        "en": {
            "rationale": "Profit improved while net margin remains below a typical health band — recovery is underway but margin discipline stays critical.",
        },
        "ar": {
            "rationale": "تحسن الربح مع بقاء الهامش الصافي دون نطاق صحة نموذجي — الاستعادة جارية لكن انضباط الهامش يبقى حاسماً.",
        },
        "tr": {
            "rationale": "Kâr iyileşti; net marj tipik sağlık bandının altında — toparlanma sürüyor, marj disiplini kritik.",
        },
    },
    "profit_story.profit_recovery.action": {
        "en": {
            "rationale": "Lock in revenue gains; continue cost and pricing actions until net margin clears sustainable targets.",
        },
        "ar": {
            "rationale": "ثبّت مكاسب الإيراد؛ واصل إجراءات التكلفة والتسعير حتى يتجاوز الهامش الصافي أهدافاً مستدامة.",
        },
        "tr": {
            "rationale": "Gelir kazanımlarını kilitleyin; net marj sürdürülebilir hedefleri aşana kadar maliyet ve fiyat adımlarını sürdürün.",
        },
    },
    "profit_story.mixed.what_changed": {
        "en": {
            "rationale": "Profit bridge ({previous_period} → {latest_period}): revenue {delta_rev_fmt}, COGS {delta_cogs_fmt}, OpEx {delta_opex_fmt}, net profit {delta_np_fmt}.",
        },
        "ar": {
            "rationale": "جسر الربح ({previous_period} → {latest_period}): الإيراد {delta_rev_fmt}، تكلفة المبيعات {delta_cogs_fmt}، المصاريف التشغيلية {delta_opex_fmt}، صافي الربح {delta_np_fmt}.",
        },
        "tr": {
            "rationale": "Kâr köprüsü ({previous_period} → {latest_period}): gelir {delta_rev_fmt}, SMM {delta_cogs_fmt}, OpEx {delta_opex_fmt}, net kâr {delta_np_fmt}.",
        },
    },
    "profit_story.mixed.why": {
        "en": {
            "rationale": "Offsetting movements across revenue, COGS, and OpEx — no single bridge line clearly dominated the outcome.",
        },
        "ar": {
            "rationale": "حركات متعاكسة عبر الإيراد وتكلفة المبيعات والمصاريف التشغيلية — لا سطر جسر واحد هيمن بوضوح على النتيجة.",
        },
        "tr": {
            "rationale": "Gelir, SMM ve OpEx üzerinde dengeleyici hareketler — sonucu tek bir köprü kalemi belirlemedi.",
        },
    },
    "profit_story.mixed.action": {
        "en": {
            "rationale": "Walk the full waterfall (revenue → COGS → OpEx → net); prioritize the next-largest absolute delta after executive review.",
        },
        "ar": {
            "rationale": "امشِ كامل الشلال (إيراد → تكلفة مبيعات → مصاريف تشغيلية → صافي)؛ أولوية لثاني أكبر تغير مطلق بعد المراجعة التنفيذية.",
        },
        "tr": {
            "rationale": "Tam şelaleyi yürüyün (gelir → SMM → OpEx → net); yönetici incelemesinden sonra mutlak değeri en büyük ikinci kaleme öncelik verin.",
        },
    },

    # ── Efficiency decisions ───────────────────────────────────────────────────
    "eff_cash_cycle_optimization": {
        "en": {
            "title":     "Cash Cycle Optimisation",
            "rationale": "Cash conversion cycle of {ccc} days means capital is locked in operations for too long, reducing financial flexibility.",
            "action":    "1) Reduce DSO: implement early-payment discounts (2/10 net 30) for top 10 customers. 2) Optimize inventory: reduce safety stock by 15% on slow-moving categories. 3) Extend DPO: renegotiate supplier payment terms from 30 to 45+ days. 4) Target CCC below 45 days within 2 quarters.",
            "impact":    "Reducing CCC by 15 days frees approximately {freed} in working capital.",
        },
        "ar": {
            "title":     "تحسين دورة النقد",
            "rationale": "دورة تحويل النقد {ccc} يوماً تعني أن رأس المال محتجز في العمليات لفترة طويلة جداً، مما يقلل المرونة المالية.",
            "action":    "1) تقليل DSO: تطبيق خصومات الدفع المبكر (2/10 net 30) لأكبر 10 عملاء. 2) تحسين المخزون: تقليل مخزون الأمان 15% للفئات بطيئة الحركة. 3) تمديد DPO: إعادة التفاوض على شروط دفع الموردين من 30 إلى 45+ يوم. 4) استهداف CCC أقل من 45 يوماً خلال ربعين.",
            "impact":    "تقليل دورة النقد بـ 15 يوماً يحرر تقريباً {freed} في رأس المال العامل.",
        },
        "tr": {
            "title":     "Nakit Döngüsü Optimizasyonu",
            "rationale": "Nakit döngüsü {ccc} gün, sermayenin çok uzun süre operasyonlarda kilitli kaldığı anlamına geliyor.",
            "action":    "1) DSO'yu azaltın: ilk 10 müşteriye erken ödeme indirimi uygulayın. 2) Stoğu optimize edin: yavaş hareket eden kategorilerde %15 güvenlik stoğu azaltın. 3) DPO'yu uzatın: tedarikçi ödeme koşullarını 45+ güne çıkarın.",
            "impact":    "CCC'yi 15 gün azaltmak yaklaşık {freed} işletme sermayesi serbest bırakır.",
        },
    },

    "eff_receivables_management": {
        "en": {
            "title":     "Strengthen Receivables Management",
            "rationale": "DSO of {dso} days indicates customers are taking too long to pay, creating unnecessary cash pressure.",
            "action":    "1) Segment customers by payment history — categorise into A/B/C tiers. 2) Implement stricter credit limits for C-tier customers. 3) Automate dunning process for invoices > 15 days overdue. 4) Consider invoice discounting for large outstanding balances.",
            "impact":    "Reducing DSO by 10 days improves monthly cash availability significantly.",
        },
        "ar": {
            "title":     "تعزيز إدارة المستحقات",
            "rationale": "أيام القبض {dso} يوماً تشير إلى أن العملاء يستغرقون وقتاً طويلاً للدفع، مما يخلق ضغطاً نقدياً غير ضروري.",
            "action":    "1) تصنيف العملاء حسب سجل الدفع — تصنيفهم في فئات A/B/C. 2) تطبيق حدود ائتمانية أكثر صرامة لعملاء الفئة C. 3) أتمتة عملية المطالبة للفواتير المتأخرة أكثر من 15 يوماً. 4) النظر في خصم الفواتير للأرصدة الكبيرة المستحقة.",
            "impact":    "تقليل أيام القبض بـ 10 أيام يحسن توفر النقد الشهري بشكل ملحوظ.",
        },
        "tr": {
            "title":     "Alacak Yönetimini Güçlendirin",
            "rationale": "DSO {dso} gün, müşterilerin ödemek için çok uzun süre aldığını gösteriyor.",
            "action":    "1) Müşterileri ödeme geçmişine göre A/B/C olarak sınıflandırın. 2) C kategorisi müşteriler için daha sıkı kredi limitleri uygulayın. 3) 15 günden fazla gecikmiş faturalar için otomatik tahsilat süreci kurun.",
            "impact":    "DSO'yu 10 gün azaltmak aylık nakit kullanılabilirliğini önemli ölçüde artırır.",
        },
    },

    # ── Leverage decisions ─────────────────────────────────────────────────────
    "lev_debt_reduction": {
        "en": {
            "title":     "Debt Reduction Strategy",
            "rationale": "Debt-to-equity of {de}x indicates elevated financial leverage. High debt increases vulnerability to interest rate changes and economic downturns.",
            "action":    "1) Map all debt by maturity, rate, and covenants. 2) Prioritise repayment of highest-cost debt. 3) Avoid taking on new debt for non-essential investments. 4) Target debt-to-equity below 1.5x within 18 months. 5) Evaluate sale-leaseback of non-core assets to reduce debt.",
            "impact":    "Lower leverage reduces financial risk and improves credit rating.",
        },
        "ar": {
            "title":     "استراتيجية تخفيض الديون",
            "rationale": "نسبة الدين إلى حقوق الملكية {de} تشير إلى رفع مالي مرتفع. الديون العالية تزيد من التعرض لتغيرات أسعار الفائدة والركود الاقتصادي.",
            "action":    "1) رسم خريطة لجميع الديون حسب الاستحقاق والمعدل والشروط. 2) إعطاء الأولوية لسداد الديون ذات التكلفة الأعلى. 3) تجنب أخذ ديون جديدة للاستثمارات غير الأساسية. 4) استهداف نسبة دين إلى حقوق ملكية أقل من 1.5x خلال 18 شهراً.",
            "impact":    "انخفاض الرفع المالي يقلل المخاطر المالية ويحسن التصنيف الائتماني.",
        },
        "tr": {
            "title":     "Borç Azaltma Stratejisi",
            "rationale": "Borç/özkaynaklar {de}x, yüksek finansal kaldıraç gösteriyor.",
            "action":    "1) Tüm borçları vade, faiz ve kovenant açısından haritalayın. 2) En yüksek maliyetli borçların öncelikli geri ödemesini yapın. 3) Temel olmayan yatırımlar için yeni borç almaktan kaçının.",
            "impact":    "Düşük kaldıraç finansal riski azaltır ve kredi notunu iyileştirir.",
        },
    },

    # ── Growth decisions ───────────────────────────────────────────────────────
    "growth_revenue_acceleration": {
        "en": {
            "title":     "Revenue Growth Acceleration",
            "rationale": "Revenue momentum is measurable: 3M avg MoM {rev_roll_3m}%, YoY {yoy_rev_pct}%, CAGR {cagr_rev_pct}% — trend {rev_dir} supports selective reinvestment behind demand.",
            "action":    "1) Identify the top 3 Revenue Drivers: new customer segments, new offerings, and expansion in high-performing markets. 2) Run a 90-day pilot for the highest-potential lever. 3) Allocate 5–10% of operating cash flow to growth initiatives. 4) Set quarterly Revenue growth targets with clear accountability.",
            "impact":    "Incremental revenue growth at current margins directly improves profit and owner value.",
        },
        "ar": {
            "title":     "تسريع نمو الإيرادات",
            "rationale": "زخم الإيرادات قابل للقياس: متوسط 3 أشهر {rev_roll_3m}%، سنوي {yoy_rev_pct}%، معدل نمو مركب {cagr_rev_pct}% — اتجاه {rev_dir} يدعم إعادة استثمار انتقائية.",
            "action":    "1) تحديد أهم 3 محركات للإيرادات: شرائح عملاء جديدة، عروض/خدمات جديدة، وتوسع في الأسواق الأعلى أداءً. 2) إجراء تجربة لمدة 90 يوماً للمحرك الأعلى تأثيراً. 3) تخصيص 5-10% من التدفق النقدي التشغيلي لمبادرات النمو. 4) تحديد أهداف نمو الإيرادات ربع سنوية مع مساءلة واضحة.",
            "impact":    "نمو الإيرادات الإضافي بالهوامش الحالية يحسن مباشرة الأرباح وقيمة المالك.",
        },
        "tr": {
            "title":     "Gelir Büyümesini Hızlandırın",
            "rationale": "Gelir ivmesi ölçülebilir: 3 aylık ort. MoM %{rev_roll_3m}, YoY %{yoy_rev_pct}, CAGR %{cagr_rev_pct} — {rev_dir} trendi seçici yatırımı destekliyor.",
            "action":    "1) En iyi 3 gelir büyüme kaldıraçlarını belirleyin: yeni müşteri segmentleri, yeni teklifler ve yüksek performanslı pazarlarda genişleme. 2) En yüksek potansiyelli kaldıraç için 90 günlük pilot çalıştırın. 3) Faaliyet nakit akışının %5-10'unu büyüme girişimlerine ayırın.",
            "impact":    "Mevcut marjlarla artan gelir büyümesi doğrudan kârı ve sahip değerini artırır.",
        },
    },

    "growth_margin_expansion": {
        "en": {
            "title":     "Margin Expansion While Growing",
            "rationale": "Revenue growing {rev_ytd}% YTD vs prior year — the business has momentum to invest in efficiency alongside growth.",
            "action":    "1) Use growth momentum to negotiate better supplier pricing (volume discounts). 2) Invest in workflow/process optimization to reduce unit costs and Operating Expenses intensity. 3) Cross-sell higher-margin offerings to existing customers. 4) Track Revenue per offering/customer segment vs total cost-to-serve monthly.",
            "impact":    "Combining top-line growth with margin management compounds owner value.",
        },
        "ar": {
            "title":     "توسع الهوامش أثناء النمو",
            "rationale": "الإيرادات في نمو {rev_ytd}% منذ بداية العام مقابل العام الماضي — الشركة تمتلك زخماً للاستثمار في الكفاءة جنباً إلى جنب مع النمو.",
            "action":    "1) استخدام زخم النمو للتفاوض على تسعير أفضل من الموردين (خصومات الحجم). 2) الاستثمار في تحسين سير العمل/العمليات لخفض تكلفة الوحدة وشدة المصروفات التشغيلية. 3) البيع التقاطعي للعروض ذات الهامش الأعلى للعملاء الحاليين. 4) تتبع الإيرادات حسب العرض/شريحة العميل مقابل إجمالي تكلفة الخدمة شهرياً.",
            "impact":    "الجمع بين نمو الإيرادات وإدارة الهوامش يُضاعف قيمة المالك.",
        },
        "tr": {
            "title":     "Büyürken Marj Genişletme",
            "rationale": "Gelir geçen yıla göre YBD'de %{rev_ytd} büyüyor.",
            "action":    "1) Büyüme momentumunu tedarikçilerle daha iyi fiyat müzakeresi için kullanın. 2) Birim maliyetleri ve işletme gideri yoğunluğunu azaltmak için süreç optimizasyonuna yatırım yapın. 3) Mevcut müşterilere daha yüksek marjlı teklifleri çapraz satın.",
            "impact":    "Üst hat büyümesini marj yönetimiyle birleştirmek sahip değerini katlar.",
        },
    },
}


def _t(key: str, lang: str, **kwargs) -> dict:
    entry = _DT.get(key, {})
    loc   = entry.get(lang) or entry.get("en") or {}
    def _f(s: str) -> str:
        try:    return s.format(**kwargs)
        except: return s
    return {k: _f(v) for k, v in loc.items()}


def _try_paradox_growth_negative_om_pack(
    analysis: Optional[dict],
    ratios: dict,
    lang: str,
) -> Optional[tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict]]]:
    """
    IF trailing 3M avg revenue growth vs prior 3M > 5% AND operating margin < 0
    → structured high-priority paradox decision + evidence metrics.
    """
    om = _get(ratios, "profitability", "operating_margin_pct", "value")
    if om is None or float(om) >= 0:
        return None
    rg = _revenue_growth_trailing_3m_vs_prior_3m(analysis)
    if rg is None or float(rg) <= 5:
        return None
    er = _latest_total_cost_ratio_pct_from_trends(analysis)

    fmt_rg = f"{float(rg):+.1f}"
    fmt_om = f"{float(om):.1f}"
    fmt_er = "—" if er is None else f"{float(er):.1f}"
    kwargs = {
        "revenue_growth_3m_pct": fmt_rg,
        "operating_margin_pct": fmt_om,
        "expense_ratio_pct": fmt_er,
    }
    txt = _t(PARADOX_GROWTH_MARGIN_KEY, lang, **kwargs)
    card = {
        "key": PARADOX_GROWTH_MARGIN_KEY,
        "domain": "profitability",
        **txt,
    }
    template_params = dict(kwargs)
    sm: list[dict] = [
        {"metric": "revenue_growth_trailing_3m_pct", "value": float(rg)},
        {"metric": "operating_margin_pct", "value": float(om)},
    ]
    if er is not None:
        sm.append({"metric": "expense_ratio_pct", "value": float(er)})
    fp = {
        "key": PARADOX_GROWTH_MARGIN_KEY,
        "domain": "profitability",
        "metrics": {
            "rev_g3": float(rg),
            "om": float(om),
            "er": float(er) if er is not None else None,
        },
    }
    return card, template_params, fp, sm


# ──────────────────────────────────────────────────────────────────────────────
#  Domain scoring
# ──────────────────────────────────────────────────────────────────────────────

def _get(d: dict, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d


def _score_domain(
    domain: str,
    ratios: dict,
    trends: dict,
    alerts: list,
    anomalies: list,
    *,
    depth: Optional[dict] = None,
    trend_mag: Optional[dict] = None,
) -> int:
    """Return 0–100 urgency score for a domain. 100 = critical."""
    score = 0

    if domain == "liquidity":
        cr_st = _get(ratios, "liquidity", "current_ratio", "status") or "neutral"
        wc_st = _get(ratios, "liquidity", "working_capital", "status") or "neutral"
        qr_st = _get(ratios, "liquidity", "quick_ratio", "status") or "neutral"
        score += {"risk": 40, "warning": 25, "neutral": 5, "good": 0}.get(cr_st, 0)
        score += {"risk": 35, "warning": 20, "neutral": 3, "good": 0}.get(wc_st, 0)
        score += {"risk": 25, "warning": 15, "neutral": 3, "good": 0}.get(qr_st, 0)
        # Trend penalty
        rev_dir = _get(trends, "revenue", "direction") or "insufficient_data"
        if rev_dir == "down": score += 15

    elif domain == "profitability":
        nm_st = _get(ratios, "profitability", "net_margin_pct", "status") or "neutral"
        gm_st = _get(ratios, "profitability", "gross_margin_pct", "status") or "neutral"
        score += {"risk": 45, "warning": 30, "neutral": 8, "good": 0}.get(nm_st, 0)
        score += {"risk": 30, "warning": 18, "neutral": 5, "good": 0}.get(gm_st, 0)
        np_dir = _get(trends, "net_profit", "direction") or "insufficient_data"
        if np_dir == "down": score += 15
        elif np_dir == "stable": score += 5

    elif domain == "efficiency":
        dso_st = _get(ratios, "efficiency", "dso_days", "status") or "neutral"
        ccc_st = _get(ratios, "efficiency", "ccc_days", "status") or "neutral"
        it_st  = _get(ratios, "efficiency", "inventory_turnover", "status") or "neutral"
        score += {"risk": 35, "warning": 20, "neutral": 5, "good": 0}.get(dso_st, 0)
        score += {"risk": 30, "warning": 18, "neutral": 4, "good": 0}.get(ccc_st, 0)
        score += {"risk": 20, "warning": 12, "neutral": 3, "good": 0}.get(it_st, 0)

    elif domain == "leverage":
        de_st = _get(ratios, "leverage", "debt_to_equity", "status") or "neutral"
        dr_st = _get(ratios, "leverage", "debt_ratio_pct", "status") or "neutral"
        score += {"risk": 40, "warning": 25, "neutral": 5, "good": 0}.get(de_st, 0)
        score += {"risk": 30, "warning": 18, "neutral": 4, "good": 0}.get(dr_st, 0)

    elif domain == "growth":
        rev_dir = _get(trends, "revenue",    "direction") or "insufficient_data"
        np_dir  = _get(trends, "net_profit", "direction") or "insufficient_data"
        ytd_rev = _get(trends, "revenue",    "ytd_vs_prior")
        # Growth opportunity: reward positive signals (inverse — score = opportunity, not urgency)
        if rev_dir == "up":    score += 30
        elif rev_dir == "stable": score += 15
        if np_dir == "up":    score += 25
        elif np_dir == "stable": score += 10
        if ytd_rev is not None and ytd_rev > 5: score += 20

    # Rolling / magnitude overlays (Phase 5B)
    dep = depth or {}
    tm = trend_mag or {}
    if domain == "growth":
        rr = tm.get("rev_roll_3m")
        if rr is not None:
            score += min(14, int(abs(float(rr)) * 1.4))
        cv = tm.get("rev_cagr")
        if cv is not None:
            score += min(12, int(abs(float(cv)) / 5))
        yv = tm.get("rev_yoy")
        if yv is not None:
            score += min(10, int(abs(float(yv)) / 6))
        ny = tm.get("np_yoy")
        if ny is not None:
            score += min(8, int(abs(float(ny)) / 8))
    elif domain == "liquidity":
        row = depth_get(dep, "liquidity.current_ratio")
        d6 = row.get("delta_vs_roll_6m")
        if d6 is not None and float(d6) <= -0.1:
            score += 12
        z = row.get("z_vs_roll6_excl_latest")
        if z is not None and float(z) <= -1.5:
            score += 10
    elif domain == "profitability":
        row = depth_get(dep, "profitability.net_margin_pct")
        d6 = row.get("delta_vs_roll_6m")
        if d6 is not None and float(d6) <= -1.0:
            score += 10
    elif domain == "efficiency":
        row = depth_get(dep, "efficiency.ccc_days")
        d6 = row.get("delta_vs_roll_6m")
        if d6 is not None and float(d6) >= 15:
            score += 10

    # Alert penalty boost
    for a in alerts:
        if domain in a.get("impact", ""):
            score += {"high": 15, "medium": 8, "low": 3}.get(a.get("severity", "low"), 0)

    # Anomaly boost — domain-targeted (series anomalies now populate via aligned keys)
    for an in anomalies:
        pts = {"critical": 10, "high": 6, "medium": 3}.get(an.get("severity", "medium"), 3)
        if domain in _anomaly_targets(an):
            score += pts

    return min(100, score)


# ──────────────────────────────────────────────────────────────────────────────
#  Decision selector
# ──────────────────────────────────────────────────────────────────────────────

def _select_decision(
    domain: str,
    ratios: dict,
    trends: dict,
    health_score: int,
    lang: str,
    *,
    depth_ctx: Optional[dict] = None,
    analysis: Optional[dict] = None,
) -> Optional[tuple[dict, dict[str, Any]]]:
    """Pick the most appropriate decision key for a domain and build the card.

    Returns ``(card, template_params)`` where ``template_params`` are the same
    keyword arguments passed into decision templates (for causal realization).
    """

    dep = depth_ctx or {}

    cr  = _get(ratios, "liquidity",     "current_ratio",    "value")
    qr  = _get(ratios, "liquidity",     "quick_ratio",      "value")
    wc  = _get(ratios, "liquidity",     "working_capital",  "value")
    nm  = _get(ratios, "profitability", "net_margin_pct",   "value")
    gm  = _get(ratios, "profitability", "gross_margin_pct", "value")
    dso = _get(ratios, "efficiency",    "dso_days",         "value")
    ccc = _get(ratios, "efficiency",    "ccc_days",         "value")
    de  = _get(ratios, "leverage",      "debt_to_equity",   "value")
    rev_ytd = _get(trends, "revenue",   "ytd_vs_prior")
    rev_dir = _get(trends, "revenue",   "direction") or "insufficient_data"
    np_dir  = _get(trends, "net_profit","direction") or "insufficient_data"
    rev_roll = _get(trends, "revenue", "rolling_3m")
    yoy_rev = _get(trends, "revenue", "yoy_change")
    cagr = _get(trends, "revenue", "cagr_pct")

    tr_raw = (analysis or {}).get("trends") or {}
    mom_s = tr_raw.get("revenue_mom_pct") or tr_raw.get("revenue_mom") or []
    last_mom = next((x for x in reversed(mom_s) if x is not None), None)

    cr_d = depth_get(dep, "liquidity.current_ratio")
    nm_d = depth_get(dep, "profitability.net_margin_pct")
    gm_d = depth_get(dep, "profitability.gross_margin_pct")

    def _fmt(v, fmt=".1f", fallback="—"):
        try: return format(float(v), fmt) if v is not None else fallback
        except: return fallback

    def _fmt_cr(v):  return _fmt(v, ".2f")
    def _fmt_nm(v):  return _fmt(v, ".1f")
    def _fmt_gm(v):  return _fmt(v, ".1f")
    def _fmt_de(v):  return _fmt(v, ".1f")
    def _fmt_dso(v): return str(round(v)) if v is not None else "—"
    def _fmt_ccc(v): return str(round(v)) if v is not None else "—"
    def _fmt_pct(v): return (f"{v:+.1f}%" if v is not None else "—")

    def _fmt_pct_num(v: Any) -> str:
        if v is None:
            return "—"
        try:
            return f"{float(v):+.1f}"
        except (TypeError, ValueError):
            return "—"

    def _pp_delta(row: dict) -> str:
        d = row.get("delta_vs_roll_6m")
        if d is None:
            return "—"
        try:
            return f"{float(d):+.2f}"
        except (TypeError, ValueError):
            return "—"

    # ── Estimate annual revenue from ratios for impact calculation ────────────
    rev_annual = None
    if nm is not None and nm > 0:
        np_val = _get(ratios, "profitability", "net_profit", "value")
        if np_val is not None:
            rev_annual = abs(float(np_val)) / (nm / 100)

    def _per_pp():
        """Value of 1 percentage point margin improvement."""
        if rev_annual and rev_annual > 0:
            v = rev_annual * 0.01
            if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
            if v >= 1_000:     return f"{v/1_000:.0f}K"
            return f"{v:.0f}"
        return "a meaningful amount"

    def _freed_by_ccc_reduction(days=15):
        """Approximate cash freed by reducing CCC by N days."""
        if rev_annual and rev_annual > 0:
            v = rev_annual / 365 * days
            if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
            if v >= 1_000:     return f"{v/1_000:.0f}K"
            return f"{v:.0f}"
        return "significant cash"

    key = None
    kwargs: dict[str, Any] = {}

    if domain == "liquidity":
        if cr is not None and cr < 1.0:
            key = "liq_immediate_cashflow"
            kwargs = {"cr": _fmt_cr(cr)}
        else:
            # Always attach numeric + vs-baseline context; material_weak flags urgency in scoring
            key = "liq_strengthen_working_capital"
            kwargs = {
                "cr": _fmt_cr(cr),
                "qr": _fmt_cr(qr),
                "wc": _fmt(wc, ".0f"),
                "cr_roll6m": _fmt_cr(cr_d.get("rolling_avg_6m")),
                "delta_cr_vs_roll6m": _pp_delta(cr_d),
            }

    elif domain == "profitability":
        if nm is not None and nm < 8:
            key = "prof_margin_recovery"
            kwargs = {
                "nm": _fmt_nm(nm),
                "per_pp": _per_pp(),
                "nm_roll6m": _fmt_nm(nm_d.get("rolling_avg_6m")),
                "delta_nm_vs_roll6m": _pp_delta(nm_d),
            }
        else:
            key = "prof_cost_structure_review"
            kwargs = {
                "gm": _fmt_gm(gm),
                "gm_roll6m": _fmt_gm(gm_d.get("rolling_avg_6m")),
                "delta_gm_vs_roll6m": _pp_delta(gm_d),
            }

    elif domain == "efficiency":
        if ccc is not None and ccc > 60:
            key = "eff_cash_cycle_optimization"
            kwargs = {"ccc": _fmt_ccc(ccc), "freed": _freed_by_ccc_reduction()}
        else:
            key = "eff_receivables_management"
            kwargs = {"dso": _fmt_dso(dso)}

    elif domain == "leverage":
        key = "lev_debt_reduction"
        kwargs = {"de": _fmt_de(de)}

    elif domain == "growth":
        mag_ok = False
        if rev_ytd is not None and abs(float(rev_ytd)) >= 3:
            mag_ok = True
        if yoy_rev is not None and abs(float(yoy_rev)) >= 5:
            mag_ok = True
        if cagr is not None and abs(float(cagr)) >= 6:
            mag_ok = True
        if rev_roll is not None and abs(float(rev_roll)) >= 1.5:
            mag_ok = True
        if last_mom is not None and abs(float(last_mom)) >= 4:
            mag_ok = True

        ytd_eff = rev_ytd
        if ytd_eff is None and yoy_rev is not None:
            ytd_eff = float(yoy_rev)

        gkw = {
            "rev_roll_3m": _fmt_pct_num(rev_roll),
            "yoy_rev_pct": _fmt_pct_num(yoy_rev),
            "cagr_rev_pct": _fmt_pct_num(cagr),
            "rev_dir": rev_dir,
        }
        if last_mom is not None and gkw["rev_roll_3m"] == "—":
            gkw["rev_roll_3m"] = _fmt_pct_num(last_mom)

        if rev_dir in ("up", "stable") and ytd_eff is not None and float(ytd_eff) > 5:
            key = "growth_margin_expansion"
            kwargs = {"rev_ytd": _fmt_pct(float(ytd_eff))}
        elif mag_ok and rev_dir in ("up", "stable", "insufficient_data"):
            key = "growth_revenue_acceleration"
            kwargs = dict(gkw)
        elif rev_dir in ("up", "stable"):
            key = "growth_margin_expansion"
            eff = ytd_eff if ytd_eff is not None else rev_roll if rev_roll is not None else last_mom
            if eff is None:
                eff = 0.0
            kwargs = {"rev_ytd": _fmt_pct(float(eff))}
        else:
            if not mag_ok:
                return None
            key = "growth_revenue_acceleration"
            kwargs = dict(gkw)

    if not key:
        return None

    txt = _t(key, lang, **kwargs)
    card = {
        "key":    key,
        "domain": domain,
        **txt,
    }
    return card, dict(kwargs)


def _urgency(domain_score: int) -> str:
    if domain_score >= 70: return "high"
    if domain_score >= 40: return "medium"
    return "low"


def _timeframe(domain_score: int) -> str:
    if domain_score >= 70: return "0-30 days"
    if domain_score >= 40: return "30-60 days"
    return "60-90 days"


def _impact_level(domain: str, domain_score: int) -> str:
    """Classify overall business impact of this domain's action."""
    if domain == "liquidity" and domain_score >= 30: return "high"
    if domain_score >= 60: return "high"
    if domain_score >= 30: return "medium"
    return "low"


def _linked_causes_for_domain(domain: str, alerts: list) -> list[dict]:
    """
    Map management alerts to the active decision domain (deterministic, id-based rules).
    """
    linked: list[dict] = []
    for a in alerts or []:
        aid = str(a.get("id") or "")
        imp = str(a.get("impact") or "")
        match = False
        if domain == "liquidity" and imp == "liquidity":
            match = True
        elif domain == "profitability" and imp == "profitability" and aid not in (
            "revenue_declining", "revenue_ytd_behind",
        ):
            match = True
        elif domain == "efficiency" and imp == "operational":
            match = True
        elif domain == "leverage" and "debt" in aid:
            match = True
        elif domain == "growth" and aid in ("revenue_declining", "revenue_ytd_behind"):
            match = True
        elif domain == "growth" and imp == "profitability" and aid.startswith("revenue_"):
            match = True
        if match:
            linked.append({
                "alert_id":   aid,
                "title":      a.get("title"),
                "severity":   a.get("severity"),
                "impact":     imp,
                "message":    a.get("message"),
                "confidence": a.get("confidence"),
            })
    return linked[:5]


def _depth_row_to_source_entry(metric_name: str, row: dict) -> dict[str, Any]:
    out: dict[str, Any] = {"metric": metric_name, "value": row.get("latest")}
    if row.get("rolling_avg_6m") is not None:
        out["rolling_avg_6m"] = row["rolling_avg_6m"]
    if row.get("rolling_avg_3m") is not None:
        out["rolling_avg_3m"] = row["rolling_avg_3m"]
    if row.get("delta_vs_roll_6m") is not None:
        out["delta_vs_roll_6m"] = row["delta_vs_roll_6m"]
    if row.get("yoy_change_pct") is not None:
        out["yoy_change_pct"] = row["yoy_change_pct"]
    if row.get("z_vs_roll6_excl_latest") is not None:
        out["z_vs_roll6_excl_latest"] = row["z_vs_roll6_excl_latest"]
    if row.get("percentile_in_window") is not None:
        out["percentile_in_window"] = row["percentile_in_window"]
    return out


def _decision_source_metrics(
    domain: str,
    ratios: dict,
    trends: dict,
    depth_ctx: Optional[dict] = None,
) -> list[dict]:
    """Deterministic metric bundle tied to the decision domain (for audit / UI)."""
    sm: list[dict] = []
    dep = depth_ctx or {}

    if domain == "liquidity":
        for m in ("current_ratio", "quick_ratio", "working_capital"):
            v = _get(ratios, "liquidity", m, "value")
            if v is not None:
                sm.append({"metric": m, "value": v})
        cr_row = depth_get(dep, "liquidity.current_ratio")
        if cr_row.get("latest") is not None or cr_row.get("rolling_avg_6m") is not None:
            sm.append(_depth_row_to_source_entry("current_ratio_depth", cr_row))
    elif domain == "profitability":
        for m in ("net_margin_pct", "gross_margin_pct", "operating_margin_pct", "net_profit"):
            v = _get(ratios, "profitability", m, "value")
            if v is not None:
                sm.append({"metric": m, "value": v})
        for path, label in (
            ("profitability.net_margin_pct", "net_margin_pct_depth"),
            ("profitability.gross_margin_pct", "gross_margin_pct_depth"),
        ):
            row = depth_get(dep, path)
            if row.get("latest") is not None or row.get("rolling_avg_6m") is not None:
                sm.append(_depth_row_to_source_entry(label, row))
    elif domain == "efficiency":
        for m in ("dso_days", "dpo_days", "ccc_days", "inventory_turnover"):
            v = _get(ratios, "efficiency", m, "value")
            if v is not None:
                sm.append({"metric": m, "value": v})
        ccc_row = depth_get(dep, "efficiency.ccc_days")
        if ccc_row.get("latest") is not None or ccc_row.get("rolling_avg_6m") is not None:
            sm.append(_depth_row_to_source_entry("ccc_days_depth", ccc_row))
    elif domain == "leverage":
        for m in ("debt_to_equity", "debt_ratio_pct"):
            v = _get(ratios, "leverage", m, "value")
            if v is not None:
                sm.append({"metric": m, "value": v})
        de_row = depth_get(dep, "leverage.debt_to_equity")
        if de_row.get("latest") is not None or de_row.get("rolling_avg_6m") is not None:
            sm.append(_depth_row_to_source_entry("debt_to_equity_depth", de_row))
    elif domain == "growth":
        ry = _get(trends, "revenue", "ytd_vs_prior")
        if ry is not None:
            sm.append({"metric": "revenue_ytd_vs_prior_pct", "value": ry})
        rr = _get(trends, "revenue", "rolling_3m")
        if rr is not None:
            sm.append({"metric": "revenue_rolling_3m_mom_avg_pct", "value": rr})
        yoy = _get(trends, "revenue", "yoy_change")
        if yoy is not None:
            sm.append({"metric": "revenue_yoy_change_pct", "value": yoy})
        cg = _get(trends, "revenue", "cagr_pct")
        if cg is not None:
            sm.append({"metric": "revenue_cagr_pct", "value": cg})
    rd = _get(trends, "revenue", "direction")
    if rd and rd != "insufficient_data":
        sm.append({"metric": "revenue_trend_direction", "value": rd})
    nd = _get(trends, "net_profit", "direction")
    if nd and nd != "insufficient_data":
        sm.append({"metric": "net_profit_trend_direction", "value": nd})
    return sm


def _evidence_delta_slice(domain: str, depth_ctx: dict) -> dict[str, Any]:
    path = {
        "liquidity": "liquidity.current_ratio",
        "profitability": "profitability.net_margin_pct",
        "efficiency": "efficiency.ccc_days",
        "leverage": "leverage.debt_to_equity",
        "growth": "profitability.net_margin_pct",
    }.get(domain, "")
    row = depth_get(depth_ctx or {}, path)
    return {
        "metric_path": path,
        "delta_vs_roll_6m": row.get("delta_vs_roll_6m"),
        "delta_vs_roll_3m": row.get("delta_vs_roll_3m"),
        "z_vs_roll6_excl_latest": row.get("z_vs_roll6_excl_latest"),
    }


def _confidence(domain_score: int, health: int, n_periods: int) -> int:
    base = min(90, domain_score)
    if health < 40:        base += 5
    if n_periods >= 6:     base += 5
    elif n_periods <= 2:   base -= 10
    return min(95, max(50, base))


# ──────────────────────────────────────────────────────────────────────────────
#  Wave 2B — causal_items (parallel to decisions; no realization here)
# ──────────────────────────────────────────────────────────────────────────────

_DECISION_CAUSAL_PREFIX = "decision.causal"

_TOPIC_BY_DOMAIN: dict[str, str] = {
    "liquidity": "liquidity",
    "profitability": "margin",
    "efficiency": "efficiency",
    "leverage": "leverage",
    "growth": "growth",
}


def _topic_for_decision_domain(domain: str) -> str:
    return _TOPIC_BY_DOMAIN.get(domain, domain)


def _causal_severity_from_urgency_impact(urgency: str, impact_level: str) -> str:
    """Worst of urgency and impact_level (both high|medium|low)."""
    order = {"high": 0, "medium": 1, "low": 2}
    u = order.get(str(urgency or "medium").lower(), 1)
    i = order.get(str(impact_level or "medium").lower(), 1)
    worst = min(u, i)
    return {0: "high", 1: "medium", 2: "low"}[worst]


def _source_metrics_list_to_dict(rows: list) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        m = row.get("metric")
        if m is not None:
            out[str(m)] = row.get("value")
    return out


def _causal_params_for_decision(
    template_params: dict[str, Any],
    domain: str,
    priority_rank: int,
    source_metrics_rows: list,
) -> dict[str, Any]:
    """Flat params: template slots first, then extra metrics (no overwrite)."""
    params: dict[str, Any] = dict(template_params)
    sm = _source_metrics_list_to_dict(source_metrics_rows)
    for k in sorted(sm.keys()):
        if k not in params:
            params[k] = sm[k]
    params["domain"] = domain
    params["decision_priority_rank"] = priority_rank
    return params


def _profit_story_fragment(key: Optional[str], lang: str, params: dict) -> str:
    if not key or key not in _DT:
        return ""
    entry = _DT[key]
    loc = entry.get(lang) or entry.get("en") or {}
    text = str(loc.get("rationale") or "")
    try:
        return text.format(**params)
    except Exception:
        return text


def _effective_profit_story(analysis: Optional[dict]) -> Optional[dict]:
    if not analysis:
        return None
    s = analysis.get("structured_profit_story")
    if isinstance(s, dict) and s.get("summary_type") is not None:
        return s
    if analysis.get("structured_profit_bridge"):
        return build_structured_profit_story_from_analysis(analysis)
    return None


def _should_bridge_back_reason(
    eff_domain: str,
    domain: str,
    card_key: str,
    summary_type: Optional[str],
) -> bool:
    if not summary_type or summary_type == "mixed":
        return False
    if eff_domain == "profitability" and card_key in (
        "prof_margin_recovery",
        "prof_cost_structure_review",
        PARADOX_GROWTH_MARGIN_KEY,
    ):
        return True
    if domain == "growth" and card_key == "growth_margin_expansion":
        return summary_type in ("healthy_growth", "profit_recovery")
    return False


def _attach_profit_bridge_to_decision(
    card: dict,
    template_params: dict[str, Any],
    analysis: Optional[dict],
    domain: str,
    eff_domain: str,
    lang: str,
) -> dict[str, Any]:
    """Attach bridge + story to evidence; prepend bridge-backed rationale for applicable cards."""
    story = _effective_profit_story(analysis)
    ev = card.get("evidence")
    if not isinstance(ev, dict):
        return template_params

    if analysis:
        for k in (
            "structured_profit_bridge",
            "structured_profit_bridge_interpretation",
            "structured_profit_bridge_meta",
        ):
            v = analysis.get(k)
            if v is not None:
                ev[k] = v
    if story is not None:
        ev["structured_profit_story"] = story

    st = story.get("summary_type") if isinstance(story, dict) else None
    if not story or not _should_bridge_back_reason(
        eff_domain, domain, str(card.get("key") or ""), st
    ):
        return template_params

    wparams = story.get("what_changed_params") or {}
    yparams = story.get("why_params") or {}
    aparams = story.get("action_params") or {}
    parts = [
        _profit_story_fragment(story.get("what_changed_key"), lang, wparams),
        _profit_story_fragment(story.get("why_key"), lang, yparams),
        _profit_story_fragment(story.get("action_key"), lang, aparams),
    ]
    bridge_block = " ".join(p for p in parts if p).strip()
    if bridge_block:
        orig = card.get("reason") or ""
        card["reason"] = f"{bridge_block}\n\nContext: {orig}".strip()

    merged = dict(template_params)
    merged["bridge_story_summary_type"] = st
    return merged


def _causal_item_for_decision(card: dict, template_params: dict[str, Any]) -> dict:
    tk = str(card.get("key") or "")
    domain = str(card.get("domain") or "")
    rank = int(card.get("priority") or 0)
    cid = f"decision:{domain}:{tk}:{rank}"
    sm_rows = card.get("source_metrics") or []
    params = _causal_params_for_decision(template_params, domain, rank, sm_rows)
    sev = _causal_severity_from_urgency_impact(
        str(card.get("urgency") or ""),
        str(card.get("impact_level") or ""),
    )
    merged_from = [tk] if tk else []
    template_ids = [f"cfo_decision.{tk}"] if tk else []
    return {
        "id": cid,
        "topic": _topic_for_decision_domain(domain),
        "change": {"key": f"{_DECISION_CAUSAL_PREFIX}.{tk}.change", "params": params},
        "cause": {"key": f"{_DECISION_CAUSAL_PREFIX}.{tk}.cause", "params": params},
        "action": {"key": f"{_DECISION_CAUSAL_PREFIX}.{tk}.action", "params": params},
        "severity": sev,
        "source": "decision",
        "evidence": {
            "source_metrics": _source_metrics_list_to_dict(sm_rows),
            "template_ids": template_ids,
            "merged_from": merged_from,
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_cfo_decisions(
    intelligence: dict,
    alerts: list,
    lang: str = "en",
    n_periods: int = 3,
    top_n: int = 3,
    analysis: Optional[dict] = None,
    branch_context: Optional[dict] = None,
    prior_decision_fingerprints: Optional[list] = None,
) -> dict:
    """
    Build top-N CFO-level prioritized decisions from Phase 21/23 intelligence.

    Args:
        intelligence: output of fin_intelligence.build_intelligence()
        alerts:       output of alerts_engine.build_alerts()["alerts"]
        lang:         "en" | "ar" | "tr"
        n_periods:    number of periods in the analysis window (affects confidence)
        top_n:        how many decisions to return (default 3)
        analysis:     output of run_analysis() — enables rolling baselines & growth MoM tail
        branch_context: optional portfolio snapshot (2+ branches) for segmentation boost
        prior_decision_fingerprints: optional list of prior ``_build_decision_fingerprint`` dicts;
            suppresses a decision when key+domain match and tracked metrics are unchanged

    Returns:
        {
          "decisions": [...],
          "causal_items": [...],  # Wave 2B: parallel causal rows (same order as decisions)
          "recommendations": [{ "recommendation", "reason", "priority" }, ...],
          "domain_scores": { ... },
        }
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"

    ratios    = intelligence.get("ratios",    {})
    trends    = intelligence.get("trends",    {})
    anomalies = intelligence.get("anomalies", [])
    health    = intelligence.get("health_score_v2", 50)

    depth_ctx = build_ratio_depth_context(analysis)
    trend_mag = _trend_mag_dict(trends)

    # ── Score every domain ─────────────────────────────────────────────────────
    domains = ["liquidity", "profitability", "efficiency", "leverage", "growth"]
    raw_scores: dict[str, int] = {}
    for d in domains:
        raw_scores[d] = _score_domain(
            d, ratios, trends, alerts, anomalies,
            depth=depth_ctx,
            trend_mag=trend_mag,
        )

    nm_company = _get(ratios, "profitability", "net_margin_pct", "value")
    branch_seg = _branch_profitability_concentration(branch_context, nm_company)
    if branch_seg:
        raw_scores["profitability"] = min(100, raw_scores["profitability"] + 12)

    # ── Apply domain weights — liquidity always first if score >= 30 ───────────
    weighted: list[tuple[int, str]] = []
    for d in domains:
        s = raw_scores[d]
        w = DOMAIN_WEIGHTS.get(d, 10)
        if d == "liquidity" and s >= 30:
            effective = s * (w / 35) * 1.4
        else:
            effective = s * (w / 100)
        weighted.append((effective, d))

    weighted.sort(key=lambda x: -x[0])

    decisions: list[dict] = []
    causal_items: list[dict] = []
    skipped_stale = 0

    # ── Growth vs profit paradox (Phase 5C): rank above generic cost-structure cards
    paradox_pack = _try_paradox_growth_negative_om_pack(analysis, ratios, lang)
    if paradox_pack:
        _pc, _tp, paradox_fp_pre, _psm = paradox_pack
        if prior_decision_fingerprints and _fingerprint_is_stale(
            paradox_fp_pre, prior_decision_fingerprints
        ):
            paradox_pack = None
            skipped_stale += 1
        else:
            weighted.insert(0, (1_000_000.0, _PARADOX_DOMAIN_TOKEN))

    # ── Build decision cards (walk ranked domains until top_n emitted) ──────────
    pool_i = 0
    trend_mag_block = {
        "revenue_rolling_3m_mom_avg_pct": trend_mag.get("rev_roll_3m"),
        "net_profit_rolling_3m_mom_avg_pct": trend_mag.get("np_roll_3m"),
        "revenue_yoy_change_pct": trend_mag.get("rev_yoy"),
        "net_profit_yoy_change_pct": trend_mag.get("np_yoy"),
        "revenue_cagr_pct": trend_mag.get("rev_cagr"),
        "revenue_ytd_vs_prior_pct": trend_mag.get("rev_ytd"),
    }

    while len(decisions) < top_n and pool_i < len(weighted):
        eff_score, domain = weighted[pool_i]
        pool_i += 1

        if domain == _PARADOX_DOMAIN_TOKEN:
            if not paradox_pack:
                continue
            p_card, template_params, fp, paradox_sm = paradox_pack
            card = dict(p_card)
            card["source_metrics"] = paradox_sm
        else:
            selected = _select_decision(
                domain, ratios, trends, health, lang,
                depth_ctx=depth_ctx,
                analysis=analysis,
            )
            if selected is None:
                continue
            card, template_params = selected
            if (
                card.get("key") == "prof_cost_structure_review"
                and any(d.get("key") == PARADOX_GROWTH_MARGIN_KEY for d in decisions)
            ):
                continue
            fp = _build_decision_fingerprint(
                card["key"], domain, ratios, depth_ctx,
            )
            if prior_decision_fingerprints and _fingerprint_is_stale(
                fp, prior_decision_fingerprints,
            ):
                skipped_stale += 1
                continue

        if domain == _PARADOX_DOMAIN_TOKEN:
            raw = min(100, raw_scores.get("profitability", 55) + 35)
        else:
            raw = raw_scores[domain]
        card["priority"]        = len(decisions) + 1
        if domain == _PARADOX_DOMAIN_TOKEN:
            card["urgency"] = "high"
            card["impact_level"] = "high"
            card["action_type"] = "paradox_growth_negative_operating_margin"
        else:
            card["urgency"] = _urgency(raw)
            card["impact_level"] = _impact_level(domain, raw)
        card["timeframe"]       = _timeframe(raw)
        card["time_horizon"]    = card["timeframe"]
        card["confidence"]      = _confidence(raw, health, n_periods)
        card["priority_score"]  = round(eff_score, 1)
        card["reason"]          = card.pop("rationale", "")
        card["expected_effect"] = card.pop("impact", "")
        card["expected_impact"] = card["expected_effect"]
        card["action"]          = card.get("action", "")
        if domain != _PARADOX_DOMAIN_TOKEN:
            card["source_metrics"] = _decision_source_metrics(
                domain, ratios, trends, depth_ctx,
            )
        card["decision_title"]  = card.get("title", "")
        eff_domain = "profitability" if domain == _PARADOX_DOMAIN_TOKEN else domain
        card["linked_causes"]   = _linked_causes_for_domain(eff_domain, alerts)

        seg = branch_seg if eff_domain == "profitability" else None
        if seg:
            card["branch_id"] = seg["branch_id"]
            card["branch_name"] = seg["branch_name"]
            card["revenue_contribution_pct"] = seg["revenue_contribution_pct"]
            template_params = dict(template_params)
            template_params.setdefault("branch_name", seg["branch_name"])
            template_params.setdefault("branch_net_margin_pct", seg["branch_net_margin_pct"])
            template_params.setdefault("company_net_margin_pct", seg["company_net_margin_pct"])
            template_params.setdefault("branch_revenue_share_pct", seg["revenue_contribution_pct"])

        ps = depth_ctx.get("period_span") if depth_ctx else None
        card["evidence"]        = {
            "health_score_v2": health,
            "domain_urgency_score": raw,
            "source_metrics": card["source_metrics"],
            "linked_alerts": [x.get("alert_id") for x in card["linked_causes"]],
            "period_span": ps,
            "baseline": {
                "rolling_6m_mean_label": "Trailing mean of last ≤6 periods (see source_metrics *_depth rows)",
                "ratio_depth_metrics": depth_ctx.get("metrics") if depth_ctx else {},
            },
            "current": {
                "as_of_period": (ps or {}).get("to_period"),
            },
            "delta": _evidence_delta_slice(eff_domain, depth_ctx),
            "financial_paradox": (
                {"type": "growth_vs_negative_operating_margin"}
                if card.get("key") == PARADOX_GROWTH_MARGIN_KEY
                else None
            ),
            "trend_magnitude": trend_mag_block,
            "segmentation": seg,
            "repeat_control": {
                "fingerprint": fp,
                "suppressed_as_stale": False,
                "prior_fingerprints_supplied": bool(prior_decision_fingerprints),
            },
        }
        if card.get("scope") is None and seg:
            card["scope"] = "branch"
        elif card.get("scope") is None:
            card["scope"] = "company"

        template_params = _attach_profit_bridge_to_decision(
            card, template_params, analysis, domain, eff_domain, lang,
        )

        decisions.append(card)
        causal_items.append(_causal_item_for_decision(card, template_params))

    top_focus = decisions[0]["domain"] if decisions else ""
    top_domain = decisions[0]["domain"] if decisions else ""
    fin_paradox_summary = None
    if any(d.get("key") == PARADOX_GROWTH_MARGIN_KEY for d in decisions):
        fin_paradox_summary = "growth_vs_negative_operating_margin"

    recommendations = _build_actionable_recommendations(
        intelligence,
        alerts,
        lang,
        analysis=analysis,
        branch_context=branch_context,
    )

    return {
        "decisions":         decisions,
        "causal_items":      causal_items,
        "recommendations":   recommendations,
        "domain_scores":     raw_scores,
        "summary": {
            "top_focus":        top_focus,
            "top_focus_domain": top_domain,
            "health_score":     health,
            "total":            len(decisions),
            "insufficient_evidence": len(decisions) == 0,
            "financial_paradox": fin_paradox_summary,
            "repeat_control": {
                "skipped_stale_repeats": skipped_stale,
                "prior_fingerprints_supplied": bool(prior_decision_fingerprints),
            },
        },
    }
