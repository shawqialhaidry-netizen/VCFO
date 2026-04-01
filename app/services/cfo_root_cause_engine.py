"""
cfo_root_cause_engine.py — Phase 26
CFO Root Cause Analysis Engine.

Explains WHY each CFO decision is needed by tracing financial indicators
back to their underlying causes. Linked to Phase 25 decisions.

Design principles:
  - Every cause references a SPECIFIC METRIC with its ACTUAL VALUE
  - Causes explain WHY (mechanism), not WHAT (symptom)
  - Each cause is linked to one or more Phase 25 decisions
  - Grouped by domain for clear navigation
  - No generic filler text — all descriptions use real data points
  - Fully localized EN / AR / TR
  - Pure function — no DB, no HTTP
"""
from __future__ import annotations
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get(d: dict, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d


def _v(ratios: dict, category: str, metric: str) -> Optional[float]:
    """Extract a ratio value."""
    return _get(ratios, category, metric, "value")


def _st(ratios: dict, category: str, metric: str) -> str:
    """Extract a ratio status."""
    return _get(ratios, category, metric, "status") or "neutral"


def _fmt(v, spec=".1f", fallback="—") -> str:
    try:
        return format(float(v), spec) if v is not None else fallback
    except (TypeError, ValueError):
        return fallback


def _fmtK(v) -> str:
    try:
        a = abs(float(v))
        s = "-" if float(v) < 0 else ""
        if a >= 1_000_000: return f"{s}{a/1_000_000:.1f}M"
        if a >= 1_000:     return f"{s}{a/1_000:.0f}K"
        return f"{s}{a:.0f}"
    except (TypeError, ValueError):
        return "—"


# ──────────────────────────────────────────────────────────────────────────────
#  Embedded localized cause text
# ──────────────────────────────────────────────────────────────────────────────

_CT: dict[str, dict] = {

    # ── Liquidity causes ──────────────────────────────────────────────────────
    "liq_cr_weak": {
        "en": {
            "title": "Current Ratio Below Safe Threshold",
            "description": "The current ratio of {cr}x means for every {cr} in current assets the company owes {cl_ratio} in current liabilities due within 12 months. Below 1.0x signals the company cannot cover short-term obligations from liquid assets alone — it depends on future cash inflows or credit.",
            "mechanism": "When current assets < current liabilities, the business must generate incoming cash (collections, sales) fast enough to service each payment cycle. If collections slow or a major customer delays, a payment gap opens.",
        },
        "ar": {
            "title": "نسبة التداول أقل من الحد الآمن",
            "description": "نسبة التداول {cr} تعني أنه مقابل كل {cr} في الأصول المتداولة، تدين الشركة بـ {cl_ratio} في الالتزامات المتداولة المستحقة خلال 12 شهراً. أقل من 1.0 يشير إلى عدم قدرة الشركة على تغطية الالتزامات قصيرة الأجل من الأصول السائلة وحدها.",
            "mechanism": "عندما تكون الأصول المتداولة أقل من الالتزامات المتداولة، يجب على الشركة توليد نقد وارد بسرعة كافية لخدمة كل دورة دفع.",
        },
        "tr": {
            "title": "Cari Oran Güvenli Eşiğin Altında",
            "description": "Cari oran {cr}x, her {cr} dönen varlık karşılığında 12 ay içinde vadesi gelecek {cl_ratio} kısa vadeli yükümlülük olduğu anlamına geliyor.",
            "mechanism": "Dönen varlıklar kısa vadeli yükümlülüklerden az olduğunda, işletme her ödeme döngüsünü karşılamak için yeterince hızlı nakit üretmek zorunda.",
        },
    },

    "liq_wc_negative": {
        "en": {
            "title": "Negative Working Capital Creates Structural Cash Gap",
            "description": "Working capital of {wc} means the business is funding day-to-day operations using money it owes to creditors. The structural gap of {wc_abs} must be continuously refinanced — any interruption in supplier credit or bank lines creates immediate payment failure.",
            "mechanism": "Negative working capital is not inherently fatal in businesses with fast cash cycles, but when receivables DSO is {dso} days and supplier payment terms are shorter, it creates a chronic cash deficit that must be continuously bridged.",
        },
        "ar": {
            "title": "رأس المال العامل السالب يخلق فجوة نقدية هيكلية",
            "description": "رأس مال عامل بقيمة {wc} يعني أن الشركة تمول عملياتها اليومية باستخدام أموال مستحقة للدائنين. الفجوة الهيكلية البالغة {wc_abs} يجب إعادة تمويلها باستمرار.",
            "mechanism": "رأس المال العامل السالب ليس قاتلاً بطبيعته في الأعمال ذات دورات النقد السريعة، لكن عندما تكون أيام القبض {dso} يوماً وشروط الدفع للموردين أقصر، يخلق عجزاً نقدياً مزمناً يجب تمويله باستمرار.",
        },
        "tr": {
            "title": "Negatif İşletme Sermayesi Yapısal Nakit Açığı Yaratıyor",
            "description": "İşletme sermayesi {wc}, işletmenin günlük operasyonlarını alacaklılara borçlu olduğu parayla finanse ettiği anlamına geliyor. {wc_abs}'lık yapısal açık sürekli yeniden finanse edilmeli.",
            "mechanism": "Negatif işletme sermayesi, hızlı nakit döngüsü olan işletmelerde ölümcül değil, ancak alacak DSO {dso} gün iken tedarikçi ödeme koşulları daha kısa olduğunda kronik bir nakit açığı yaratıyor.",
        },
    },

    "liq_slow_collections": {
        "en": {
            "title": "Slow Receivables Collection Drains Liquidity",
            "description": "DSO of {dso} days means cash earned from {period_label} services is not collected until {dso} days later. With current liabilities due on shorter cycles, the mismatch directly compresses available cash.",
            "mechanism": "Every extra day of DSO delays cash by approximately {daily_rev} per day (estimated from operating revenue). At {dso} days, the business is effectively lending {total_locked} to customers interest-free.",
        },
        "ar": {
            "title": "بطء تحصيل المستحقات يستنزف السيولة",
            "description": "أيام القبض {dso} يوم تعني أن النقد المكتسب من خدمات {period_label} لا يُحصَّل حتى {dso} يوم لاحقاً. مع استحقاق الالتزامات المتداولة في دورات أقصر، يضغط هذا التفاوت مباشرةً على النقد المتاح.",
            "mechanism": "كل يوم إضافي من أيام القبض يؤخر النقد بمقدار {daily_rev} يومياً تقريباً. عند {dso} يوم، الشركة تُقرض فعلياً {total_locked} للعملاء دون فائدة.",
        },
        "tr": {
            "title": "Yavaş Alacak Tahsilatı Likiditeyi Etkiliyor",
            "description": "DSO {dso} gün, {period_label} hizmetlerinden kazanılan nakdin {dso} gün sonraya kadar tahsil edilmediği anlamına geliyor.",
            "mechanism": "Her ek DSO günü nakdi yaklaşık {daily_rev} geciktiriyor. {dso} günde işletme {total_locked}'yi müşterilere faizsiz borç veriyor.",
        },
    },

    # ── Profitability causes ───────────────────────────────────────────────────
    "prof_nm_compression": {
        "en": {
            "title": "Net Margin Compressed by Cost Structure",
            "description": "Net margin of {nm}% means {nm_cents} cents of every revenue currency unit reaches the bottom line. The gap between gross margin ({gm}%) and net margin ({nm}%) is {gap}pp — absorbed by operating expenses and financing costs.",
            "mechanism": "In operational businesses, direct service costs determine gross margin. If gross margin is stable but net margin falls, the compression is in overhead: admin costs, depreciation, interest expense, or one-off charges expanding faster than revenue.",
        },
        "ar": {
            "title": "ضغط الهامش الصافي بسبب هيكل التكاليف",
            "description": "الهامش الصافي {nm}% يعني أن {nm_cents} قرش من كل وحدة إيراد تصل إلى صافي الأرباح. الفجوة بين هامش الربح الإجمالي ({gm}%) والهامش الصافي ({nm}%) هي {gap} نقطة مئوية — تستهلكها المصاريف التشغيلية وتكاليف التمويل.",
            "mechanism": "في الشركات التشغيلية، التكاليف المباشرة لتقديم الخدمة تحدد هامش الربح الإجمالي. إذا كان الهامش الإجمالي مستقراً لكن الهامش الصافي ينخفض، فالضغط موجود في الأعباء العامة: تكاليف الإدارة، الإهلاك، مصاريف الفائدة، أو التكاليف الاستثنائية.",
        },
        "tr": {
            "title": "Net Marj Maliyet Yapısı Tarafından Sıkıştırılıyor",
            "description": "Net marj %{nm}, her gelir biriminin {nm_cents} kuruşunun son satıra ulaştığı anlamına geliyor. Brüt marj (%{gm}) ile net marj (%{nm}) arasındaki {gap} pp'lik fark faaliyet giderleri ve finansman maliyetleri tarafından emiliyor.",
            "mechanism": "Operasyonel işletmelerde doğrudan hizmet maliyetleri brüt marjı belirler. Brüt marj stabil ama net marj düşüyorsa, baskı genel giderlerdedir: yönetim maliyetleri, amortisman, faiz giderleri.",
        },
    },

    "prof_gm_pressure": {
        "en": {
            "title": "Gross Margin Under Cost-Side Pressure",
            "description": "Gross margin of {gm}% is approaching warning territory. For service and operational businesses, healthy gross margin typically ranges from 35–55% depending on business model. At {gm}%, the cost of delivering the service is consuming {cogs_pct}% of revenue, leaving limited room for overhead and profit.",
            "mechanism": "Gross margin deterioration in operational businesses usually traces to: (1) input cost increases (materials, energy, subcontractors) not passed through to pricing, (2) delivery or service inefficiency — output per resource unit declining, (3) supplier cost increases not offset by productivity gains, or (4) labour cost inflation without a corresponding increase in output per employee.",
        },
        "ar": {
            "title": "هامش الربح الإجمالي تحت ضغط جانب التكاليف",
            "description": "هامش الربح الإجمالي {gm}% يقترب من منطقة التحذير. للشركات التشغيلية والخدمية، يتراوح الهامش الصحي عادةً بين 35-55% حسب نموذج الأعمال. عند {gm}%، تكلفة تقديم الخدمة تستهلك {cogs_pct}% من الإيرادات.",
            "mechanism": "تراجع هامش الربح الإجمالي في الشركات التشغيلية عادةً يعود إلى: (1) ارتفاع تكاليف المدخلات (مواد، طاقة، مقاولون) غير المنعكس في التسعير، (2) انخفاض كفاءة تقديم الخدمة، (3) ارتفاع تكاليف الموردين غير المُعوَّض، أو (4) تضخم تكاليف العمالة دون زيادة مقابلة في الإنتاجية.",
        },
        "tr": {
            "title": "Brüt Marj Maliyet Tarafı Baskısı Altında",
            "description": "Brüt marj %{gm} uyarı bölgesine yaklaşıyor. Hizmet ve operasyonel işletmeler için sağlıklı brüt marj iş modeline göre genellikle %35-55 aralığındadır. %{gm}'de, hizmet teslim maliyeti gelirin %{cogs_pct}'ini tüketiyor.",
            "mechanism": "Operasyonel işletmelerde brüt marj düşüşü genellikle şunlara bağlıdır: (1) fiyatlandırmaya yansıtılmayan girdi maliyeti artışları (malzeme, enerji, taşeronlar), (2) hizmet tesliminde verimsizlik — kaynak birimi başına düşen çıktı, (3) verimlilik kazanımlarıyla telafi edilemeyen tedarikçi maliyet artışları, (4) çıktı artışı olmaksızın işçilik maliyeti enflasyonu.",
        },
    },

    # ── Efficiency causes ──────────────────────────────────────────────────────
    "eff_ccc_long": {
        "en": {
            "title": "Long Cash Conversion Cycle Traps Capital",
            "description": "The {ccc}-day cash cycle means money invested today takes {ccc} days to return as collected cash. This consists of {dio} days of inventory holding + {dso} days of receivables collection - {dpo} days of supplier credit. The business is effectively financing {ccc_capital} of working capital to sustain operations.",
            "mechanism": "In service-based businesses, CCC should be relatively short because services are delivered and billed promptly. A long CCC reveals that either customers are slow to pay (DSO {dso}d) or operating inventory (materials, supplies, consumables) is not turning fast enough ({it}x/year vs a typical 6–8x benchmark for operational businesses).",
        },
        "ar": {
            "title": "طول دورة تحويل النقد يحتجز رأس المال",
            "description": "دورة نقد {ccc} يوم تعني أن المال المستثمر اليوم يستغرق {ccc} يوماً للعودة كنقد محصَّل. يتكون من {dio} يوم احتجاز مخزون + {dso} يوم تحصيل مستحقات - {dpo} يوم ائتمان مورد. الشركة تمول فعلياً {ccc_capital} من رأس المال العامل.",
            "mechanism": "في الشركات الخدمية، يجب أن تكون دورة النقد قصيرة نسبياً لأن الخدمات تُسلَّم وتُفوتَر فوراً. دورة طويلة تكشف إما عن بطء سداد العملاء (أيام القبض {dso}) أو بطء دوران المخزون التشغيلي ({it} مرة/سنة مقابل معيار 6-8 مرات).",
        },
        "tr": {
            "title": "Uzun Nakit Döngüsü Sermayeyi Hapsediyor",
            "description": "{ccc} günlük nakit döngüsü, bugün yatırılan paranın {ccc} gün sonra tahsil edilmiş nakit olarak geri döndüğü anlamına geliyor. {dio} gün stok tutma + {dso} gün alacak tahsilatı - {dpo} gün tedarikçi kredisinden oluşuyor.",
            "mechanism": "Hizmet odaklı işletmelerde nakit döngüsü görece kısa olmalı çünkü hizmetler teslim edilip hemen faturalanıyor. Uzun döngü müşteri ödemelerinin yavaş olduğunu (DSO {dso}g) veya operasyonel stok devir hızının düşük olduğunu ({it}x/yıl) gösteriyor.",
        },
    },

    "eff_slow_inventory": {
        "en": {
            "title": "Inventory Turnover Below Operational Benchmark",
            "description": "Inventory turns {it}x per year (approximately every {it_days} days). For operational businesses, inventory (materials, supplies, consumables) typically should turn 6–8x per year or more. At {it}x, approximately {excess_inv} of capital is tied up in excess stock beyond what efficient operations require.",
            "mechanism": "Low inventory turnover in operations means either over-purchasing to guard against stockouts, poor demand forecasting, or items becoming obsolete. Each day of unnecessary inventory is dead capital that earns no return and consumes storage and management overhead.",
        },
        "ar": {
            "title": "دوران المخزون أقل من المعيار التشغيلي",
            "description": "يدور المخزون {it} مرة في السنة (كل {it_days} يوم تقريباً). للشركات التشغيلية، يجب أن يدور المخزون (مواد، لوازم، مستهلكات) 6-8 مرات في السنة أو أكثر. عند {it}x، حوالي {excess_inv} من رأس المال محتجز في مخزون زائد.",
            "mechanism": "انخفاض دوران المخزون في العمليات يعني إما مشتريات زائدة لتجنب نفاد المخزون، أو ضعف التنبؤ بالطلب، أو تقادم بعض البنود. كل يوم من المخزون غير الضروري هو رأس مال ميت لا يدر عائداً.",
        },
        "tr": {
            "title": "Stok Devir Hızı Operasyonel Ölçütün Altında",
            "description": "Stok yılda {it}x dönüyor (yaklaşık her {it_days} günde bir). Operasyonel işletmeler için stok genellikle 6-8x/yıl veya daha fazla dönmeli. {it}x'te yaklaşık {excess_inv} sermaye fazla stokta bağlı.",
            "mechanism": "İşlemlerde düşük stok devri, stok tükenmesine karşı aşırı satın alma, zayıf talep tahmini veya eskimiş kalemler anlamına geliyor. Her gereksiz stok günü, depolama ve yönetim maliyetleri tüketen ve getiri sağlamayan ölü sermayedir.",
        },
    },

    # ── Leverage causes ────────────────────────────────────────────────────────
    "lev_high_de": {
        "en": {
            "title": "Debt Load Amplifies Earnings Volatility",
            "description": "Debt-to-equity of {de}x means creditors have {de} times more claim on assets than equity holders. With debt ratio of {dr}%, every downturn in revenue immediately stresses debt coverage ratios. Interest payments are fixed regardless of revenue — they consume margin even when revenue falls.",
            "mechanism": "High leverage creates an operating cost floor that cannot flex downward. If EBIT falls 20% but interest payments stay constant, net profit can fall 40-60% depending on leverage level. At {de}x D/E, the business has limited financial buffer to absorb a bad quarter.",
        },
        "ar": {
            "title": "العبء الديني يضخم تقلبات الأرباح",
            "description": "نسبة الدين إلى حقوق الملكية {de} تعني أن الدائنين لديهم مطالبة بالأصول تفوق {de} مرة ما لدى المساهمين. مع نسبة دين {dr}%، أي انخفاض في الإيرادات يضغط فوراً على نسب تغطية الديون.",
            "mechanism": "الرفع المالي العالي يخلق أرضية تكاليف تشغيلية لا يمكن خفضها. إذا انخفض EBIT بنسبة 20% لكن مدفوعات الفائدة بقيت ثابتة، قد ينخفض صافي الربح بنسبة 40-60%.",
        },
        "tr": {
            "title": "Borç Yükü Kazanç Oynaklığını Artırıyor",
            "description": "Borç/özkaynaklar {de}x, alacaklıların varlıklar üzerinde özkaynak sahiplerinden {de} kat daha fazla hak sahibi olduğu anlamına geliyor. Borç oranı %{dr} iken, gelirdeki her düşüş borç karşılama oranlarını hemen zorluyor.",
            "mechanism": "Yüksek kaldıraç, aşağı esnetilemez bir sabit maliyet tabanı oluşturuyor. EBIT %20 düşerse ama faiz ödemeleri sabit kalırsa, kaldıraç seviyesine bağlı olarak net kar %40-60 düşebilir.",
        },
    },

    # ── Growth causes ──────────────────────────────────────────────────────────
    "growth_revenue_stall": {
        "en": {
            "title": "Revenue Growth Stalling Despite Market Opportunity",
            "description": "Revenue trend is {rev_dir} with YTD change of {ytd_rev}% vs prior year. In a growing economy, flat or declining revenue signals one of: (1) customer churn not being replaced, (2) pricing not keeping pace with cost inflation, (3) capacity or operational constraints limiting new business acceptance, or (4) competitive pressure on price or service quality.",
            "mechanism": "In service businesses, revenue growth requires either more customers, more volume per customer, or higher prices. Each of these has a different remediation path. Without diagnosing which driver is failing, growth investment may be mis-directed.",
        },
        "ar": {
            "title": "ركود نمو الإيرادات رغم فرص السوق",
            "description": "اتجاه الإيرادات {rev_dir} مع تغيير YTD بنسبة {ytd_rev}% مقارنة بالعام السابق. في اقتصاد نام، الإيرادات الثابتة أو المتراجعة تشير إلى أحد: (1) تسرب العملاء غير المُعوَّض، (2) التسعير لا يواكب تضخم التكاليف، (3) قيود تشغيلية تحد من قبول أعمال جديدة، أو (4) ضغط تنافسي على السعر أو جودة الخدمة.",
            "mechanism": "في أعمال الخدمات، يتطلب نمو الإيرادات إما مزيداً من العملاء أو حجماً أكبر لكل عميل أو أسعاراً أعلى. بدون تشخيص المحرك الفاشل، قد يكون استثمار النمو في الاتجاه الخاطئ.",
        },
        "tr": {
            "title": "Pazar Fırsatlarına Rağmen Gelir Büyümesi Durma Noktasında",
            "description": "Gelir trendi {rev_dir}, geçen yıla göre YBD değişimi %{ytd_rev}. Büyüyen bir ekonomide sabit veya düşen gelir şunlardan birini gösteriyor: (1) yerine konulmayan müşteri kaybı, (2) fiyatlandırmanın maliyet enflasyonunu takip edememesi, (3) yeni iş kabulünü kısıtlayan operasyonel kısıtlamalar, (4) fiyat veya hizmet kalitesi üzerindeki rekabetçi baskı.",
            "mechanism": "Hizmet işletmelerinde gelir büyümesi daha fazla müşteri, müşteri başına daha fazla hacim veya daha yüksek fiyat gerektirir.",
        },
    },

    # ── Cross-domain cause ────────────────────────────────────────────────────
    "cross_margin_liquidity_trap": {
        "en": {
            "title": "Margin Compression and Liquidity Weakness Are Self-Reinforcing",
            "description": "The combination of net margin {nm}% and current ratio {cr}x creates a compounding risk. Low margins mean less cash generated per cycle. Low liquidity means less buffer when collections slow. Together, these create a self-reinforcing trap: to fix liquidity, collections must accelerate — but customers who are slow payers tend to stay slow without pricing power or contract renegotiation.",
            "mechanism": "This pattern is common in commodity-like service businesses where pricing is competitive and clients have leverage. Breaking out requires simultaneous action on margin (cost reduction or pricing) and liquidity (collections or financing) — neither alone is sufficient.",
        },
        "ar": {
            "title": "ضغط الهامش وضعف السيولة يُعزز كل منهما الآخر",
            "description": "تركيبة الهامش الصافي {nm}% ونسبة التداول {cr} تخلق خطراً مركباً. الهوامش المنخفضة تعني توليد نقد أقل لكل دورة. السيولة المنخفضة تعني هامش أمان أقل عند تباطؤ التحصيل.",
            "mechanism": "هذا النمط شائع في أعمال الخدمات التنافسية حيث للعملاء قوة تفاوضية. الخروج يتطلب إجراءاً متزامناً على الهامش والسيولة — لا يكفي أي منهما وحده.",
        },
        "tr": {
            "title": "Marj Baskısı ve Likidite Zayıflığı Birbirini Güçlendiriyor",
            "description": "Net marj %{nm} ve cari oran {cr}x kombinasyonu bileşik risk yaratıyor. Düşük marjlar döngü başına daha az nakit üretir. Düşük likidite tahsilat yavaşladığında daha az tampon sağlar.",
            "mechanism": "Bu örüntü, müşterilerin pazarlık gücüne sahip olduğu rekabetçi hizmet işletmelerinde yaygın. Çıkış için marj ve likidite üzerinde eş zamanlı eylem gerekli.",
        },
    },
}


def _t(key: str, lang: str, **kw) -> dict:
    entry = _CT.get(key, {})
    loc   = entry.get(lang) or entry.get("en") or {}
    def _f(s: str) -> str:
        try:    return s.format(**kw)
        except: return s
    return {k: _f(v) for k, v in loc.items()}


# ──────────────────────────────────────────────────────────────────────────────
#  Cause builders per domain
# ──────────────────────────────────────────────────────────────────────────────

def _confidence_from_status(status: str, n_periods: int) -> int:
    base = {"risk": 90, "warning": 75, "neutral": 55, "good": 35}.get(status, 55)
    if n_periods >= 6:  base += 5
    elif n_periods <= 2: base -= 10
    return min(95, max(40, base))


def _cause(id_: str, domain: str, linked_decisions: list,
           confidence: int, impact: str, text: dict) -> dict:
    return {
        "id":               id_,
        "domain":           domain,
        "title":            text.get("title", id_),
        "description":      text.get("description", ""),
        "mechanism":        text.get("mechanism", ""),
        "impact":           impact,       # "high" | "medium" | "low"
        "confidence":       confidence,
        "linked_decisions": linked_decisions,
    }


def _liquidity_causes(ratios: dict, trends: dict, decisions: list,
                      lang: str, n: int) -> list[dict]:
    causes = []
    dec_ids = [d.get("domain", "") for d in decisions]
    linked  = ["liquidity"]

    cr  = _v(ratios, "liquidity", "current_ratio")
    wc  = _v(ratios, "liquidity", "working_capital")
    dso = _v(ratios, "efficiency", "dso_days")
    nm  = _v(ratios, "profitability", "net_margin_pct")
    cr_st = _st(ratios, "liquidity", "current_ratio")
    wc_st = _st(ratios, "liquidity", "working_capital")

    # Estimate daily revenue
    np_val = _v(ratios, "profitability", "net_profit")
    daily_rev = None
    total_locked = None
    if np_val and nm and nm > 0:
        rev_est = abs(np_val) / (nm / 100)
        daily_rev   = _fmtK(rev_est / 30)   # monthly
        total_locked= _fmtK(rev_est / 365 * (dso or 0))

    if cr is not None and cr_st in ("risk", "warning"):
        cl_ratio = _fmt(1 / cr, ".1f") if cr and cr > 0 else "?"
        txt = _t("liq_cr_weak", lang, cr=_fmt(cr,".2f"), cl_ratio=cl_ratio)
        impact = "high" if cr_st == "risk" else "medium"
        causes.append(_cause("liq_cr_weak", "liquidity", linked,
                              _confidence_from_status(cr_st, n), impact, txt))

    if wc is not None and wc_st in ("risk", "warning"):
        txt = _t("liq_wc_negative", lang,
                 wc=_fmtK(wc), wc_abs=_fmtK(abs(wc)),
                 dso=str(round(dso)) if dso else "—")
        impact = "high" if wc < 0 else "medium"
        causes.append(_cause("liq_wc_negative", "liquidity", linked,
                              _confidence_from_status(wc_st, n), impact, txt))

    if dso is not None and dso > 45:
        dso_st = _st(ratios, "efficiency", "dso_days")
        period_label = (trends.get("periods") or ["the period"])[-1]
        txt = _t("liq_slow_collections", lang,
                 dso=str(round(dso)), period_label=period_label,
                 daily_rev=daily_rev or "—", total_locked=total_locked or "—")
        impact = "high" if dso > 70 else "medium"
        causes.append(_cause("liq_slow_collections", "liquidity",
                              ["liquidity", "efficiency"],
                              _confidence_from_status(dso_st, n), impact, txt))

    return causes


def _profitability_causes(ratios: dict, trends: dict, decisions: list,
                           lang: str, n: int) -> list[dict]:
    causes = []
    nm  = _v(ratios, "profitability", "net_margin_pct")
    gm  = _v(ratios, "profitability", "gross_margin_pct")
    nm_st = _st(ratios, "profitability", "net_margin_pct")
    gm_st = _st(ratios, "profitability", "gross_margin_pct")

    if nm is not None and nm_st in ("risk", "warning"):
        gap = round((gm or 0) - nm, 1)
        txt = _t("prof_nm_compression", lang,
                 nm=_fmt(nm), gm=_fmt(gm), gap=_fmt(gap),
                 nm_cents=_fmt(nm / 100, ".2f") if nm else "—")
        causes.append(_cause("prof_nm_compression", "profitability", ["profitability"],
                              _confidence_from_status(nm_st, n), "high", txt))

    if gm is not None and gm_st in ("risk", "warning"):
        cogs_pct = round(100 - gm, 1) if gm else "—"
        txt = _t("prof_gm_pressure", lang,
                 gm=_fmt(gm), cogs_pct=_fmt(cogs_pct))
        impact = "high" if gm < 25 else "medium"
        causes.append(_cause("prof_gm_pressure", "profitability", ["profitability"],
                              _confidence_from_status(gm_st, n), impact, txt))

    return causes


def _efficiency_causes(ratios: dict, trends: dict, decisions: list,
                        lang: str, n: int) -> list[dict]:
    causes = []
    ccc = _v(ratios, "efficiency", "ccc_days")
    dso = _v(ratios, "efficiency", "dso_days")
    dpo = _v(ratios, "efficiency", "dpo_days")
    dio = _v(ratios, "efficiency", "dio_days")
    it  = _v(ratios, "efficiency", "inventory_turnover")
    ccc_st = _st(ratios, "efficiency", "ccc_days")
    it_st  = _st(ratios, "efficiency", "inventory_turnover")

    # Estimate capital locked in CCC
    nm   = _v(ratios, "profitability", "net_margin_pct")
    np_v = _v(ratios, "profitability", "net_profit")
    ccc_capital = "—"
    if np_v and nm and nm > 0 and ccc:
        rev_est = abs(np_v) / (nm / 100)
        ccc_capital = _fmtK(rev_est / 365 * ccc)

    if ccc is not None and ccc_st in ("risk", "warning"):
        txt = _t("eff_ccc_long", lang,
                 ccc=str(round(ccc)),
                 dio=str(round(dio)) if dio else "—",
                 dso=str(round(dso)) if dso else "—",
                 dpo=str(round(dpo)) if dpo else "—",
                 it=_fmt(it, ".1f") if it else "—",
                 ccc_capital=ccc_capital)
        causes.append(_cause("eff_ccc_long", "efficiency",
                              ["efficiency", "liquidity"],
                              _confidence_from_status(ccc_st, n), "high", txt))

    if it is not None and it_st in ("risk", "warning") and it < 4:
        it_days = round(365 / it) if it > 0 else 999
        # Excess inventory estimate: if benchmark is 6x, excess = inv*(1 - it/6)
        excess_inv = "—"
        if np_v and nm and nm > 0 and it > 0:
            rev_est    = abs(np_v) / (nm / 100)
            benchmark  = 6
            inv_est    = rev_est / it
            excess     = inv_est * max(0, 1 - it / benchmark)
            excess_inv = _fmtK(excess)
        txt = _t("eff_slow_inventory", lang,
                 it=_fmt(it, ".1f"), it_days=str(it_days),
                 excess_inv=excess_inv)
        causes.append(_cause("eff_slow_inventory", "efficiency", ["efficiency"],
                              _confidence_from_status(it_st, n), "medium", txt))

    return causes


def _leverage_causes(ratios: dict, trends: dict, decisions: list,
                      lang: str, n: int) -> list[dict]:
    causes = []
    de    = _v(ratios, "leverage", "debt_to_equity")
    dr    = _v(ratios, "leverage", "debt_ratio_pct")
    de_st = _st(ratios, "leverage", "debt_to_equity")

    if de is not None and de_st in ("risk", "warning"):
        txt = _t("lev_high_de", lang, de=_fmt(de, ".1f"), dr=_fmt(dr, ".1f"))
        impact = "high" if de > 3.0 else "medium"
        causes.append(_cause("lev_high_de", "leverage", ["leverage"],
                              _confidence_from_status(de_st, n), impact, txt))

    return causes


def _growth_causes(ratios: dict, trends: dict, decisions: list,
                    lang: str, n: int) -> list[dict]:
    causes = []
    rev_dir = (trends.get("revenue") or {}).get("direction", "insufficient_data")
    ytd_rev = (trends.get("revenue") or {}).get("ytd_vs_prior")

    if rev_dir in ("down", "stable") and (ytd_rev is None or ytd_rev < 5):
        txt = _t("growth_revenue_stall", lang,
                 rev_dir=rev_dir,
                 ytd_rev=_fmt(ytd_rev, "+.1f") if ytd_rev is not None else "—")
        impact = "high" if rev_dir == "down" else "medium"
        causes.append(_cause("growth_revenue_stall", "growth", ["growth", "profitability"],
                              70, impact, txt))

    return causes


def _cross_causes(ratios: dict, trends: dict, decisions: list,
                   lang: str, n: int) -> list[dict]:
    causes = []
    nm  = _v(ratios, "profitability", "net_margin_pct")
    cr  = _v(ratios, "liquidity",     "current_ratio")
    nm_st = _st(ratios, "profitability", "net_margin_pct")
    cr_st = _st(ratios, "liquidity",     "current_ratio")

    # Only generate cross-cause when BOTH are weak
    if (nm is not None and nm_st in ("risk", "warning") and
            cr is not None and cr_st in ("risk", "warning")):
        txt = _t("cross_margin_liquidity_trap", lang,
                 nm=_fmt(nm, ".1f"), cr=_fmt(cr, ".2f"))
        causes.append(_cause("cross_margin_liquidity_trap", "cross_domain",
                              ["liquidity", "profitability"],
                              80, "high", txt))

    return causes


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_root_causes(
    intelligence:   dict,
    decisions:      list,
    lang:           str = "en",
    n_periods:      int = 3,
) -> dict:
    """
    Build CFO-level root cause analysis linked to Phase 25 decisions.

    Args:
        intelligence: output of fin_intelligence.build_intelligence()
        decisions:    output of cfo_decision_engine.build_cfo_decisions()["decisions"]
        lang:         "en" | "ar" | "tr"
        n_periods:    number of analysis periods (affects confidence)

    Returns:
        {
          "causes":          [RootCause, ...],   -- sorted by impact
          "causes_by_domain": { domain: [RootCause] },
          "summary": {
              "total":    int,
              "high":     int,
              "medium":   int,
              "domains_affected": [str],
          }
        }
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"

    ratios  = intelligence.get("ratios",  {})
    trends  = intelligence.get("trends",  {})

    all_causes: list[dict] = []
    all_causes += _liquidity_causes(ratios, trends, decisions, lang, n_periods)
    all_causes += _profitability_causes(ratios, trends, decisions, lang, n_periods)
    all_causes += _efficiency_causes(ratios, trends, decisions, lang, n_periods)
    all_causes += _leverage_causes(ratios, trends, decisions, lang, n_periods)
    all_causes += _growth_causes(ratios, trends, decisions, lang, n_periods)
    all_causes += _cross_causes(ratios, trends, decisions, lang, n_periods)

    # Deduplicate by id
    seen: dict[str, dict] = {}
    for c in all_causes:
        seen[c["id"]] = c
    all_causes = list(seen.values())

    # Sort: high impact first, then by confidence
    impact_rank = {"high": 2, "medium": 1, "low": 0}
    all_causes.sort(key=lambda c: (
        -impact_rank.get(c["impact"], 0),
        -c["confidence"],
    ))

    # Group by domain
    by_domain: dict[str, list] = {}
    for c in all_causes:
        by_domain.setdefault(c["domain"], []).append(c)

    domains_affected = list(by_domain.keys())
    summary = {
        "total":            len(all_causes),
        "high":             sum(1 for c in all_causes if c["impact"] == "high"),
        "medium":           sum(1 for c in all_causes if c["impact"] == "medium"),
        "low":              sum(1 for c in all_causes if c["impact"] == "low"),
        "domains_affected": domains_affected,
    }

    return {
        "causes":            all_causes,
        "causes_by_domain":  by_domain,
        "summary":           summary,
    }
