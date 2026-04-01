"""
alerts_engine.py — Phase 23
Converts Phase 21 intelligence outputs into prioritized management alerts.

Input:  outputs from fin_intelligence.build_intelligence()
Output: { alerts: [...top 5], summary: {high, medium, low} }

Design rules:
  - Pure function — no DB, no HTTP
  - Reads from existing intelligence output (no re-computation)
  - Max 5 alerts (most critical first)
  - No duplicate alerts on same root cause
  - All message text via _ALERT_TEXT i18n table (EN/AR)
  - Confidence derived from data quality + severity signal strength
"""
from __future__ import annotations
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
#  Embedded alert text (EN / AR)
# ──────────────────────────────────────────────────────────────────────────────

_T: dict[str, dict] = {
    # ── Profitability ─────────────────────────────────────────────────────────
    "net_margin_low": {
        "en": {"title": "Low Net Margin",
               "message": "Net margin is {val}% — below the 5% healthy threshold.",
               "action": "Review Cost of Goods Sold and Operating Expenses for reduction opportunities."},
        "ar": {"title": "هامش صافٍ منخفض",
               "message": "الهامش الصافي {val}% — أقل من الحد الصحي 5%.",
               "action": "راجع تكلفة المبيعات والمصاريف التشغيلية لتحديد فرص التخفيض."},
        "tr": {"title": "Düşük Net Marj",
               "message": "Net marj %{val} — sağlıklı eşik olan %5'in altında.",
               "action": "Maliyet ve giderleri gözden geçirin."},
    },
    "net_margin_drop": {
        "en": {"title": "Net Margin Declining",
               "message": "Net margin trending downward over recent periods.",
               "action": "Investigate cost structure — rising COGS or OpEx may be compressing margins."},
        "ar": {"title": "تراجع الهامش الصافي",
               "message": "الهامش الصافي في اتجاه هبوطي خلال الفترات الأخيرة.",
               "action": "افحص هيكل التكاليف — ارتفاع تكلفة المبيعات أو المصاريف قد يضغط على الهوامش."},
        "tr": {"title": "Düşen Net Marj",
               "message": "Net marj son dönemlerde düşüş eğiliminde.",
               "action": "Maliyet yapısını inceleyin."},
    },
    "gross_margin_low": {
        "en": {"title": "Weak Gross Margin",
               "message": "Gross margin is {val}% — below 25% indicates cost pressure.",
               "action": "Evaluate pricing strategy and Cost of Goods Sold efficiency."},
        "ar": {"title": "هامش إجمالي ضعيف",
               "message": "هامش الربح الإجمالي {val}% — أقل من 25% يُشير إلى ضغط على التكاليف.",
               "action": "قيّم استراتيجية التسعير وكفاءة تكلفة المبيعات."},
        "tr": {"title": "Zayıf Brüt Marj",
               "message": "Brüt marj %{val} — maliyet baskısı göstergesi.",
               "action": "Fiyatlandırma stratejisini değerlendirin."},
    },
    # ── Liquidity ──────────────────────────────────────────────────────────────
    "current_ratio_low": {
        "en": {"title": "Liquidity Risk",
               "message": "Current ratio is {val}x — below 1.0 means current liabilities exceed current assets.",
               "action": "Accelerate receivables collection and review short-term debt obligations."},
        "ar": {"title": "خطر السيولة",
               "message": "نسبة التداول {val} — أقل من 1 تعني أن الالتزامات قصيرة الأجل تتجاوز الأصول المتداولة.",
               "action": "سرّع تحصيل المستحقات وراجع الالتزامات قصيرة الأجل."},
        "tr": {"title": "Likidite Riski",
               "message": "Cari oran {val}x — 1.0'ın altında kısa vadeli yükümlülükler varlıkları aşıyor.",
               "action": "Alacak tahsilatını hızlandırın."},
    },
    "working_capital_negative": {
        "en": {"title": "Negative Working Capital",
               "message": "Working capital is negative — the business may struggle to meet short-term obligations.",
               "action": "Review cash position and consider short-term financing or asset liquidation."},
        "ar": {"title": "رأس المال العامل سالب",
               "message": "رأس المال العامل سالب — قد تواجه الشركة صعوبة في تلبية الالتزامات قصيرة الأجل.",
               "action": "راجع الوضع النقدي وفكّر في التمويل قصير الأجل أو تسييل الأصول."},
        "tr": {"title": "Negatif İşletme Sermayesi",
               "message": "İşletme sermayesi negatif — kısa vadeli yükümlülükleri karşılamak zorlaşabilir.",
               "action": "Nakit pozisyonunu gözden geçirin."},
    },
    # ── Revenue ────────────────────────────────────────────────────────────────
    "revenue_declining": {
        "en": {"title": "Revenue Decline",
               "message": "Revenue is in a sustained downward trend.",
               "action": "Investigate Revenue Drivers, pricing, and customer retention."},
        "ar": {"title": "تراجع الإيرادات",
               "message": "الإيرادات في اتجاه هبوطي مستمر.",
               "action": "افحص محركات الإيرادات والتسعير والاحتفاظ بالعملاء."},
        "tr": {"title": "Gelir Düşüşü",
               "message": "Gelir sürekli düşüş eğiliminde.",
               "action": "Gelir sürücülerini, fiyatlandırmayı ve müşteri tutmayı inceleyin."},
    },
    "revenue_ytd_behind": {
        "en": {"title": "YTD Revenue Below Prior Year",
               "message": "YTD revenue is {val}% behind the same period last year.",
               "action": "Review Revenue performance versus plan and prior year targets."},
        "ar": {"title": "إيرادات YTD دون العام السابق",
               "message": "إيرادات منذ بداية العام أقل بنسبة {val}% مقارنة بنفس الفترة من العام الماضي.",
               "action": "راجع أداء الإيرادات مقابل الخطة وأهداف العام السابق."},
        "tr": {"title": "YBD Geliri Geçen Yılın Altında",
               "message": "YBD geliri geçen yılın aynı dönemine göre %{val} geride.",
               "action": "Gelir performansını hedeflerle karşılaştırın."},
    },
    # ── Efficiency ─────────────────────────────────────────────────────────────
    "dso_high": {
        "en": {"title": "High Days Sales Outstanding",
               "message": "DSO is {val} days — customers are taking too long to pay.",
               "action": "Tighten credit terms and accelerate invoicing and collection processes."},
        "ar": {"title": "أيام القبض مرتفعة",
               "message": "أيام القبض {val} يوم — العملاء يتأخرون في السداد.",
               "action": "شدّد شروط الائتمان وسرّع عمليات الفوترة والتحصيل."},
        "tr": {"title": "Yüksek Tahsilat Süresi",
               "message": "DSO {val} gün — müşteriler geç ödüyor.",
               "action": "Kredi koşullarını sıkılaştırın ve tahsilatı hızlandırın."},
    },
    "ccc_high": {
        "en": {"title": "Cash Conversion Cycle Too Long",
               "message": "CCC is {val} days — capital is tied up for too long in operations.",
               "action": "Reduce inventory levels, accelerate collections, and negotiate longer supplier terms."},
        "ar": {"title": "دورة النقد طويلة جداً",
               "message": "دورة النقد {val} يوم — رأس المال محتجز في العمليات لفترة طويلة.",
               "action": "قلّل مستويات المخزون وسرّع التحصيل وتفاوض على شروط موردين أطول."},
        "tr": {"title": "Uzun Nakit Döngüsü",
               "message": "CCC {val} gün — sermaye işlemlerde çok uzun süre bekliyor.",
               "action": "Stok seviyelerini azaltın ve tahsilatı hızlandırın."},
    },
    # ── Leverage ───────────────────────────────────────────────────────────────
    "debt_high": {
        "en": {"title": "High Leverage",
               "message": "Debt-to-equity is {val}x — the business is significantly leveraged.",
               "action": "Review debt repayment schedule and consider deleveraging strategy."},
        "ar": {"title": "رفع مالي مرتفع",
               "message": "نسبة الدين إلى حقوق الملكية {val} — الشركة مُموَّلة بديون عالية نسبياً.",
               "action": "راجع جدول سداد الديون وفكّر في استراتيجية تخفيض الديون."},
        "tr": {"title": "Yüksek Kaldıraç",
               "message": "Borç/özkaynaklar {val}x — işletme önemli ölçüde kaldıraçlı.",
               "action": "Borç ödeme planını gözden geçirin."},
    },
    # ── Anomaly ────────────────────────────────────────────────────────────────
    "anomaly_revenue_drop": {
        "en": {"title": "Unusual Revenue Drop Detected",
               "message": "An anomalous revenue drop of {val}% was detected in {period}.",
               "action": "Investigate root cause — potential lost client, pricing issue, or seasonal factor."},
        "ar": {"title": "انخفاض غير اعتيادي في الإيرادات",
               "message": "رُصد انخفاض غير اعتيادي بنسبة {val}% في الإيرادات خلال {period}.",
               "action": "افحص السبب الجذري — عميل مفقود محتمل أو مشكلة تسعير أو عامل موسمي."},
        "tr": {"title": "Olağandışı Gelir Düşüşü",
               "message": "{period} döneminde %{val} olağandışı gelir düşüşü tespit edildi.",
               "action": "Kök nedeni araştırın."},
    },
    "anomaly_profit_collapse": {
        "en": {"title": "Sharp Net Profit Decline",
               "message": "Net profit dropped {val}% in {period} — an unusual swing.",
               "action": "Analyse cost spikes or one-off charges in the affected period."},
        "ar": {"title": "تراجع حاد في صافي الربح",
               "message": "تراجع صافي الربح بنسبة {val}% في {period} — تأرجح غير اعتيادي.",
               "action": "حلّل ارتفاعات التكاليف أو الرسوم الاستثنائية في الفترة المتأثرة."},
        "tr": {"title": "Keskin Net Kar Düşüşü",
               "message": "{period}'de net kar %{val} düştü.",
               "action": "Maliyet artışlarını veya tek seferlik giderleri analiz edin."},
    },
    # ── Health ────────────────────────────────────────────────────────────────
    "health_low": {
        "en": {"title": "Low Financial Health Score",
               "message": "Overall financial health score is {val}/100 — requires management attention.",
               "action": "Review top financial risks and prioritize corrective actions across profitability and liquidity."},
        "ar": {"title": "مؤشر صحة مالية منخفض",
               "message": "مؤشر الصحة المالية الإجمالي {val}/100 — يستدعي اهتمام الإدارة.",
               "action": "راجع أبرز المخاطر المالية وحدّد الإجراءات التصحيحية للربحية والسيولة."},
        "tr": {"title": "Düşük Finansal Sağlık Skoru",
               "message": "Genel finansal sağlık skoru {val}/100 — yönetim dikkatini gerektiriyor.",
               "action": "Başlıca finansal riskleri gözden geçirin."},
    },
}


def _txt(key: str, lang: str, **kw) -> dict:
    """Fetch localized alert text and format placeholders."""
    entry = _T.get(key, {})
    loc   = entry.get(lang) or entry.get("en") or {}
    def _f(s: str) -> str:
        try:    return s.format(**kw)
        except: return s
    return {
        "title":   _f(loc.get("title",   key)),
        "message": _f(loc.get("message", "")),
        "action":  _f(loc.get("action",  "")),
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Alert builders
# ──────────────────────────────────────────────────────────────────────────────

SEV_RANK = {"high": 3, "medium": 2, "low": 1}


def _alert(id_: str, severity: str, impact: str, confidence: int,
           title: str, message: str, action: str) -> dict:
    return {
        "id":         id_,
        "title":      title,
        "severity":   severity,
        "impact":     impact,
        "message":    message,
        "action":     action,
        "confidence": min(100, max(0, confidence)),
    }


def _from_ratios(ratios: dict, lang: str) -> list[dict]:
    alerts = []

    def _val(cat, key):
        return (ratios.get(cat, {}).get(key, {}) or {}).get("value")

    def _st(cat, key):
        return (ratios.get(cat, {}).get(key, {}) or {}).get("status", "neutral")

    # Net margin
    nm = _val("profitability", "net_margin_pct")
    nm_st = _st("profitability", "net_margin_pct")
    if nm_st == "risk" or (nm is not None and nm < 0):
        t = _txt("net_margin_low", lang, val=round(nm or 0, 1))
        alerts.append(_alert("net_margin_low", "high", "profitability", 88, **t))
    elif nm_st == "warning":
        t = _txt("net_margin_low", lang, val=round(nm or 0, 1))
        alerts.append(_alert("net_margin_low", "medium", "profitability", 75, **t))

    # Gross margin
    gm = _val("profitability", "gross_margin_pct")
    if gm is not None and gm < 25 and _st("profitability", "gross_margin_pct") in ("warning","risk"):
        t = _txt("gross_margin_low", lang, val=round(gm, 1))
        sev = "high" if gm < 15 else "medium"
        alerts.append(_alert("gross_margin_low", sev, "profitability", 82, **t))

    # Current ratio
    cr = _val("liquidity", "current_ratio")
    cr_st = _st("liquidity", "current_ratio")
    if cr is not None and cr_st in ("warning", "risk"):
        t = _txt("current_ratio_low", lang, val=round(cr, 2))
        sev = "high" if cr < 1.0 else "medium"
        alerts.append(_alert("current_ratio_low", sev, "liquidity", 85, **t))

    # Working capital
    wc = _val("liquidity", "working_capital")
    if wc is not None and wc < 0:
        t = _txt("working_capital_negative", lang)
        alerts.append(_alert("working_capital_negative", "high", "liquidity", 90, **t))

    # DSO
    dso = _val("efficiency", "dso_days")
    if dso is not None and _st("efficiency", "dso_days") in ("warning","risk"):
        t = _txt("dso_high", lang, val=round(dso))
        sev = "high" if dso > 75 else "medium"
        alerts.append(_alert("dso_high", sev, "operational", 78, **t))

    # CCC
    ccc = _val("efficiency", "ccc_days")
    if ccc is not None and _st("efficiency", "ccc_days") in ("warning","risk"):
        t = _txt("ccc_high", lang, val=round(ccc))
        sev = "high" if ccc > 90 else "medium"
        alerts.append(_alert("ccc_high", sev, "operational", 74, **t))

    # Debt-to-equity
    de = _val("leverage", "debt_to_equity")
    if de is not None and _st("leverage", "debt_to_equity") in ("warning","risk"):
        t = _txt("debt_high", lang, val=round(de, 1))
        sev = "high" if de > 3.0 else "medium"
        alerts.append(_alert("debt_high", sev, "cost", 70, **t))

    return alerts


def _from_trends(trends: dict, lang: str) -> list[dict]:
    alerts = []

    rev_t   = trends.get("revenue",    {})
    np_t    = trends.get("net_profit", {})
    gm_t    = trends.get("gross_margin", {})

    # Revenue declining
    if rev_t.get("direction") == "down":
        t = _txt("revenue_declining", lang)
        alerts.append(_alert("revenue_declining", "high", "profitability", 80, **t))

    # Revenue YTD behind prior year
    ytd_rev = rev_t.get("ytd_vs_prior")
    if ytd_rev is not None and ytd_rev < -5:
        t = _txt("revenue_ytd_behind", lang, val=abs(round(ytd_rev, 1)))
        sev = "high" if ytd_rev < -15 else "medium"
        alerts.append(_alert("revenue_ytd_behind", sev, "profitability", 85, **t))

    # Net margin declining
    if np_t.get("direction") == "down" and gm_t.get("direction") == "down":
        t = _txt("net_margin_drop", lang)
        alerts.append(_alert("net_margin_drop", "medium", "profitability", 72, **t))

    return alerts


def _from_anomalies(anomalies: list, lang: str) -> list[dict]:
    alerts = []
    for a in anomalies:
        metric = a.get("metric", "")
        period = a.get("period", "")
        chg    = a.get("change_pct")
        sev    = a.get("severity", "medium")

        if metric == "revenue" and chg is not None and chg < 0:
            t = _txt("anomaly_revenue_drop", lang,
                     val=abs(round(chg, 1)), period=period)
            conf = 88 if sev == "critical" else 75
            alerts.append(_alert(f"anomaly_revenue_{period}", sev if sev in SEV_RANK else "medium",
                                  "profitability", conf, **t))

        elif metric == "net_profit" and chg is not None and chg < -30:
            t = _txt("anomaly_profit_collapse", lang,
                     val=abs(round(chg, 1)), period=period)
            conf = 85 if sev == "critical" else 72
            alerts.append(_alert(f"anomaly_profit_{period}", sev if sev in SEV_RANK else "medium",
                                  "profitability", conf, **t))

    return alerts


def _from_health(score: int, lang: str) -> list[dict]:
    if score >= 50:
        return []
    t = _txt("health_low", lang, val=score)
    sev = "high" if score < 35 else "medium"
    return [_alert("health_low", sev, "profitability", 80, **t)]


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_alerts(
    intelligence: dict,
    lang:         str = "en",
    max_alerts:   int = 5,
) -> dict:
    """
    Generate prioritized management alerts from Phase 21 intelligence output.

    Args:
        intelligence: output of fin_intelligence.build_intelligence()
        lang:         "en" | "ar" | "tr"
        max_alerts:   cap on number of alerts returned (default 5)

    Returns:
        { alerts: [...], summary: {high, medium, low} }
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"

    ratios    = intelligence.get("ratios",    {})
    trends    = intelligence.get("trends",    {})
    anomalies = intelligence.get("anomalies", [])
    score     = intelligence.get("health_score_v2", 100)

    raw: list[dict] = []
    raw += _from_anomalies(anomalies, lang)   # highest priority — detected events
    raw += _from_ratios(ratios,       lang)   # structural weaknesses
    raw += _from_trends(trends,       lang)   # directional issues
    raw += _from_health(score,        lang)   # overall score

    # Deduplicate by id (keep highest severity if same id)
    seen: dict[str, dict] = {}
    for a in raw:
        aid = a["id"]
        if aid not in seen or SEV_RANK.get(a["severity"], 0) > SEV_RANK.get(seen[aid]["severity"], 0):
            seen[aid] = a

    # Sort: severity desc, then confidence desc
    ranked = sorted(
        seen.values(),
        key=lambda a: (SEV_RANK.get(a["severity"], 0), a["confidence"]),
        reverse=True,
    )

    top = ranked[:max_alerts]

    summary = {
        "high":   sum(1 for a in top if a["severity"] == "high"),
        "medium": sum(1 for a in top if a["severity"] == "medium"),
        "low":    sum(1 for a in top if a["severity"] == "low"),
        "total":  len(top),
    }

    return {"alerts": top, "summary": summary}
