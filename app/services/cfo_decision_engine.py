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

_REC_SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}


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
            reason = "Liquidity signals require near-term action to prevent cash pressure."
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
            reason = "Revenue is growing but net profit is under pressure — prioritize cost efficiency."
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
            "rationale": "Working capital is below optimal levels. The business needs a buffer to absorb operational fluctuations without disrupting payments.",
            "action":    "1) Implement 30-day payment terms for all new customer contracts. 2) Set up automated invoice reminders at 15, 30, and 45 days. 3) Consider factoring receivables to unlock trapped cash. 4) Target working capital ratio of 1.5x within 2 quarters.",
            "impact":    "Improves operational resilience and reduces reliance on credit lines.",
        },
        "ar": {
            "title":     "تعزيز موقف رأس المال العامل",
            "rationale": "رأس المال العامل أقل من المستويات المثلى. الشركة بحاجة إلى هامش لامتصاص التقلبات التشغيلية دون تعطيل المدفوعات.",
            "action":    "1) تطبيق شروط دفع 30 يوماً لجميع عقود العملاء الجديدة. 2) إعداد تذكيرات فاتورة آلية في 15 و30 و45 يوماً. 3) النظر في خصم الفواتير لتحرير النقد المحتجز. 4) استهداف نسبة رأس مال عامل 1.5x خلال ربعين.",
            "impact":    "يحسن المرونة التشغيلية ويقلل الاعتماد على خطوط الائتمان.",
        },
        "tr": {
            "title":     "İşletme Sermayesini Güçlendirin",
            "rationale": "İşletme sermayesi optimum seviyenin altında.",
            "action":    "1) Tüm yeni müşteri sözleşmeleri için 30 günlük ödeme koşulları uygulayın. 2) 15, 30 ve 45. günlerde otomatik fatura hatırlatmaları kurun. 3) Alacakların faktoring yoluyla nakde çevrilmesini değerlendirin.",
            "impact":    "Operasyonel dayanıklılığı artırır ve kredi limitlerine bağımlılığı azaltır.",
        },
    },

    # ── Profitability decisions ────────────────────────────────────────────────
    "prof_margin_recovery": {
        "en": {
            "title":     "Margin Recovery Programme",
            "rationale": "Net margin {nm}% is below a healthy range for sustainable financial performance. Sustained margin pressure will erode equity over time.",
            "action":    "1) Run unit economics analysis (cost per unit/service line) — identify margin leakage. 2) Review the largest Cost Drivers (COGS and Operating Expenses) and their allocation logic. 3) Update pricing and customer segmentation for low-margin segments. 4) Target a minimum 12% Net Margin within 3 quarters.",
            "impact":    "Each 1pp margin improvement on current revenue ≈ {per_pp} additional annual profit.",
        },
        "ar": {
            "title":     "برنامج استعادة الهوامش",
            "rationale": "الهامش الصافي {nm}% أقل من النطاق الصحي للأداء المالي المستدام. استمرار ضغط الهوامش سيؤدي إلى تآكل حقوق الملكية بمرور الوقت.",
            "action":    "1) إجراء تحليل اقتصاديات الوحدة (التكلفة لكل وحدة/خط خدمة) لتحديد تسرب الهوامش. 2) مراجعة أكبر محركات التكاليف (تكلفة المبيعات والمصروفات التشغيلية) ومنهجية توزيعها. 3) تحديث التسعير وتقسيم العملاء لشرائح الهامش المنخفض. 4) استهداف هامش صافي لا يقل عن 12% خلال 3 أرباع.",
            "impact":    "كل تحسن بنسبة 1 نقطة مئوية في الهامش على الإيرادات الحالية ≈ {per_pp} ربح إضافي سنوي.",
        },
        "tr": {
            "title":     "Marj İyileştirme Programı",
            "rationale": "Net marj %{nm}, sürdürülebilir finansal performans için sağlıklı aralığın altında.",
            "action":    "1) Birim ekonomisi analizi (birim/hizmet hattı başına maliyet) yapın ve marj kaçaklarını bulun. 2) En büyük maliyet etkenlerini (COGS ve işletme giderleri) ve tahsis mantığını gözden geçirin. 3) Düşük marjlı segmentler için fiyatlandırma ve müşteri segmentasyonunu güncelleyin.",
            "impact":    "Mevcut gelirde her 1 puanlık marj iyileşmesi ≈ {per_pp} ek yıllık kar.",
        },
    },

    "prof_cost_structure_review": {
        "en": {
            "title":     "Strategic Cost Structure Review",
            "rationale": "Gross margin {gm}% and operating costs suggest room for structural improvement. Without action, profitability will remain compressed.",
            "action":    "1) Map all cost centres by percentage of revenue — benchmark against peers. 2) Identify top 5 cost drivers and set 5% reduction targets. 3) Evaluate outsourcing non-core activities (maintenance, admin). 4) Implement monthly cost performance reviews with department heads.",
            "impact":    "Structural cost reduction improves both margins and long-term competitiveness.",
        },
        "ar": {
            "title":     "مراجعة هيكل التكاليف الاستراتيجية",
            "rationale": "هامش الربح الإجمالي {gm}% والتكاليف التشغيلية تشير إلى وجود مجال للتحسين الهيكلي. بدون إجراء، ستبقى الربحية مضغوطة.",
            "action":    "1) رسم خريطة لجميع مراكز التكاليف كنسبة مئوية من الإيرادات — المقارنة مع النظراء. 2) تحديد أكبر 5 محركات للتكاليف وتحديد أهداف تخفيض 5%. 3) تقييم الاستعانة بمصادر خارجية للأنشطة غير الأساسية. 4) تطبيق مراجعات شهرية لأداء التكاليف مع رؤساء الأقسام.",
            "impact":    "تخفيض التكاليف الهيكلي يحسن الهوامش والقدرة التنافسية على المدى الطويل.",
        },
        "tr": {
            "title":     "Stratejik Maliyet Yapısı Gözden Geçirme",
            "rationale": "Brüt marj %{gm} ve işletme maliyetleri yapısal iyileştirme alanı olduğunu gösteriyor.",
            "action":    "1) Tüm maliyet merkezlerini gelirin yüzdesi olarak haritalayın. 2) En büyük 5 maliyet etkenini belirleyin ve %5 azaltma hedefleri koyun. 3) Çekirdek dışı faaliyetler için dış kaynak kullanımını değerlendirin.",
            "impact":    "Yapısal maliyet azaltımı marjları ve uzun vadeli rekabetçiliği artırır.",
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
            "rationale": "Revenue trend is stable-to-positive and financial position supports controlled growth investment.",
            "action":    "1) Identify the top 3 Revenue Drivers: new customer segments, new offerings, and expansion in high-performing markets. 2) Run a 90-day pilot for the highest-potential lever. 3) Allocate 5–10% of operating cash flow to growth initiatives. 4) Set quarterly Revenue growth targets with clear accountability.",
            "impact":    "Incremental revenue growth at current margins directly improves profit and owner value.",
        },
        "ar": {
            "title":     "تسريع نمو الإيرادات",
            "rationale": "اتجاه الإيرادات مستقر إلى إيجابي والوضع المالي يدعم الاستثمار في النمو المتحكم فيه.",
            "action":    "1) تحديد أهم 3 محركات للإيرادات: شرائح عملاء جديدة، عروض/خدمات جديدة، وتوسع في الأسواق الأعلى أداءً. 2) إجراء تجربة لمدة 90 يوماً للمحرك الأعلى تأثيراً. 3) تخصيص 5-10% من التدفق النقدي التشغيلي لمبادرات النمو. 4) تحديد أهداف نمو الإيرادات ربع سنوية مع مساءلة واضحة.",
            "impact":    "نمو الإيرادات الإضافي بالهوامش الحالية يحسن مباشرة الأرباح وقيمة المالك.",
        },
        "tr": {
            "title":     "Gelir Büyümesini Hızlandırın",
            "rationale": "Gelir trendi stabil-pozitif ve finansal durum kontrollü büyüme yatırımını destekliyor.",
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


# ──────────────────────────────────────────────────────────────────────────────
#  Domain scoring
# ──────────────────────────────────────────────────────────────────────────────

def _get(d: dict, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d


def _score_domain(domain: str, ratios: dict, trends: dict,
                   alerts: list, anomalies: list) -> int:
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

    # Alert penalty boost
    for a in alerts:
        if domain in a.get("impact", ""):
            score += {"high": 15, "medium": 8, "low": 3}.get(a.get("severity", "low"), 0)

    # Anomaly boost
    for an in anomalies:
        score += {"critical": 10, "high": 6, "medium": 3}.get(an.get("severity", "medium"), 0)

    return min(100, score)


# ──────────────────────────────────────────────────────────────────────────────
#  Decision selector
# ──────────────────────────────────────────────────────────────────────────────

def _select_decision(domain: str, ratios: dict, trends: dict,
                     health_score: int, lang: str) -> Optional[tuple[dict, dict[str, Any]]]:
    """Pick the most appropriate decision key for a domain and build the card.

    Returns ``(card, template_params)`` where ``template_params`` are the same
    keyword arguments passed into decision templates (for causal realization).
    """

    cr  = _get(ratios, "liquidity",     "current_ratio",    "value")
    wc  = _get(ratios, "liquidity",     "working_capital",  "value")
    nm  = _get(ratios, "profitability", "net_margin_pct",   "value")
    gm  = _get(ratios, "profitability", "gross_margin_pct", "value")
    dso = _get(ratios, "efficiency",    "dso_days",         "value")
    ccc = _get(ratios, "efficiency",    "ccc_days",         "value")
    de  = _get(ratios, "leverage",      "debt_to_equity",   "value")
    rev_ytd = _get(trends, "revenue",   "ytd_vs_prior")
    rev_dir = _get(trends, "revenue",   "direction") or "insufficient_data"
    np_dir  = _get(trends, "net_profit","direction") or "insufficient_data"

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

    # ── Estimate annual revenue from ratios for impact calculation ────────────
    # Use net_profit / net_margin_pct to back-calculate revenue
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
    kwargs = {}

    if domain == "liquidity":
        if cr is not None and cr < 1.0:
            key = "liq_immediate_cashflow"
            kwargs = {"cr": _fmt_cr(cr)}
        else:
            key = "liq_strengthen_working_capital"
            kwargs = {}

    elif domain == "profitability":
        if nm is not None and nm < 8:
            key = "prof_margin_recovery"
            kwargs = {"nm": _fmt_nm(nm), "per_pp": _per_pp()}
        else:
            key = "prof_cost_structure_review"
            kwargs = {"gm": _fmt_gm(gm)}

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
        if rev_dir in ("up", "stable") and (rev_ytd or 0) > 5:
            key = "growth_margin_expansion"
            kwargs = {"rev_ytd": _fmt_pct(rev_ytd)}
        else:
            key = "growth_revenue_acceleration"
            kwargs = {}

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


def _decision_source_metrics(domain: str, ratios: dict, trends: dict) -> list[dict]:
    """Deterministic metric bundle tied to the decision domain (for audit / UI)."""
    sm: list[dict] = []
    if domain == "liquidity":
        for m in ("current_ratio", "quick_ratio", "working_capital"):
            v = _get(ratios, "liquidity", m, "value")
            if v is not None:
                sm.append({"metric": m, "value": v})
    elif domain == "profitability":
        for m in ("net_margin_pct", "gross_margin_pct", "operating_margin_pct", "net_profit"):
            v = _get(ratios, "profitability", m, "value")
            if v is not None:
                sm.append({"metric": m, "value": v})
    elif domain == "efficiency":
        for m in ("dso_days", "dpo_days", "ccc_days", "inventory_turnover"):
            v = _get(ratios, "efficiency", m, "value")
            if v is not None:
                sm.append({"metric": m, "value": v})
    elif domain == "leverage":
        for m in ("debt_to_equity", "debt_ratio_pct"):
            v = _get(ratios, "leverage", m, "value")
            if v is not None:
                sm.append({"metric": m, "value": v})
    elif domain == "growth":
        ry = _get(trends, "revenue", "ytd_vs_prior")
        if ry is not None:
            sm.append({"metric": "revenue_ytd_vs_prior_pct", "value": ry})
    rd = _get(trends, "revenue", "direction")
    if rd and rd != "insufficient_data":
        sm.append({"metric": "revenue_trend_direction", "value": rd})
    nd = _get(trends, "net_profit", "direction")
    if nd and nd != "insufficient_data":
        sm.append({"metric": "net_profit_trend_direction", "value": nd})
    return sm


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
) -> dict:
    """
    Build top-N CFO-level prioritized decisions from Phase 21/23 intelligence.

    Args:
        intelligence: output of fin_intelligence.build_intelligence()
        alerts:       output of alerts_engine.build_alerts()["alerts"]
        lang:         "en" | "ar" | "tr"
        n_periods:    number of periods in the analysis window (affects confidence)
        top_n:        how many decisions to return (default 3)

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

    # ── Score every domain ─────────────────────────────────────────────────────
    domains = ["liquidity", "profitability", "efficiency", "leverage", "growth"]
    raw_scores: dict[str, int] = {}
    for d in domains:
        raw_scores[d] = _score_domain(d, ratios, trends, alerts, anomalies)

    # ── Apply domain weights — liquidity always first if score >= 30 ───────────
    liq_score = raw_scores["liquidity"]
    weighted: list[tuple[int, str]] = []
    for d in domains:
        s = raw_scores[d]
        w = DOMAIN_WEIGHTS.get(d, 10)
        # If liquidity is critical, boost it above everything else
        if d == "liquidity" and s >= 30:
            effective = s * (w / 35) * 1.4   # boost factor
        else:
            effective = s * (w / 100)
        weighted.append((effective, d))

    # Sort descending by effective priority
    weighted.sort(key=lambda x: -x[0])

    # ── Build decision cards for top domains ───────────────────────────────────
    decisions: list[dict] = []
    causal_items: list[dict] = []
    for eff_score, domain in weighted[:top_n]:
        selected = _select_decision(domain, ratios, trends, health, lang)
        if selected is None:
            continue
        card, template_params = selected
        raw = raw_scores[domain]
        card["priority"]        = len(decisions) + 1
        card["urgency"]         = _urgency(raw)
        card["impact_level"]    = _impact_level(domain, raw)
        card["timeframe"]       = _timeframe(raw)
        card["time_horizon"]    = card["timeframe"]
        card["confidence"]      = _confidence(raw, health, n_periods)
        card["priority_score"]  = round(eff_score, 1)
        # Phase 25 schema aliases
        card["reason"]          = card.pop("rationale", "")
        card["expected_effect"] = card.pop("impact", "")
        card["expected_impact"] = card["expected_effect"]
        card["action"]          = card.get("action", "")
        card["source_metrics"]  = _decision_source_metrics(domain, ratios, trends)
        card["decision_title"]  = card.get("title", "")
        card["linked_causes"]   = _linked_causes_for_domain(domain, alerts)
        card["evidence"]        = {
            "health_score_v2": health,
            "domain_urgency_score": raw,
            "source_metrics": card["source_metrics"],
            "linked_alerts": [x.get("alert_id") for x in card["linked_causes"]],
        }
        decisions.append(card)
        causal_items.append(_causal_item_for_decision(card, template_params))

    top_focus = decisions[0]["domain"] if decisions else ""

    top_domain = decisions[0]["domain"] if decisions else ""

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
        },
    }
