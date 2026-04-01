"""
vcfo_ai_advisor.py — VCFO AI CFO Answer Engine (Production Grade)

Builds dense, grounded system prompts from full VCFO context.
Handles natural Arabic conversation including follow-up and dialectal patterns.
Routes questions to correct data domains.
"""
from __future__ import annotations
from typing import Optional


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


# ── System prompt builder — production grade ─────────────────────────────────

def build_system_prompt(ctx: dict, lang: str = "ar", memory: Optional[dict] = None) -> str:
    """
    Build a comprehensive system prompt from the full VCFO context.
    Accepts session memory to handle follow-up questions correctly.
    """
    co     = ctx.get("company", {})
    dash   = ctx.get("dashboard", {})
    stmts  = ctx.get("statements", {})
    an     = ctx.get("analysis", {})
    cf     = ctx.get("cashflow", {})
    br     = ctx.get("branches", {})
    val    = ctx.get("validation", {})
    decs   = ctx.get("decisions", {})
    fcast  = ctx.get("forecast", {})
    board  = ctx.get("board_report", {})
    period = ctx.get("period", "?")
    window = ctx.get("window", "ALL")
    scope  = ctx.get("scope", "company")

    liq = an.get("liquidity", {})
    eff = an.get("efficiency", {})
    prof = an.get("profitability", {})
    trends = an.get("trends", {})

    val_status = val.get("status", "UNKNOWN")
    val_errs   = val.get("errors", [])
    val_warns  = val.get("warnings", [])
    approx     = val.get("approximation_detected", False)
    blocking   = val.get("blocking", False)

    risk_score = decs.get("risk_score", "?")
    risk_prio  = decs.get("priority", "?")
    dec_list   = decs.get("decisions", [])

    # Build branch block
    branch_lines = []
    for b in (br.get("branches") or [])[:6]:
        loss_tag = " ⚠ خسارة" if b.get("is_loss") else ""
        branch_lines.append(
            f"  • {b['branch_name']}: إيراد={_fmt(b['revenue'])}"
            f"  هامش={_pct(b['net_margin'])}"
            f"  صافي ربح={_fmt(b['net_profit'])}{loss_tag}"
        )
    branch_block = "\n".join(branch_lines) if branch_lines else "  لا توجد بيانات فروع"

    # Build validation block
    if val_status == "PASS":
        val_block = "✓ سليمة — يمكن الاعتماد على الأرقام"
    elif val_status == "WARNING":
        val_block = "⚠ تحذير — الأرقام مقبولة لكن بحذر"
        if val_warns:
            val_block += "\n  " + "\n  ".join(f"• {w}" for w in val_warns[:3])
    elif val_status == "FAIL":
        val_block = "✗ فشل — هناك مشاكل في سلامة البيانات"
        if val_errs:
            val_block += "\n  " + "\n  ".join(f"• {e}" for e in val_errs[:3])
    else:
        val_block = "غير معروف"
    if approx:
        val_block += "\n  ⚠ تقريب مكتشف: نسبة التداول والنسبة السريعة قد تكون غير دقيقة"
    if blocking:
        val_block += "\n  🚫 مشكلة حرجة: لا تعتمد على هذه الأرقام لقرارات مهمة"

    # Decisions block
    dec_lines = []
    for i, d in enumerate(dec_list[:3], 1):
        dec_lines.append(f"  {i}. {d.get('action_type','?')} ({d.get('priority','?')}): {d.get('rationale','')}")
    dec_block = "\n".join(dec_lines) if dec_lines else "  لا توجد قرارات"

    # Memory context
    mem_block = ""
    if memory:
        parts = []
        if memory.get("last_intent"): parts.append(f"آخر موضوع: {memory['last_intent']}")
        if memory.get("last_branch"): parts.append(f"آخر فرع: {memory['last_branch']}")
        if memory.get("last_metric"): parts.append(f"آخر مقياس: {memory['last_metric']}")
        if parts:
            mem_block = f"\nسياق المحادثة السابقة: {' | '.join(parts)}"

    lang_instr = {
        "ar": (
            "CRITICAL LANGUAGE RULE: أجب دائماً بالعربية.\n"
            "استخدم لغة عربية واضحة وبسيطة.\n"
            "لا تستخدم المصطلحات التقنية المعقدة.\n"
            "تحدث كمدير مالي يشرح لمدير تنفيذي.\n"
            "يمكنك استخدام اللهجة الخليجية المبسطة إذا بدا أن المستخدم يستخدمها."
        ),
        "tr": "CRITICAL: Always respond in professional Turkish.",
        "en": "Always respond in clear, direct English. Be professional and actionable.",
    }.get(lang, "Always respond in English.")

    # Per-period breakdown
    pd_lines = []
    for pd_item in (an.get("periods_data") or [])[:6]:
        pd_lines.append(
            f"  {pd_item.get('period','?')}: إيراد={_fmt(pd_item.get('revenue'))} "
            f"ربح={_fmt(pd_item.get('net_profit'))} هامش={_pct(pd_item.get('net_margin'))}"
        )
    periods_block = " | ".join(pd_lines) if pd_lines else "  لا توجد بيانات فترات متعددة"

    return f"""أنت المستشار المالي الذكي المدمج في منصة VCFO.
لديك صلاحية الوصول لكامل البيانات المالية للشركة.

{lang_instr}

━━━ بيانات الشركة ━━━
الشركة: {co.get('name', '?')} | العملة: {co.get('currency', 'USD')}
الفترة: {period} | النافذة: {window} | النطاق: {scope}
{mem_block}

━━━ الأداء المالي ━━━
الإيراد (الفترة):       {_fmt(dash.get('revenue_latest'))}
الإيراد (النافذة كاملة): {_fmt(dash.get('revenue'))}
صافي الربح:             {_fmt(dash.get('np_latest'))}
الربح الإجمالي:         {_fmt(dash.get('gross_profit'))}
تكلفة البضاعة (COGS):  {_fmt(dash.get('cogs'))}
المصروفات التشغيلية:   {_fmt(dash.get('expenses_opex'))}

التغيير MoM - الإيراد:  {_pct(dash.get('revenue_mom_pct'))} ({dash.get('revenue_direction', '?')})
التغيير MoM - الربح:    {_pct(dash.get('net_profit_mom_pct'))} ({dash.get('np_direction', '?')})

━━━ الهوامش والنسب ━━━
هامش الربح الإجمالي:    {_pct(stmts.get('gross_margin_pct'))}
هامش الربح الصافي:      {_pct(stmts.get('net_margin_pct'))}
هامش التشغيل:           {_pct(stmts.get('operating_margin_pct'))}
نسبة المصروفات:         {_pct(stmts.get('expense_ratio'))}
نسبة التداول:           {liq.get('current_ratio', 'N/A')}x
نسبة سريعة:             {liq.get('quick_ratio', 'N/A')}x
رأس المال العامل:       {_fmt(liq.get('working_capital'))}
DSO (أيام القبض):       {eff.get('dso_days', 'N/A')} يوم
DPO (أيام الدفع):       {eff.get('dpo_days', 'N/A')} يوم
CCC (دورة النقد):       {eff.get('ccc_days', 'N/A')} يوم

━━━ التدفق النقدي ━━━
التدفق التشغيلي (OCF):  {_fmt(cf.get('operating_cashflow'))}
التدفق الحر (FCF):      {_fmt(cf.get('free_cashflow'))}
الرصيد النقدي:          {_fmt(cf.get('cash_balance'))}
المعادلة: {cf.get('formula', 'OCF = صافي الربح + إهلاك ± تغيرات رأس المال العامل')}

━━━ الفروع ({br.get('branch_count', 0)} فروع) ━━━
الأقوى: {br.get('strongest', 'غير متاح')} | الأضعف / الخاسر: {br.get('weakest', 'غير متاح')}
{branch_block}

━━━ تقييم المخاطر ━━━
درجة الخطر: {risk_score}/100 | الأولوية: {risk_prio}
{dec_block}

━━━ مقارنة الفترات ━━━
{periods_block}

━━━ سلامة البيانات ━━━
{val_block}

━━━ قواعد الإجابة (إلزامية) ━━━
1. الجواب المباشر: أول جملة تجيب على السؤال مباشرة
2. الدليل الرقمي: استخدم الأرقام الحقيقية من البيانات أعلاه فقط
3. التفسير: اشرح لماذا حدث هذا (السبب الجذري)
4. الإجراء المطلوب: أعطِ خطوة عملية واضحة

حالة التحقق = {val_status}: {"إذا لم تكن PASS، اذكر ذلك بوضوح في أول إجابتك" if val_status != "PASS" else "البيانات سليمة"}
لا تستخدم أرقاماً غير موجودة في البيانات أعلاه.
إذا كانت البيانات غير متاحة: قل "هذه البيانات غير متاحة حالياً" ولا تخترع أرقاماً.
الأسئلة المتابعة (ليش؟ طيب؟ وش السبب؟): استخدم سياق المحادثة السابق للإجابة.
الطول المثالي: 150-300 كلمة إلا إذا طُلب تفصيل أكثر."""


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
