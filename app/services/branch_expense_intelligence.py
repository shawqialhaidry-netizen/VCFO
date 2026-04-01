"""
branch_expense_intelligence.py

Branch-level Expense Intelligence Layer.
Reads classified TB line items from disk (normalized CSV) to produce:
  - expense_breakdown: per-category amounts + % of revenue per branch
  - expense_insights:  dominant cost, abnormal ratios, pressure signals
  - top_movers:        largest MoM expense category increases

NO financial recalculation.
Reuses _classify_item from expense_engine + _load_df from analysis pipeline.
"""
from __future__ import annotations
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Import shared classification helper (no duplication) ─────────────────────
from app.services.expense_engine import _classify_item, CATEGORY_DEFS

# ── Category display labels (EN/AR/TR) ────────────────────────────────────────
_CAT_LABELS: dict[str, dict[str, str]] = {
    "cogs":             {"en": "COGS",              "ar": "تكلفة البضاعة",   "tr": "SMM"},
    "payroll":          {"en": "Payroll",            "ar": "الرواتب",         "tr": "Bordro"},
    "rent_facilities":  {"en": "Rent & Facilities",  "ar": "الإيجار والمرافق","tr": "Kira ve Tesisler"},
    "fleet_vehicle":    {"en": "Fleet / Vehicles",   "ar": "الأسطول والمركبات","tr":"Filo / Araçlar"},
    "fuel":             {"en": "Fuel",               "ar": "الوقود",          "tr": "Yakıt"},
    "maintenance":      {"en": "Maintenance",        "ar": "الصيانة",         "tr": "Bakım"},
    "logistics":        {"en": "Logistics",          "ar": "اللوجستيات",      "tr": "Lojistik"},
    "admin_other":      {"en": "Admin & Other",      "ar": "إداري وأخرى",     "tr": "İdari & Diğer"},
}

def _cat_label(cat: str, lang: str) -> str:
    return _CAT_LABELS.get(cat, {}).get(lang) or _CAT_LABELS.get(cat, {}).get("en") or cat


# ── Per-row expense categorization from normalized TB dataframe ───────────────

def _categorize_from_stmt(stmt: dict) -> dict[str, float]:
    """
    Classify statement_engine output into expense categories.
    Returns: {category: total_amount}

    Reads from statement_engine output ONLY — no debit/credit arithmetic.
    All amounts come from is_.expenses.items and is_.cogs.items which were
    computed by financial_statements.py (the single source of truth).
    """
    totals: dict[str, float] = defaultdict(float)
    is_ = stmt.get("income_statement", {})

    # Read expense line items from statement_engine output
    for section_key, mtype in (("expenses", "expenses"), ("cogs", "cogs")):
        items = is_.get(section_key, {}).get("items", [])
        for item in items:
            code   = str(item.get("account_code", "") or "").strip()
            name   = str(item.get("account_name", "") or "").strip()
            amount = float(item.get("amount", 0) or 0)
            if amount <= 0:
                continue
            cat, _ = _classify_item(code, name, mtype)
            totals[cat] += amount

    return dict(totals)


def _categorize_df(df) -> dict[str, float]:
    """
    Legacy shim: builds a minimal statement from raw df using account_classifier
    then delegates to _categorize_from_stmt. Preserves compatibility with callers
    that still pass raw DataFrames, while routing arithmetic through statement_engine.
    """
    from app.services.account_classifier import classify_dataframe
    from app.services.financial_statements import build_statements, statements_to_dict
    try:
        classified = classify_dataframe(df)
        fs  = build_statements(classified, company_id="_branch_", period="_")
        return _categorize_from_stmt(statements_to_dict(fs))
    except Exception:
        return {}


# ── Expense breakdown builder ─────────────────────────────────────────────────

def _build_expense_breakdown(
    branch_name: str,
    period_dfs: list[tuple[str, object]],   # [(period, df), ...]
    lang: str,
) -> dict:
    """
    Build latest-period expense group breakdown for one branch.
    Returns: {branch_name, expense_groups: [{category, label, amount, pct_of_revenue}]}

    Revenue and expense amounts are read from statement_engine output ONLY.
    No arithmetic on raw debit/credit columns.
    """
    if not period_dfs:
        return {"branch_name": branch_name, "expense_groups": []}

    from app.services.account_classifier import classify_dataframe
    from app.services.financial_statements import build_statements, statements_to_dict

    # Use latest period
    latest_period, latest_df = sorted(period_dfs, key=lambda x: x[0])[-1]

    # Build statement via statement_engine — single source of truth for all amounts
    try:
        classified = classify_dataframe(latest_df)
        fs   = build_statements(classified, company_id="_branch_", period=latest_period)
        stmt = statements_to_dict(fs)
    except Exception:
        stmt = {}

    # Revenue from statement_engine output — NOT from raw debit/credit
    is_  = stmt.get("income_statement", {})
    rev  = float(is_.get("revenue", {}).get("total") or 0)

    cat_totals = _categorize_from_stmt(stmt)
    groups = []
    for cat, amt in sorted(cat_totals.items(), key=lambda x: -x[1]):
        pct = round(amt / rev * 100, 2) if rev > 0 else None
        groups.append({
            "category":       cat,
            "label":          _cat_label(cat, lang),
            "amount":         round(amt, 2),
            "pct_of_revenue": pct,
        })

    return {
        "branch_name":    branch_name,
        "latest_period":  period_dfs[-1][0] if period_dfs else None,
        "revenue":        round(rev, 2),
        "expense_groups": groups,
    }


# ── Expense insights builder ──────────────────────────────────────────────────

def _build_expense_insights(breakdown: dict, lang: str) -> list[dict]:
    """
    Detect: dominant cost, abnormal expense ratio, cost pressure vs revenue.
    Reads only from breakdown — no new calculations.
    """
    ar  = lang == "ar"; tr_ = lang == "tr"
    insights = []
    groups  = breakdown.get("expense_groups", [])
    rev     = breakdown.get("revenue") or 0
    branch  = breakdown.get("branch_name", "")

    if not groups or not rev:
        return []

    total_exp = sum(g["amount"] for g in groups)
    exp_ratio = round(total_exp / rev * 100, 2) if rev else None

    # ── Dominant cost category (top group > 40% of total expenses) ───────────
    if groups:
        top = groups[0]
        top_pct_of_exp = round(top["amount"] / total_exp * 100, 1) if total_exp else 0
        if top_pct_of_exp > 40:
            cat_lbl = top["label"]
            pct_rev = top.get("pct_of_revenue") or 0
            if ar:
                what = f"فئة {cat_lbl} تُمثّل {top_pct_of_exp:.0f}٪ من إجمالي مصروفات فرع {branch} ({pct_rev:.1f}٪ من الإيرادات)."
                why  = f"تركّز المصروفات في فئة واحدة يزيد من حساسية الفرع لأي ارتفاع في تكاليف {cat_lbl}."
            elif tr_:
                what = f"{cat_lbl} kalemi, {branch} şubesinin toplam giderlerinin {top_pct_of_exp:.0f}%'ini oluşturuyor (gelirin {pct_rev:.1f}%'i)."
                why  = f"Giderlerin tek bir kategoride yoğunlaşması, şubeyi {cat_lbl} maliyet artışlarına karşı savunmasız kılıyor."
            else:
                what = f"{cat_lbl} accounts for {top_pct_of_exp:.0f}% of total expenses in {branch} ({pct_rev:.1f}% of revenue)."
                why  = f"Concentration in a single cost category makes the branch sensitive to any increase in {cat_lbl} costs."
            insights.append({
                "type":          f"dominant_{top['category']}",
                "severity":      "medium",
                "what_happened": what,
                "why":           why,
                "drivers":       [top["category"]],
            })

    # ── Abnormal total expense ratio (> 70%) ──────────────────────────────────
    if exp_ratio and exp_ratio > 70:
        sev = "high" if exp_ratio > 80 else "medium"
        if ar:
            what = f"نسبة المصروفات الإجمالية لفرع {branch} بلغت {exp_ratio:.1f}٪ من الإيرادات — تتجاوز العتبة الحرجة."
            why  = "نسبة مصروفات بهذا المستوى تُضيّق هامش التشغيل وتزيد من مخاطر الخسارة عند أي تراجع في الإيرادات."
        elif tr_:
            what = f"{branch} şubesinin toplam gider oranı {exp_ratio:.1f}% — kritik eşiği aşıyor."
            why  = "Bu düzeyde bir gider oranı, faaliyet marjını daraltır ve gelir düşüşü durumunda zarar riskini artırır."
        else:
            what = f"Total expense ratio for {branch} reached {exp_ratio:.1f}% of revenue — above the critical threshold."
            why  = "An expense ratio at this level compresses operating margin and increases loss risk on any revenue decline."
        insights.append({
            "type":          "abnormal_expense_ratio",
            "severity":      sev,
            "what_happened": what,
            "why":           why,
            "drivers":       [g["category"] for g in groups[:2]],
        })

    # ── Cost pressure: expenses growing faster than revenue signal ────────────
    # (derived from the presence of high cogs + payroll together)
    heavy_cats = {g["category"] for g in groups if (g.get("pct_of_revenue") or 0) > 20}
    if len(heavy_cats) >= 2:
        labels_str = ", ".join(_cat_label(c, lang) for c in list(heavy_cats)[:2])
        if ar:
            what = f"فرع {branch} يتحمّل ضغطاً تكاليفياً مزدوجاً من: {labels_str}."
            why  = "تراكم فئتين أو أكثر من المصروفات فوق 20٪ من الإيرادات يُشكّل ضغطاً هيكلياً على الربحية."
        elif tr_:
            what = f"{branch} şubesi çift yönlü maliyet baskısı yaşıyor: {labels_str}."
            why  = "Gelirin %20'sinden fazlasını oluşturan iki veya daha fazla gider kategorisi, kârlılık üzerinde yapısal baskı oluşturur."
        else:
            what = f"{branch} faces dual cost pressure from: {labels_str}."
            why  = "Two or more expense categories each exceeding 20% of revenue creates structural pressure on profitability."
        insights.append({
            "type":          "dual_cost_pressure",
            "severity":      "medium",
            "what_happened": what,
            "why":           why,
            "drivers":       list(heavy_cats),
        })

    return insights


# ── Top movers builder (MoM) ──────────────────────────────────────────────────

def _build_top_movers(
    branch_name: str,
    period_dfs: list[tuple[str, object]],
    lang: str,
) -> list[dict]:
    """
    Detect largest MoM expense category increases.
    Requires at least 2 periods.
    """
    ar  = lang == "ar"; tr_ = lang == "tr"

    sorted_periods = sorted(period_dfs, key=lambda x: x[0])
    if len(sorted_periods) < 2:
        return []

    _, prev_df   = sorted_periods[-2]
    _, latest_df = sorted_periods[-1]

    prev_cats   = _categorize_df(prev_df)
    latest_cats = _categorize_df(latest_df)

    movers = []
    all_cats = set(prev_cats) | set(latest_cats)
    for cat in all_cats:
        prev_amt   = prev_cats.get(cat, 0)
        latest_amt = latest_cats.get(cat, 0)
        if prev_amt <= 0:
            continue
        change_pct = round((latest_amt - prev_amt) / abs(prev_amt) * 100, 1)
        if change_pct > 5:   # Only surface meaningful increases
            label = _cat_label(cat, lang)
            if ar:
                desc = f"مصروفات {label} ارتفعت {change_pct:.1f}٪ مقارنةً بالشهر الماضي في فرع {branch_name}."
            elif tr_:
                desc = f"{branch_name} şubesinde {label} giderleri geçen aya göre {change_pct:.1f}% arttı."
            else:
                desc = f"{label} expenses increased {change_pct:.1f}% MoM in {branch_name}."
            movers.append({
                "category":    cat,
                "label":       label,
                "prev_amount": round(prev_amt, 2),
                "curr_amount": round(latest_amt, 2),
                "change_pct":  change_pct,
                "description": desc,
            })

    movers.sort(key=lambda x: -x["change_pct"])
    return movers[:5]


# ── Main entry point ──────────────────────────────────────────────────────────

def build_branch_expense_intelligence(
    branches: list[dict],   # [{branch_id, branch_name, uploads: [TrialBalanceUpload]}]
    load_df_fn,             # callable(upload) → pd.DataFrame | None
    lang: str = "en",
) -> dict:
    """
    Build branch-level expense intelligence for all branches.

    Args:
        branches:    list of {branch_id, branch_name, uploads}
        load_df_fn:  _load_df function from analysis.py (no reimplementation)
        lang:        "en" | "ar" | "tr"

    Returns:
        {
            expense_breakdown: [per-branch breakdown],
            expense_insights:  [per-branch insights],
            top_movers:        [per-branch movers],
        }
    """
    safe_lang = lang if lang in ("en", "ar", "tr") else "en"
    result: dict = {
        "expense_breakdown": [],
        "expense_insights":  [],
        "top_movers":        [],
    }

    for branch in branches:
        branch_id   = branch.get("branch_id", "")
        branch_name = branch.get("branch_name", "unknown")
        uploads     = branch.get("uploads", [])

        if not uploads:
            continue

        # Build period → df map using the shared _load_df (no reimplementation)
        period_dfs: list[tuple[str, object]] = []
        for upload in uploads:
            try:
                df = load_df_fn(upload)
                if df is not None and not df.empty:
                    period = getattr(upload, "period", None) or ""
                    period_dfs.append((period, df))
            except Exception as exc:
                logger.warning("branch_expense: load_df failed branch=%s upload=%s: %s",
                               branch_id, getattr(upload, "id", "?"), exc)

        if not period_dfs:
            continue

        # Expense breakdown
        try:
            bd = _build_expense_breakdown(branch_name, period_dfs, safe_lang)
            result["expense_breakdown"].append(bd)
        except Exception as exc:
            logger.warning("branch_expense: breakdown failed branch=%s: %s", branch_id, exc)
            result["expense_breakdown"].append({"branch_name": branch_name, "expense_groups": []})

        # Expense insights
        try:
            ins = _build_expense_insights(
                result["expense_breakdown"][-1], safe_lang
            )
            if ins:
                result["expense_insights"].append({
                    "branch_id":   branch_id,
                    "branch_name": branch_name,
                    "insights":    ins,
                })
        except Exception as exc:
            logger.warning("branch_expense: insights failed branch=%s: %s", branch_id, exc)

        # Top movers
        try:
            mv = _build_top_movers(branch_name, period_dfs, safe_lang)
            if mv:
                result["top_movers"].append({
                    "branch_id":   branch_id,
                    "branch_name": branch_name,
                    "movers":      mv,
                })
        except Exception as exc:
            logger.warning("branch_expense: movers failed branch=%s: %s", branch_id, exc)

    return result
