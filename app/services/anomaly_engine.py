"""
anomaly_engine.py — Phase 43
Anomaly detection layer (STRICT, high-signal only).

Interprets existing metrics and trends ONLY.
No financial recalculation. No engine modification.
Returns 0–3 anomalies in practice; conditions are strict by design.
"""
from __future__ import annotations


def detect_anomalies(
    metrics: dict,
    trends:  dict,
    lang:    str = "en",
) -> list:
    """
    Detect anomalous financial patterns from existing metric/trend snapshots.

    Args:
        metrics: latest-period KPI dict
        trends:  MoM % change dict
        lang:    "en" | "ar" | "tr"

    Returns:
        list of anomaly dicts, ordered high → medium, max ~3 in typical operation.
    """
    ar = lang == "ar"
    tr = lang == "tr"

    def _g(d: dict, *keys, default: float = 0.0) -> float:
        for k in keys:
            v = d.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
        return default

    nm       = _g(metrics, "net_margin_pct", "net_margin")
    exp_r    = _g(metrics, "total_cost_ratio_pct", "expense_ratio", "expense_ratio_pct")
    cogs_r   = _g(metrics, "cogs_ratio",     "cogs_ratio_pct")

    rev_mom  = _g(trends, "revenue_mom",       "revenue_mom_pct")
    np_mom   = _g(trends, "net_profit_mom",    "net_profit_mom_pct")
    exp_mom  = _g(trends, "opex_mom_pct", "expense_ratio_mom", "expense_ratio_mom_pct")
    cogs_mom = _g(trends, "cogs_ratio_mom",    "cogs_ratio_mom_pct")

    results: list[dict] = []

    # ── 1. cost_anomaly ───────────────────────────────────────────────────────
    # Strict: COGS ratio rising ≥5pp MoM AND outpacing revenue growth
    if cogs_mom >= 5.0 and cogs_mom > rev_mom:
        gap = round(cogs_mom - rev_mom, 1)

        if ar:
            what = (f"تكلفة البضاعة ارتفعت {cogs_mom:.1f}٪ شهرياً — "
                    f"أعلى من نمو الإيرادات البالغ {rev_mom:.1f}٪ بفارق {gap:.1f} نقطة.")
            matter = ("حين تتجاوز التكاليف الإيرادات بهذا الهامش، يتآكل هامش الربح الإجمالي بسرعة "
                      "وتزداد حدة تأثير أي تباطؤ في المبيعات على الربحية.")
            todo = ("مراجعة فورية لعقود الموردين وهيكل تكلفة البضاعة؛ تحديد ما إذا كان الارتفاع "
                    "ناتجاً عن تغيّر في المزيج أو ارتفاع في أسعار المدخلات أو ضعف في التسعير.")
        elif tr:
            what = (f"SMM aylık {cogs_mom:.1f}% artarak gelir büyümesini ({rev_mom:.1f}%) "
                    f"{gap:.1f} puanla geride bıraktı.")
            matter = ("Maliyetler bu farkla geliri aştığında brüt marj hızla erir ve herhangi bir "
                      "satış yavaşlaması kârlılık üzerinde orantısız büyük bir baskı oluşturur.")
            todo = ("Tedarikçi sözleşmelerini ve SMM yapısını acil gözden geçirin; artışın ürün "
                    "karışımı değişikliğinden mi, girdi fiyatlarından mı yoksa fiyatlandırma "
                    "zayıflığından mı kaynaklandığını belirleyin.")
        else:
            what = (f"COGS rose {cogs_mom:.1f}% MoM — outpacing revenue growth of {rev_mom:.1f}% "
                    f"by {gap:.1f}pp.")
            matter = ("When costs outpace revenue by this margin, gross margin erodes rapidly and any "
                      "Revenue slowdown has a disproportionate impact on profitability.")
            todo = ("Immediate review of supplier contracts and COGS structure. Determine whether the "
                    "spike is driven by product mix shift, input price increases, or pricing weakness.")

        results.append({
            "type":           "cost_anomaly",
            "severity":       "high",
            "what_happened":  what,
            "why_it_matters": matter,
            "what_to_do":     todo,
            "confidence":     "high",
            "source_metrics": {
                "cogs_ratio_mom_pct": cogs_mom,
                "revenue_mom_pct":    rev_mom,
                "gap_pp":             gap,
                "cogs_ratio_pct":     cogs_r,
            },
        })

    # ── 2. margin_anomaly ─────────────────────────────────────────────────────
    # Strict: margin below 10% AND profit shrinking month-on-month
    if nm < 10.0 and np_mom < 0.0:
        if ar:
            what = (f"هامش الربح الصافي {nm:.1f}٪ — دون عتبة 10٪ — مع تراجع إضافي "
                    f"في الأرباح بنسبة {abs(np_mom):.1f}٪ شهرياً.")
            matter = ("الجمع بين ضعف الهامش واستمرار التراجع في الأرباح يُنذر بخطر الدخول في "
                      "منطقة الخسارة التشغيلية إذا لم تُعالَج الأسباب الجذرية في أقرب وقت.")
            todo = ("تشخيص فوري لمكونات الهامش: مراجعة التسعير، فحص ضغط التكاليف المتغيرة، "
                    "وتقييم الطاقة الإنتاجية المستغلة قبل الموافقة على أي توسع في المصروفات.")
        elif tr:
            what = (f"Net kâr marjı {nm:.1f}% — %10 eşiğinin altında — ve kâr aylık "
                    f"{abs(np_mom):.1f}% daha düşüyor.")
            matter = ("Düşük marj ile devam eden kâr düşüşünün bir araya gelmesi, temel nedenler "
                      "hızla ele alınmazsa işletmenin zarar bölgesine girebileceğine işaret eder.")
            todo = ("Marj bileşenlerini acil tanılayın: fiyatlandırmayı gözden geçirin, değişken "
                    "maliyet baskısını denetleyin ve herhangi bir gider genişlemesini onaylamadan "
                    "önce kullanılan kapasiteyi değerlendirin.")
        else:
            what = (f"Net margin at {nm:.1f}% — below the 10% floor — with profit declining "
                    f"a further {abs(np_mom):.1f}% MoM.")
            matter = ("Low margin combined with continuing profit contraction signals risk of entering "
                      "operating-loss territory if root causes are not addressed promptly.")
            todo = ("Immediate margin diagnosis: review pricing, audit variable cost pressure, and "
                    "assess capacity utilisation before approving any further expense commitments.")

        results.append({
            "type":           "margin_anomaly",
            "severity":       "high" if nm < 5 else "medium",
            "what_happened":  what,
            "why_it_matters": matter,
            "what_to_do":     todo,
            "confidence":     "high",
            "source_metrics": {
                "net_margin_pct":     nm,
                "net_profit_mom_pct": np_mom,
            },
        })

    # ── 3. expense_outlier ────────────────────────────────────────────────────
    # Strict: expense ratio exceeds 60% — structural threshold
    if exp_r > 60.0:
        sev = "high" if exp_r > 75 else "medium"

        if ar:
            what = f"نسبة المصروفات التشغيلية بلغت {exp_r:.1f}٪ من الإيرادات — تتجاوز حد 60٪."
            matter = ("نسبة تتخطى 60٪ تُشير إلى ضعف هيكلي في التكاليف؛ الهوامش المتاحة لامتصاص "
                      "أي صدمة في الإيرادات أو الطاقة الاستثمارية تصبح ضيقة للغاية.")
            todo = ("مراجعة شاملة للبنود الثابتة والمتغيرة في المصروفات؛ إعداد جدول زمني لتخفيض "
                    "النسبة إلى دون 55٪ عبر التفاوض على العقود أو إعادة هيكلة الخدمات.")
        elif tr:
            what = f"Faaliyet giderleri gelirin {exp_r:.1f}%'ine ulaştı — %60 eşiğini aştı."
            matter = ("Yüzde altmışı aşan bir oran yapısal maliyet zayıflığına işaret eder; "
                      "herhangi bir gelir şokunu veya yatırım kapasitesini karşılamak için "
                      "çok az marj kalır.")
            todo = ("Sabit ve değişken gider kalemlerinin kapsamlı incelemesi; sözleşme "
                    "müzakereleri veya hizmet yeniden yapılandırması yoluyla oranı %55 altına "
                    "indirmek için zaman çizelgesi hazırlayın.")
        else:
            what = f"Operating expense ratio reached {exp_r:.1f}% of revenue — exceeding the 60% threshold."
            matter = ("A ratio above 60% signals structural cost weakness. Very little margin remains "
                      "to absorb any revenue shock or fund capacity investment.")
            todo = ("Comprehensive audit of fixed and variable expense lines. Set a timeline to bring "
                    "the ratio below 55% through contract renegotiation or service restructuring.")

        results.append({
            "type":           "expense_outlier",
            "severity":       sev,
            "what_happened":  what,
            "why_it_matters": matter,
            "what_to_do":     todo,
            "confidence":     "high",
            "source_metrics": {
                "expense_ratio_pct":     exp_r,
                "expense_ratio_mom_pct": exp_mom,
            },
        })

    # ── 4. revenue_drop ───────────────────────────────────────────────────────
    # Strict: revenue contracted 5% or more MoM
    if rev_mom <= -5.0:
        sev = "high" if rev_mom <= -10 else "medium"

        if ar:
            what = f"الإيرادات تراجعت {abs(rev_mom):.1f}٪ مقارنةً بالشهر الماضي."
            matter = ("انخفاض بهذا المعدل يُحدث ضغطاً فورياً على التدفق النقدي التشغيلي ويُضعف "
                      "القدرة على تغطية التكاليف الثابتة، خاصة إذا لم تنخفض المصروفات بنفس النسبة.")
            todo = ("تحليل مصادر الانخفاض: هل يرتبط بعميل بعينه؟ بموسمية؟ بانكماش في حصة السوق؟ "
                    "تفعيل خطة الاستجابة السريعة قبل انتقال الأثر إلى دورة الشهر التالي.")
        elif tr:
            what = f"Gelir geçen aya kıyasla {abs(rev_mom):.1f}% geriledi."
            matter = ("Bu oran düşüşü, faaliyet nakit akışı üzerinde anlık baskı oluşturur ve "
                      "giderler eş oranda düşmezse sabit maliyetleri karşılama kapasitesini zayıflatır.")
            todo = ("Düşüşün kaynağını analiz edin: belirli bir müşteriye mi, mevsimselliğe mi, "
                    "yoksa pazar payı kaybına mı bağlı? Etki bir sonraki aya yansımadan hızlı "
                    "müdahale planını etkinleştirin.")
        else:
            what = f"Revenue contracted {abs(rev_mom):.1f}% compared to the prior month."
            matter = ("A drop of this magnitude creates immediate pressure on operating cash flow and "
                      "weakens the ability to cover fixed costs, especially if expenses do not "
                      "decrease proportionally.")
            todo = ("Identify the source of the decline: client-specific, seasonal, or market share "
                    "erosion. Activate a rapid-response plan before the impact cascades into the "
                    "next billing cycle.")

        results.append({
            "type":           "revenue_drop",
            "severity":       sev,
            "what_happened":  what,
            "why_it_matters": matter,
            "what_to_do":     todo,
            "confidence":     "high",
            "source_metrics": {
                "revenue_mom_pct": rev_mom,
            },
        })

    # Sort: high first, then medium
    _rank = {"high": 0, "medium": 1}
    results.sort(key=lambda r: _rank.get(r["severity"], 2))
    return results
