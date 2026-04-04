"""
vcfo_ai_advisor.py — VCFO AI CFO Answer Engine (Production Grade)

Builds dense, grounded system prompts from full VCFO context.
Handles natural Arabic conversation including follow-up and dialectal patterns.
Routes questions to correct data domains.

Wave 2B: prompt scaffold labels are selected by requested language (ar/en/tr);
decision grounding prefers realize_causal_items(ctx[\"causal_items\"]) over raw
English rationale. Intent/memory keys are mapped to localized labels.
"""
from __future__ import annotations
from typing import Optional

from app.services.causal_realize import realize_causal_items


# ── Intent detection — extended with all required categories ─────────────────

INTENT_PATTERNS = {
    "profitability": [
        # EN
        "profit", "margin", "revenue", "income", "loss", "earning", "gross",
        "net profit", "operating", "profitability",
        # AR — MSA + Gulf dialect
        "ربح", "هامش", "خسار", "إيراد", "دخل", "أرباح", "الربحية",
        "الإيرادات", "المبيعات", "ايراد", "ارباح", "خساره",
        "لماذا انخفض الربح", "لماذا ارتفع الربح", "لماذا تغير الربح",
        "ليش انخفض الربح", "ليش خسران",
        # TR
        "kâr", "marj", "gelir", "zarar", "kârlılık",
    ],
    "cashflow": [
        "cash", "flow", "liquidity", "working capital", "burn", "runway",
        "receivable", "payable", "collection",
        "نقد", "تدفق", "سيول", "رأس المال العامل", "تحصيل",
        "مدينون", "دائنون", "التدفقات", "نقدية",
        "nakit", "akış", "likidite", "işletme sermayesi",
    ],
    "risk": [
        "risk", "danger", "warning", "anomal", "unstable", "concern",
        "critical", "alert", "problem", "issue",
        "خطر", "تحذير", "مخاطر", "انتباه", "مشكلة", "خطير", "أزمة",
        "risk", "tehlike", "uyarı", "endişe",
    ],
    "decision": [
        "what should", "recommend", "action", "priority", "do first", "plan",
        "next step", "advice", "suggest",
        "ماذا أفعل", "توصية", "إجراء", "أولوية", "خطة", "قرار",
        "ايش الحل", "وش الحل", "ايش اسوي", "وش اسوي",
        "ماذا أسوي", "ايش أول", "وش أول", "اول قرار", "الحل",
        "طيب وش الحل", "طيب ايش الحل", "لو خفضنا", "لو رفعنا",
        "لو قللنا", "لو زدنا", "ماذا يحدث لو", "ايش يصير لو",
        "ne yapmalı", "tavsiye", "öncelik", "eylem",
    ],
    "branches": [
        "branch", "region", "entity", "strongest", "weakest", "compare",
        "loss branch", "worst branch", "best branch",
        "فرع", "فروع", "منطقة", "الأقوى", "الأضعف", "مقارنة",
        "طرابزون", "اوروبا", "اسيا", "الفرع", "فرع خاسر",
        "اي فرع", "ايش فرع", "وش فرع",
        "şube", "bölge", "güçlü", "zayıf", "karşılaştır",
    ],
    "validation": [
        "reliable", "accurate", "valid", "warning", "error", "approximat",
        "data quality", "trust", "correct",
        "موثوق", "دقيق", "تحقق", "تقريب", "تحذير", "صحة البيانات",
        "البيانات صحيحة", "هل الارقام", "هل البيانات", "موثوقة",
        "güvenilir", "doğru", "geçerli", "yaklaşık",
    ],
    "forecast": [
        "forecast", "project", "expect", "future", "next month", "predict",
        "outlook", "trend forward",
        "توقع", "تنبؤ", "مستقبل", "القادم", "الشهر القادم", "توقعات",
        "tahmin", "projeksiyon", "gelecek", "beklenti",
    ],
    "statements": [
        "balance sheet", "income statement", "cash flow statement",
        "explain statement", "IS ", "BS ",
        "الميزانية", "قائمة الدخل", "التدفقات النقدية",
        "القوائم المالية", "اشرح القائمة",
        "bilanço", "gelir tablosu", "nakit akış tablosu",
    ],
    "comparisons": [
        "compare", "vs", "versus", "difference", "last month",
        "last quarter", "last year", "period", "3 months",
        "قارن", "مقارنة", "الفرق", "الشهر الماضي", "آخر 3 شهور",
        "آخر ثلاثة", "بالمقارنة", "3 شهور",
        "طيب قارن", "قارن آخر", "مقارنة بـ",
        "karşılaştır", "fark", "geçen ay",
    ],
    "trend_explanation": [
        "why", "reason", "cause", "explain why", "because", "what caused",
        "how come", "what happened",
        "ليش", "ليه", "لماذا", "السبب", "لأن", "وش السبب",
        "كيف صار", "ايش صار", "وش صار", "لماذا انخفض", "لماذا ارتفع",
        "شرح", "فسر", "اشرح",
        "neden", "sebep", "açıkla",
    ],
    "action_priority": [
        "first", "most important", "urgent", "immediately", "top priority",
        "what first", "start with",
        "أولاً", "الأهم", "عاجل", "فوراً", "اول", "ابدأ بـ",
        "ايش أول شي", "وش أول شي", "البداية من", "قبل كل شي",
        "ما أول", "أول قرار", "ما هو أول", "قبل أي شيء",
        "önce", "acil", "önemli",
    ],
    "executive_summary": [
        "summary", "overall", "big picture", "in short", "brief",
        "overview", "bottom line", "tell me everything",
        "لخص", "باختصار", "ملخص", "الصورة الكاملة", "وضع الشركة",
        "اشرح مثل المدير المالي", "مثل المدير", "مثل المدير المالي",
        "مثل المدير", "مثل الـ CFO", "اشرح كـ CFO",
        "اشرح بشكل مبسط", "تلخيص", "كلها",
        "اشرح كأنك مدير", "شرح مبسط", "شرح إداري",
        "özet", "genel", "kısaca",
    ],
}

# Vague follow-up patterns — use session memory
FOLLOWUP_AR = [
    "ليش", "ليه", "طيب", "وبعدين", "إذن", "وبعد", "أكمل",
    "طيب وش", "طيب ايش", "وش عن", "ايش عن", "وعن",
    "صح", "زين", "مفهوم", "كمل", "ثم", "والآن", "الحين",
]
FOLLOWUP_EN = ["why", "ok", "and", "then", "what else", "more", "continue", "go on"]

# ── Prompt scaffold (controlled per-language; no mixed shell) ────────────────

_ADVISOR_LABELS: dict[str, dict[str, str]] = {
    "ar": {
        "role": "أنت المستشار المالي الذكي المدمج في منصة VCFO.\nلديك صلاحية الوصول لكامل البيانات المالية للشركة.",
        "company_block": "━━━ بيانات الشركة ━━━",
        "company_meta": "الشركة: {name} | العملة: {cur}",
        "performance_block": "━━━ الأداء المالي ━━━",
        "margins_block": "━━━ الهوامش والنسب ━━━",
        "cashflow_block": "━━━ التدفق النقدي ━━━",
        "branches_block": "━━━ الفروع ({n} فروع) ━━━",
        "risk_block": "━━━ تقييم المخاطر / القرارات ━━━",
        "periods_block": "━━━ مقارنة الفترات ━━━",
        "validation_block": "━━━ سلامة البيانات ━━━",
        "rules_block": "━━━ قواعد الإجابة (إلزامية) ━━━",
        "branch_strong": "الأقوى",
        "branch_weak": "الأضعف / الخاسر",
        "branch_na": "غير متاح",
        "branches_empty": "  لا توجد بيانات فروع",
        "decisions_empty": "  لا توجد قرارات منسقة",
        "periods_empty": "  لا توجد بيانات فترات متعددة",
        "mem_topic": "آخر موضوع",
        "mem_branch": "آخر فرع",
        "mem_metric": "آخر مقياس",
        "mem_header": "سياق المحادثة السابقة",
        "lbl_rev": "إيراد",
        "lbl_margin": "هامش",
        "lbl_np": "صافي ربح",
        "loss_badge": " ⚠ خسارة",
        "ocf_formula_note": "OCF = صافي الربح + إهلاك ± تغيرات رأس المال العامل",
        "days": "يوم",
        "rule_val_prefix": "حالة التحقق",
        "rule_val_pass": "البيانات سليمة",
        "rule_val_warn": "إذا لم تكن PASS، اذكر ذلك بوضوح في أول إجابتك",
        "rule_no_fabricate": "لا تستخدم أرقاماً غير موجودة في البيانات أعلاه.",
        "rule_missing": "إذا كانت البيانات غير متاحة: قل \"هذه البيانات غير متاحة حالياً\" ولا تخترع أرقاماً.",
        "rule_followup": "الأسئلة المتابعة (ليش؟ طيب؟ وش السبب؟): استخدم سياق المحادثة السابق للإجابة.",
        "rule_length": "الطول المثالي: 150-300 كلمة إلا إذا طُلب تفصيل أكثر.",
        "causal_header": "القرارات المستندة إلى القالب السببي (causal_items):",
        "legacy_header": "ملخص إشارات المخاطر (legacy):",
        "scaffold_fallback_note": "",
        "val_pass": "✓ سليمة — يمكن الاعتماد على الأرقام",
        "val_warn": "⚠ تحذير — الأرقام مقبولة لكن بحذر",
        "val_fail": "✗ فشل — هناك مشاكل في سلامة البيانات",
        "val_unknown": "غير معروف",
        "val_approx": "\n  ⚠ تقريب مكتشف: نسبة التداول والنسبة السريعة قد تكون غير دقيقة",
        "val_blocking": "\n  🚫 مشكلة حرجة: لا تعتمد على هذه الأرقام لقرارات مهمة",
        "p_rev_latest": "الإيراد (الفترة)",
        "p_rev_window": "الإيراد (النافذة كاملة)",
        "p_np": "صافي الربح",
        "p_gp": "الربح الإجمالي",
        "p_cogs": "تكلفة البضاعة (COGS)",
        "p_opex": "المصروفات التشغيلية",
        "p_mom_rev": "التغيير MoM - الإيراد",
        "p_mom_np": "التغيير MoM - الربح",
        "m_gm": "هامش الربح الإجمالي",
        "m_nm": "هامش الربح الصافي",
        "m_om": "هامش التشغيل",
        "m_er": "نسبة المصروفات",
        "m_cr": "نسبة التداول",
        "m_qr": "نسبة سريعة",
        "m_wc": "رأس المال العامل",
        "m_dso": "DSO (أيام القبض)",
        "m_dpo": "DPO (أيام الدفع)",
        "m_ccc": "CCC (دورة النقد)",
        "cf_ocf": "التدفق التشغيلي (OCF)",
        "cf_fcf": "التدفق الحر (FCF)",
        "cf_cash": "الرصيد النقدي",
        "cf_eq": "المعادلة",
        "rule1": "1. الجواب المباشر: أول جملة تجيب على السؤال مباشرة",
        "rule2": "2. الدليل الرقمي: استخدم الأرقام الحقيقية من البيانات أعلاه فقط",
        "rule3": "3. التفسير: اشرح لماذا حدث هذا (السبب الجذري)",
        "rule4": "4. الإجراء المطلوب: أعطِ خطوة عملية واضحة",
        "period_row": "  {period}: إيراد={rev} ربح={np} هامش={margin}",
        "risk_score_lbl": "درجة الخطر",
        "priority_lbl": "الأولوية",
    },
    "en": {
        "role": "You are the AI CFO advisor embedded in the VCFO platform.\nYou have access to the company's full financial dataset.",
        "company_block": "━━━ Company ━━━",
        "company_meta": "Company: {name} | Currency: {cur}",
        "performance_block": "━━━ Financial performance ━━━",
        "margins_block": "━━━ Margins & ratios ━━━",
        "cashflow_block": "━━━ Cash flow ━━━",
        "branches_block": "━━━ Branches ({n} branches) ━━━",
        "risk_block": "━━━ Risk / decisions ━━━",
        "periods_block": "━━━ Period comparison ━━━",
        "validation_block": "━━━ Data validation ━━━",
        "rules_block": "━━━ Answer rules (mandatory) ━━━",
        "branch_strong": "Strongest",
        "branch_weak": "Weakest / loss",
        "branch_na": "N/A",
        "branches_empty": "  No branch data",
        "decisions_empty": "  No structured decisions",
        "periods_empty": "  No multi-period breakdown",
        "mem_topic": "Last topic",
        "mem_branch": "Last branch",
        "mem_metric": "Last metric",
        "mem_header": "Conversation context",
        "lbl_rev": "Revenue",
        "lbl_margin": "Margin",
        "lbl_np": "Net profit",
        "loss_badge": " ⚠ loss",
        "ocf_formula_note": "OCF = net profit + depreciation ± working capital changes",
        "days": "days",
        "rule_val_prefix": "Validation status",
        "rule_val_pass": "Data passed validation",
        "rule_val_warn": "If status is not PASS, state that clearly in your first sentence",
        "rule_no_fabricate": "Do not use numbers that are not present in the data above.",
        "rule_missing": "If data is unavailable, say it is unavailable — do not invent figures.",
        "rule_followup": "For follow-ups (why? what next?), use prior conversation context.",
        "rule_length": "Aim for 150–300 words unless the user asks for more detail.",
        "causal_header": "Causal template grounding (causal_items, realized):",
        "legacy_header": "Heuristic risk summary (legacy):",
        "scaffold_fallback_note": "",
        "val_pass": "✓ OK — numbers are reliable",
        "val_warn": "⚠ Warning — numbers usable with caution",
        "val_fail": "✗ Failed — data integrity issues",
        "val_unknown": "Unknown",
        "val_approx": "\n  ⚠ Approximation detected: current/quick ratios may be less precise",
        "val_blocking": "\n  🚫 Critical: do not rely on these figures for major decisions",
        "p_rev_latest": "Revenue (latest period)",
        "p_rev_window": "Revenue (full window)",
        "p_np": "Net profit",
        "p_gp": "Gross profit",
        "p_cogs": "COGS",
        "p_opex": "Operating expenses",
        "p_mom_rev": "MoM change — revenue",
        "p_mom_np": "MoM change — net profit",
        "m_gm": "Gross margin",
        "m_nm": "Net margin",
        "m_om": "Operating margin",
        "m_er": "Expense ratio",
        "m_cr": "Current ratio",
        "m_qr": "Quick ratio",
        "m_wc": "Working capital",
        "m_dso": "DSO (days)",
        "m_dpo": "DPO (days)",
        "m_ccc": "CCC (days)",
        "cf_ocf": "Operating cash flow (OCF)",
        "cf_fcf": "Free cash flow (FCF)",
        "cf_cash": "Cash balance",
        "cf_eq": "Formula",
        "rule1": "1. Lead with a direct answer in the first sentence",
        "rule2": "2. Use only numeric evidence from the data above",
        "rule3": "3. Explain why (root cause)",
        "rule4": "4. Give one concrete next step",
        "period_row": "  {period}: revenue={rev} net_profit={np} margin={margin}",
        "risk_score_lbl": "Risk score",
        "priority_lbl": "Priority",
    },
    "tr": {
        "role": "VCFO platformuna gömülü AI CFO danışmanısınız.\nŞirketin tüm finansal verilerine erişiminiz var.",
        "company_block": "━━━ Şirket ━━━",
        "company_meta": "Şirket: {name} | Para birimi: {cur}",
        "performance_block": "━━━ Finansal performans ━━━",
        "margins_block": "━━━ Marjlar ve oranlar ━━━",
        "cashflow_block": "━━━ Nakit akışı ━━━",
        "branches_block": "━━━ Şubeler ({n} şube) ━━━",
        "risk_block": "━━━ Risk / kararlar ━━━",
        "periods_block": "━━━ Dönem karşılaştırması ━━━",
        "validation_block": "━━━ Veri doğrulama ━━━",
        "rules_block": "━━━ Yanıt kuralları (zorunlu) ━━━",
        "branch_strong": "En güçlü",
        "branch_weak": "En zayıf / zarar",
        "branch_na": "Yok",
        "branches_empty": "  Şube verisi yok",
        "decisions_empty": "  Yapılandırılmış karar yok",
        "periods_empty": "  Çok dönem verisi yok",
        "mem_topic": "Son konu",
        "mem_branch": "Son şube",
        "mem_metric": "Son metrik",
        "mem_header": "Konuşma bağlamı",
        "lbl_rev": "Gelir",
        "lbl_margin": "Marj",
        "lbl_np": "Net kâr",
        "loss_badge": " ⚠ zarar",
        "ocf_formula_note": "İşletme nakdi = net kâr + amortisman ± işletme sermayesi değişimi",
        "days": "gün",
        "rule_val_prefix": "Doğrulama durumu",
        "rule_val_pass": "Veri doğrulamayı geçti",
        "rule_val_warn": "Durum PASS değilse bunu ilk cümlede açıkça belirtin",
        "rule_no_fabricate": "Yukarıdaki verilerde olmayan rakamları kullanmayın.",
        "rule_missing": "Veri yoksa uydurmayın; mevcut olmadığını söyleyin.",
        "rule_followup": "Takip sorularında önceki konuşma bağlamını kullanın.",
        "rule_length": "Kullanıcı daha fazla detay istemedikçe 150–300 kelime hedefleyin.",
        "causal_header": "Nedensel şablon dayanağı (causal_items, gerçekleştirilmiş):",
        "legacy_header": "Sezgisel risk özeti (legacy):",
        "scaffold_fallback_note": "",
        "val_pass": "✓ Tamam — rakamlar güvenilir",
        "val_warn": "⚠ Uyarı — rakamlar dikkatle kullanılmalı",
        "val_fail": "✗ Başarısız — veri bütünlüğü sorunları",
        "val_unknown": "Bilinmiyor",
        "val_approx": "\n  ⚠ Yaklaşım tespit edildi: cari/hızlı oranlar daha az kesin olabilir",
        "val_blocking": "\n  🚫 Kritik: büyük kararlar için bu rakamlara güvenmeyin",
        "p_rev_latest": "Gelir (son dönem)",
        "p_rev_window": "Gelir (tüm pencere)",
        "p_np": "Net kâr",
        "p_gp": "Brüt kâr",
        "p_cogs": "SMM (COGS)",
        "p_opex": "Faaliyet giderleri",
        "p_mom_rev": "MoM değişim — gelir",
        "p_mom_np": "MoM değişim — net kâr",
        "m_gm": "Brüt marj",
        "m_nm": "Net marj",
        "m_om": "Faaliyet marjı",
        "m_er": "Gider oranı",
        "m_cr": "Cari oran",
        "m_qr": "Hızlı oran",
        "m_wc": "İşletme sermayesi",
        "m_dso": "DSO (gün)",
        "m_dpo": "DPO (gün)",
        "m_ccc": "CCC (gün)",
        "cf_ocf": "İşletme nakit akışı (OCF)",
        "cf_fcf": "Serbest nakit akışı",
        "cf_cash": "Nakit bakiyesi",
        "cf_eq": "Formül",
        "rule1": "1. İlk cümlede doğrudan yanıt verin",
        "rule2": "2. Yalnızca yukarıdaki verilerdeki rakamları kullanın",
        "rule3": "3. Nedenini açıklayın (kök neden)",
        "rule4": "4. Somut bir sonraki adım önerin",
        "period_row": "  {period}: gelir={rev} net_kâr={np} marj={margin}",
        "risk_score_lbl": "Risk skoru",
        "priority_lbl": "Öncelik",
    },
}

_INTENT_LABEL: dict[str, dict[str, str]] = {
    "ar": {
        "profitability": "ربحية",
        "cashflow": "تدفق نقدي",
        "risk": "مخاطر",
        "decision": "قرار",
        "branches": "فروع",
        "validation": "تحقق",
        "forecast": "توقعات",
        "statements": "قوائم",
        "comparisons": "مقارنات",
        "trend_explanation": "اتجاه",
        "action_priority": "أولوية",
        "executive_summary": "ملخص",
    },
    "en": {
        "profitability": "profitability",
        "cashflow": "cash flow",
        "risk": "risk",
        "decision": "decisions",
        "branches": "branches",
        "validation": "validation",
        "forecast": "forecast",
        "statements": "statements",
        "comparisons": "comparisons",
        "trend_explanation": "trends",
        "action_priority": "priorities",
        "executive_summary": "summary",
    },
    "tr": {
        "profitability": "karlılık",
        "cashflow": "nakit akışı",
        "risk": "risk",
        "decision": "kararlar",
        "branches": "şubeler",
        "validation": "doğrulama",
        "forecast": "tahmin",
        "statements": "tablolar",
        "comparisons": "karşılaştırma",
        "trend_explanation": "eğilimler",
        "action_priority": "öncelikler",
        "executive_summary": "özet",
    },
}


def _advisor_shell_lang(requested: str) -> tuple[str, str]:
    """Returns (shell_lang, realize_lang). Unknown scaffold lang → en with explicit note."""
    r = (requested or "").strip().lower()
    realize = r if r else "en"
    if r in _ADVISOR_LABELS:
        return r, realize
    return "en", realize


def detect_intent(question: str, last_intent: Optional[str] = None) -> str:
    """Detect intent from keyword matching, with follow-up memory fallback."""
    q = question.strip().lower()

    # Pure single-word follow-ups → always use last_intent (highest priority)
    _words = q.split()
    _pure_followup = (
        len(_words) <= 2
        and any(q.startswith(fw) or q == fw for fw in FOLLOWUP_AR + FOLLOWUP_EN)
        and last_intent
    )
    if _pure_followup:
        return last_intent

    # Score all intents first
    scores: dict[str, int] = {}
    for intent, keywords in INTENT_PATTERNS.items():
        scores[intent] = sum(1 for kw in keywords if kw in q)

    best = max(scores, key=lambda k: scores[k])

    # If we have a clear scored winner, use it — even for follow-up phrased questions
    if scores[best] > 0:
        # Tie-breaking: if top intents are tied, prefer non-trend_explanation
        top_score = scores[best]
        top_intents = [k for k,v in scores.items() if v == top_score]
        if len(top_intents) > 1 and "trend_explanation" in top_intents:
            # trend_explanation ties → prefer the other intent
            top_intents.remove("trend_explanation")
        return top_intents[0]

    # Pure follow-up (no topic keywords at all) → use session memory
    is_followup = (
        any(q.startswith(fw) for fw in FOLLOWUP_AR + FOLLOWUP_EN)
        and len(q.split()) <= 5
    )
    if is_followup and last_intent:
        return last_intent

    return last_intent or "executive_summary"


# ── Formatters ────────────────────────────────────────────────────────────────

def _fmt(v, decimals=1):
    if v is None:
        return "غير متاح" if False else "N/A"
    try:
        fv = float(v)
        av = abs(fv)
        sign = "-" if fv < 0 else ""
        if av >= 1_000_000:
            return f"{sign}{av/1_000_000:.{decimals}f}M"
        if av >= 1_000:
            return f"{sign}{av/1_000:.0f}K"
        return f"{sign}{av:.{decimals}f}"
    except Exception:
        return str(v)


def _pct(v):
    return f"{float(v):.1f}%" if v is not None else "N/A"


def _prompt_realized_ok(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    return not (
        s.startswith("[missing:")
        or s.startswith("[invalid_lang:")
        or s.startswith("[format_error:")
    )


# ── System prompt builder — production grade ─────────────────────────────────

def build_system_prompt(ctx: dict, lang: str = "ar", memory: Optional[dict] = None) -> str:
    """
    Build a comprehensive system prompt from the full VCFO context.
    Scaffold labels follow the requested language (ar/en/tr); unknown scaffold
    codes fall back to English with an explicit one-line notice.
    Decision grounding uses realize_causal_items(ctx[\"causal_items\"]); legacy English
    rationale from decisions[] is included only when no causal lines pass prompt filters.
    """
    shell_lang, realize_lang = _advisor_shell_lang(lang)
    L = _ADVISOR_LABELS[shell_lang]
    intent_lbl = _INTENT_LABEL.get(shell_lang, _INTENT_LABEL["en"])

    requested_raw = (lang or "").strip()
    scaffold_note = ""
    if requested_raw.lower() not in _ADVISOR_LABELS:
        scaffold_note = (
            f"[advisor: prompt scaffold language fallback en; requested_lang={requested_raw!r}]\n\n"
        )

    co     = ctx.get("company", {})
    dash   = ctx.get("dashboard", {})
    stmts  = ctx.get("statements", {})
    an     = ctx.get("analysis", {})
    cf     = ctx.get("cashflow", {})
    br     = ctx.get("branches", {})
    val    = ctx.get("validation", {})
    decs   = ctx.get("decisions", {})
    period = ctx.get("period", "?")
    window = ctx.get("window", "ALL")
    scope  = ctx.get("scope", "company")

    liq = an.get("liquidity", {})
    eff = an.get("efficiency", {})

    val_status = val.get("status", "UNKNOWN")
    val_errs   = val.get("errors", [])
    val_warns  = val.get("warnings", [])
    approx     = val.get("approximation_detected", False)
    blocking   = val.get("blocking", False)

    risk_score = decs.get("risk_score", "?")
    risk_prio  = decs.get("priority", "?")
    dec_list   = decs.get("decisions", [])

    branch_lines = []
    for b in (br.get("branches") or [])[:6]:
        loss_tag = L["loss_badge"] if b.get("is_loss") else ""
        branch_lines.append(
            f"  • {b['branch_name']}: {L['lbl_rev']}={_fmt(b['revenue'])}"
            f"  {L['lbl_margin']}={_pct(b['net_margin'])}"
            f"  {L['lbl_np']}={_fmt(b['net_profit'])}{loss_tag}"
        )
    branch_block = "\n".join(branch_lines) if branch_lines else L["branches_empty"]

    if val_status == "PASS":
        val_block = L["val_pass"]
    elif val_status == "WARNING":
        val_block = L["val_warn"]
        if val_warns:
            val_block += "\n  " + "\n  ".join(f"• {w}" for w in val_warns[:3])
    elif val_status == "FAIL":
        val_block = L["val_fail"]
        if val_errs:
            val_block += "\n  " + "\n  ".join(f"• {e}" for e in val_errs[:3])
    else:
        val_block = L["val_unknown"]
    if approx:
        val_block += L["val_approx"]
    if blocking:
        val_block += L["val_blocking"]

    realized = realize_causal_items(ctx.get("causal_items") or [], realize_lang or "en")
    causal_lines: list[str] = []
    for i, it in enumerate(realized[:8], 1):
        ct = it.get("change_text") or ""
        if not _prompt_realized_ok(ct):
            continue
        src = it.get("source", "")
        topic = it.get("topic", "")
        sev = it.get("severity", "")
        at = (it.get("action_text") or "").strip()
        line = f"  {i}. [{src}/{topic}/{sev}] {ct}"
        if _prompt_realized_ok(at):
            line += f" | action: {at}"
        causal_lines.append(line)

    legacy_lines = []
    for i, d in enumerate(dec_list[:3], 1):
        legacy_lines.append(
            f"  {i}. action_type={d.get('action_type', '?')} priority={d.get('priority', '?')} | {d.get('rationale', '')}"
        )
    legacy_block = "\n".join(legacy_lines) if legacy_lines else ""

    if causal_lines:
        dec_block = L["causal_header"] + "\n" + "\n".join(causal_lines)
    elif legacy_block:
        dec_block = L["legacy_header"] + "\n" + legacy_block
    else:
        dec_block = L["decisions_empty"]

    mem_block = ""
    if memory:
        parts = []
        li = memory.get("last_intent")
        if li:
            parts.append(f"{L['mem_topic']}: {intent_lbl.get(str(li), li)}")
        if memory.get("last_branch"):
            parts.append(f"{L['mem_branch']}: {memory['last_branch']}")
        if memory.get("last_metric"):
            parts.append(f"{L['mem_metric']}: {memory['last_metric']}")
        if parts:
            mem_block = f"\n{L['mem_header']}: {' | '.join(parts)}"

    _instr_map = {
        "ar": (
            "CRITICAL LANGUAGE RULE: أجب دائماً بالعربية.\n"
            "استخدم لغة عربية واضحة وبسيطة.\n"
            "لا تستخدم المصطلحات التقنية المعقدة.\n"
            "تحدث كمدير مالي يشرح لمدير تنفيذي.\n"
            "يمكنك استخدام اللهجة الخليجية المبسطة إذا بدا أن المستخدم يستخدمها."
        ),
        "tr": "CRITICAL: Always respond in professional Turkish.",
        "en": "Always respond in clear, direct English. Be professional and actionable.",
    }
    lang_instr = _instr_map.get(shell_lang, _instr_map["en"])

    pd_lines = []
    for pd_item in (an.get("periods_data") or [])[:6]:
        pd_lines.append(
            L["period_row"].format(
                period=pd_item.get("period", "?"),
                rev=_fmt(pd_item.get("revenue")),
                np=_fmt(pd_item.get("net_profit")),
                margin=_pct(pd_item.get("net_margin")),
            )
        )
    periods_block = " | ".join(pd_lines) if pd_lines else L["periods_empty"]

    rule_val_tail = L["rule_val_warn"] if val_status != "PASS" else L["rule_val_pass"]
    cf_formula = cf.get("formula") or L["ocf_formula_note"]

    return f"""{scaffold_note}{L["role"]}

{lang_instr}

{L["company_block"]}
{L["company_meta"].format(name=co.get("name", "?"), cur=co.get("currency", "USD"))}
{period} | {window} | {scope}
{mem_block}

{L["performance_block"]}
{L["p_rev_latest"]}:       {_fmt(dash.get("revenue_latest"))}
{L["p_rev_window"]}: {_fmt(dash.get("revenue"))}
{L["p_np"]}:             {_fmt(dash.get("np_latest"))}
{L["p_gp"]}:         {_fmt(dash.get("gross_profit"))}
{L["p_cogs"]}:  {_fmt(dash.get("cogs"))}
{L["p_opex"]}:   {_fmt(dash.get("expenses_opex"))}

{L["p_mom_rev"]}:  {_pct(dash.get("revenue_mom_pct"))} ({dash.get("revenue_direction", "?")})
{L["p_mom_np"]}:    {_pct(dash.get("net_profit_mom_pct"))} ({dash.get("np_direction", "?")})

{L["margins_block"]}
{L["m_gm"]}:    {_pct(stmts.get("gross_margin_pct"))}
{L["m_nm"]}:      {_pct(stmts.get("net_margin_pct"))}
{L["m_om"]}:           {_pct(stmts.get("operating_margin_pct"))}
{L["m_er"]}:         {_pct(stmts.get("expense_ratio"))}
{L["m_cr"]}:           {liq.get("current_ratio", "N/A")}x
{L["m_qr"]}:             {liq.get("quick_ratio", "N/A")}x
{L["m_wc"]}:       {_fmt(liq.get("working_capital"))}
{L["m_dso"]}:       {eff.get("dso_days", "N/A")} {L["days"]}
{L["m_dpo"]}:       {eff.get("dpo_days", "N/A")} {L["days"]}
{L["m_ccc"]}:       {eff.get("ccc_days", "N/A")} {L["days"]}

{L["cashflow_block"]}
{L["cf_ocf"]}:  {_fmt(cf.get("operating_cashflow"))}
{L["cf_fcf"]}:      {_fmt(cf.get("free_cashflow"))}
{L["cf_cash"]}:          {_fmt(cf.get("cash_balance"))}
{L["cf_eq"]}: {cf_formula}

{L["branches_block"].format(n=br.get("branch_count", 0))}
{L["branch_strong"]}: {br.get("strongest", L["branch_na"])} | {L["branch_weak"]}: {br.get("weakest", L["branch_na"])}
{branch_block}

{L["risk_block"]}
{L["risk_score_lbl"]}: {risk_score}/100 | {L["priority_lbl"]}: {risk_prio}
{dec_block}

{L["periods_block"]}
{periods_block}

{L["validation_block"]}
{val_block}

{L["rules_block"]}
{L["rule1"]}
{L["rule2"]}
{L["rule3"]}
{L["rule4"]}

{L["rule_val_prefix"]} = {val_status}: {rule_val_tail}
{L["rule_no_fabricate"]}
{L["rule_missing"]}
{L["rule_followup"]}
{L["rule_length"]}"""


# ── Quick actions — context-aware, priority-sorted ────────────────────────────

def build_quick_actions(ctx: dict, lang: str = "ar") -> list[dict]:
    """Generate 8 context-aware quick action buttons, priority-sorted."""
    decs  = ctx.get("decisions", {})
    val   = ctx.get("validation", {})
    dash  = ctx.get("dashboard", {})
    stmts = ctx.get("statements", {})
    br    = ctx.get("branches", {})

    risk_prio      = decs.get("priority", "LOW")
    nm             = stmts.get("net_margin_pct") or 0
    rev_dir        = dash.get("revenue_direction", "stable")
    val_status     = val.get("status", "PASS")
    has_branches   = (br.get("branch_count") or 0) > 0
    has_loss_branch = any(b.get("is_loss") for b in (br.get("branches") or []))
    weakest        = br.get("weakest", "")

    all_actions = {
        "ar": {
            "profit_why":    {"label": "لماذا تغيّر الربح؟",              "icon": "📊"},
            "action_first":  {"label": "ما الذي يجب فعله أولاً؟",        "icon": "🎯"},
            "risks":         {"label": "ما أكبر المخاطر؟",               "icon": "⚠️"},
            "cashflow":      {"label": "كيف حال التدفق النقدي؟",         "icon": "💵"},
            "weakest_branch":{"label": f"لماذا {weakest or 'الفرع'} ضعيف؟", "icon": "🏢"},
            "all_branches":  {"label": "قارن الفروع",                    "icon": "🔀"},
            "data_ok":       {"label": "هل البيانات موثوقة؟",            "icon": "✅"},
            "summary":       {"label": "لخّص وضع الشركة",               "icon": "📋"},
            "reduce_cost":   {"label": "كيف أخفض التكاليف؟",            "icon": "✂️"},
            "compare_3m":    {"label": "قارن آخر 3 شهور",               "icon": "📈"},
            "board_report":  {"label": "لخّص تقرير المجلس",             "icon": "📑"},
            "growth_driver": {"label": "ما الذي يقود النمو؟",            "icon": "🚀"},
        },
        "en": {
            "profit_why":    {"label": "Why did profit change?",           "icon": "📊"},
            "action_first":  {"label": "What should I do first?",         "icon": "🎯"},
            "risks":         {"label": "What are the top risks?",         "icon": "⚠️"},
            "cashflow":      {"label": "How is cash flow?",               "icon": "💵"},
            "weakest_branch":{"label": f"Why is {weakest or 'the branch'} weak?", "icon": "🏢"},
            "all_branches":  {"label": "Compare branches",                "icon": "🔀"},
            "data_ok":       {"label": "Is the data reliable?",           "icon": "✅"},
            "summary":       {"label": "Summarize company status",        "icon": "📋"},
            "reduce_cost":   {"label": "How to reduce costs?",            "icon": "✂️"},
            "compare_3m":    {"label": "Compare last 3 months",           "icon": "📈"},
            "board_report":  {"label": "Summarize board report",          "icon": "📑"},
            "growth_driver": {"label": "What is driving growth?",         "icon": "🚀"},
        },
        "tr": {
            "profit_why":    {"label": "Kâr neden değişti?",              "icon": "📊"},
            "action_first":  {"label": "Önce ne yapmalıyım?",             "icon": "🎯"},
            "risks":         {"label": "En büyük riskler neler?",         "icon": "⚠️"},
            "cashflow":      {"label": "Nakit akışı nasıl?",              "icon": "💵"},
            "weakest_branch":{"label": f"{weakest or 'Şube'} neden zayıf?", "icon": "🏢"},
            "all_branches":  {"label": "Şubeleri karşılaştır",            "icon": "🔀"},
            "data_ok":       {"label": "Veriler güvenilir mi?",           "icon": "✅"},
            "summary":       {"label": "Şirket durumunu özetle",          "icon": "📋"},
            "reduce_cost":   {"label": "Maliyetler nasıl azaltılır?",     "icon": "✂️"},
            "compare_3m":    {"label": "Son 3 ayı karşılaştır",           "icon": "📈"},
            "board_report":  {"label": "Yönetim kurulu raporu özeti",     "icon": "📑"},
            "growth_driver": {"label": "Büyümeyi ne sağlıyor?",          "icon": "🚀"},
        },
    }

    pool = all_actions.get(lang, all_actions["ar"])

    # Priority order based on context
    priority_ids: list[str] = []

    # Critical situations first
    if val_status in ("FAIL", "WARNING"):
        priority_ids.append("data_ok")
    if risk_prio == "HIGH":
        priority_ids += ["action_first", "risks"]
    if nm < 0:
        priority_ids += ["profit_why", "reduce_cost"]
    elif nm < 5:
        priority_ids += ["reduce_cost", "profit_why"]
    if has_loss_branch:
        priority_ids.append("weakest_branch")
    if rev_dir == "declining":
        priority_ids.append("profit_why")

    # Fill remaining slots
    all_order = ["profit_why","action_first","risks","cashflow",
                 "weakest_branch","all_branches","data_ok","summary",
                 "reduce_cost","compare_3m","board_report","growth_driver"]

    seen = set()
    ordered = []
    for pid in priority_ids + all_order:
        if pid not in seen and pid in pool:
            seen.add(pid)
            ordered.append({"id": pid, **pool[pid]})

    return ordered[:8]


def get_followup_suggestions(intent: str, lang: str = "ar") -> list[str]:
    """Return 3 natural follow-up question suggestions after an answer."""
    suggestions = {
        "profitability": {
            "ar": ["ليش انخفض الهامش؟", "هل المشكلة في التكلفة أو الإيراد؟", "قارن آخر 3 شهور"],
            "en": ["Why did margin drop?", "Is it a cost or revenue problem?", "Compare last 3 months"],
        },
        "cashflow": {
            "ar": ["كيف أحسن التحصيل؟", "هل التدفق النقدي خطير؟", "اشرح رأس المال العامل"],
            "en": ["How to improve collections?", "Is cash flow critical?", "Explain working capital"],
        },
        "branches": {
            "ar": ["ليش هذا الفرع خاسر؟", "هل يستحق الإغلاق؟", "قارن كل الفروع"],
            "en": ["Why is this branch losing?", "Should it be closed?", "Compare all branches"],
        },
        "risk": {
            "ar": ["ما أخطر مشكلة الآن؟", "هل الوضع يستحق قلق؟", "ايش أول قرار أسويه؟"],
            "en": ["What's the most critical issue?", "Is this serious?", "What's the first action?"],
        },
        "decision": {
            "ar": ["كيف أطبق هذا القرار؟", "ما التوقيت المناسب؟", "ما النتائج المتوقعة؟"],
            "en": ["How to implement this?", "What's the timeline?", "What results to expect?"],
        },
        "executive_summary": {
            "ar": ["أي جانب الأهم؟", "ما أكبر مخاطرة؟", "قارن بالشهر الماضي"],
            "en": ["Which area is most critical?", "What's the biggest risk?", "Compare to last month"],
        },
    }
    pool = suggestions.get(intent, suggestions["executive_summary"])
    return pool.get(lang, pool.get("ar", []))
