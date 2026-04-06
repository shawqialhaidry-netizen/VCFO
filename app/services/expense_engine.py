"""
expense_engine.py — Phase 21 (upgraded from Phase 12.5)
CFO-grade Expense Intelligence Layer.

Reads ONLY from existing financial_statements pipeline output.
No new financial calculations. No duplicate logic.

Classification hierarchy (per Adjustment 1):
  1. mapped_type  → confirms broad category (cogs / expenses / tax)
  2. account_code → sub-category signal (if 4-digit ranges available)
  3. keyword      → fallback on account_name

Adjustments applied:
  - top_items + other_total instead of full items arrays (perf + SaaS)
  - threshold_source: "internal_default" for future configurability
  - decision_hint field on every insight
  - expense_heatmap block per group
  - branch_comparison uses branch_financials kpis from canonical branch statements (caller)
"""
from __future__ import annotations
from typing import Optional

from app.services.metric_definitions import (
    cogs_ratio_pct,
    opex_ratio_pct,
    total_cost_ratio_pct,
)


# ── Category definitions ──────────────────────────────────────────────────────
# (category_key, label_i18n_key, icon, mapped_type_values, code_prefixes, keywords)
CATEGORY_DEFS: list[tuple] = [
    ("cogs",         "exp_group_cogs",         "🏭",
     ["cogs"],          [],
     ["تكلفة البضاعة","cost of goods","بضاعة مباعة","تكلفة المبيعات","direct cost"]),

    ("payroll",      "exp_group_payroll",       "👔",
     ["expenses"],      ["50","51","60"],          # 60xx = salaries/HR in 6xxx datasets
     ["رواتب","راتب","أجور","salary","salaries","wages","payroll","مرتبات",
      "عمالة","عمال","labor","labour","hr","overtime","benefits","social security",
      "employee"]),

    ("rent_facilities","exp_group_rent",        "🏢",
     ["expenses"],      ["52","53","61"],          # 61xx = rent/utilities in 6xxx datasets
     ["إيجار","rent","lease","اجار","facilities","مبنى","مكتب",
      "electricity","water","utilities","internet","communication"]),

    ("fleet_vehicle", "exp_group_fleet",        "🚛",
     ["expenses"],      ["54","55","62"],          # 62xx = vehicle in 6xxx datasets
     ["سيارات","مركبات","fleet","vehicle","araç","شاحنة","شاحنات",
      "vehicle lease","vehicle depreciation","vehicle insurance"]),

    ("fuel",          "exp_group_fuel",         "⛽",
     ["expenses"],      ["56","63"],              # 63xx = fuel in 6xxx datasets
     ["وقود","بنزين","ديزل","fuel","petrol","diesel","gas","غاز"]),

    ("maintenance",   "exp_group_maintenance",  "🔧",
     ["expenses"],      ["57","64"],              # 64xx = maintenance in 6xxx datasets
     ["صيانة","إصلاح","maintenance","repair","تصليح","spare parts","equipment repair"]),

    ("depreciation",  "exp_group_depreciation", "📉",
     ["expenses"],      ["58","59"],
     ["استهلاك","إهلاك","depreciation","amortization","amortisation"]),

    ("admin_other",   "exp_group_admin",        "📋",
     ["expenses","tax"],["65"],                  # 65xx = admin/overhead only
     ["إدارية","إدارة","admin","administrative","general","عامة","متنوعة",
      "تأمين","insurance","ضريبة","tax","مصاريف","overhead",
      "office supplies","software","legal","consulting","accounting","miscellaneous"]),

    ("logistics",     "exp_group_logistics",    "📦",
     ["expenses"],      ["66"],                  # 66xx = field ops/logistics in 6xxx datasets
     ["loading","transportation","container","handling","field operations",
      "logistics","شحن","نقل","لوجستي"]),
]

# Build keyword lookup (longest-match first)
_KW_LOOKUP: list[tuple[str, str, str]] = []
for _ck, _nk, _ic, _mt, _cp, _kws, *_ in CATEGORY_DEFS:
    for _kw in _kws:
        _KW_LOOKUP.append((_kw.lower(), _ck, _nk))
_KW_LOOKUP.sort(key=lambda x: -len(x[0]))

# Build code-prefix lookup
_CODE_LOOKUP: list[tuple[str, str, str]] = []
for _ck, _nk, _ic, _mt, _cp, _kws, *_ in CATEGORY_DEFS:
    for _pfx in _cp:
        _CODE_LOOKUP.append((_pfx, _ck, _nk))
_CODE_LOOKUP.sort(key=lambda x: -len(x[0]))

# Convenience maps
_CAT_ICON  = {d[0]: d[2] for d in CATEGORY_DEFS}
_CAT_I18N  = {d[0]: d[1] for d in CATEGORY_DEFS}

# ── Internal thresholds (generic financial context) ──────────────────────────
# threshold_source: "internal_default" allows future override
THRESHOLDS = {
    "expense_ratio_pct":   {"target_max": 75.0, "warning": 65.0, "critical": 80.0},
    "cogs_ratio_pct":      {"target_max": 60.0, "warning": 55.0, "critical": 65.0},
    "payroll_ratio_pct":   {"target_max": 35.0, "warning": 30.0, "critical": 40.0},
    "fuel_ratio_pct":      {"target_max": 15.0, "warning": 12.0, "critical": 18.0},
}
THRESHOLD_SOURCE = "internal_default"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _r2(v) -> Optional[float]:
    try: return round(float(v), 2)
    except: return None

def _pct(value, total) -> Optional[float]:
    """Return signed percentage. Negative margin stays negative.
    Zero/null denominator returns None (not zero, not fake).
    """
    if total is None or abs(total) < 0.001:
        return None
    return round(value / total * 100, 2)

def _mom(curr, prev) -> Optional[float]:
    if prev and abs(prev) > 0.001:
        return round((curr - prev) / abs(prev) * 100, 2)
    return None

def _direction(variance_pct) -> str:
    if variance_pct is None: return "stable"
    if variance_pct >  3.0:  return "increasing"
    if variance_pct < -3.0:  return "declining"
    return "stable"

def _heatmap(ratio_pct, group_key: str) -> str:
    """Return heatmap level: low / normal / high / critical."""
    thr = THRESHOLDS.get(f"{group_key}_ratio_pct") or THRESHOLDS.get("expense_ratio_pct")
    if not thr or ratio_pct is None:
        return "normal"
    if ratio_pct >= thr["critical"]: return "critical"
    if ratio_pct >= thr["warning"]:  return "high"
    if ratio_pct >= thr["target_max"] * 0.7: return "normal"
    return "low"


# ── Classification (hybrid: mapped_type → code → keyword) ─────────────────────

def _classify_item(account_code: str, account_name: str, mapped_type: str) -> tuple[str, str]:
    """
    Returns (category_key, label_i18n_key).

    Priority:
    1. mapped_type == 'cogs'     → always "cogs"
    2. mapped_type == 'tax'      → "admin_other" (absorbed)
    3. account_code prefix match → specific sub-category
    4. keyword match on name     → specific sub-category
    5. fallback                  → "admin_other"
    """
    mt = (mapped_type or "").lower()

    # Step 1: mapped_type override for cogs
    if mt == "cogs":
        return "cogs", "exp_group_cogs"

    # Step 2: account_code prefix
    code = str(account_code or "").strip()
    for pfx, ck, nk in _CODE_LOOKUP:
        if code.startswith(pfx):
            return ck, nk

    # Step 3: keyword match on account_name
    name_lower = (account_name or "").lower()
    for kw, ck, nk in _KW_LOOKUP:
        if kw in name_lower:
            return ck, nk

    # Step 4: fallback
    return "admin_other", "exp_group_admin"


# ── Build expense groups for one period ──────────────────────────────────────

def _build_groups(stmt: dict, revenue: float) -> dict[str, dict]:
    """
    Group all expense line items by category.
    Returns top_items (≤3 largest) + other_total per group.
    """
    is_ = stmt.get("income_statement", {})
    raw: dict[str, list] = {}

    for section_key in ("cogs", "expenses", "tax"):
        section = is_.get(section_key, {})
        for item in (section.get("items") or []):
            amount = abs(item.get("amount", 0) or 0)
            if not amount:
                continue
            ck, nk = _classify_item(
                item.get("account_code", ""),
                item.get("account_name", ""),
                item.get("mapped_type", section_key if section_key == "cogs" else "expenses"),
            )
            raw.setdefault(ck, []).append({
                "account_code": str(item.get("account_code", "")),
                "account_name": item.get("account_name", ""),
                "amount": round(amount, 2),
            })

    # Also capture section totals when no items (fallback for aggregated data)
    if not any(raw.values()):
        cogs_total = is_.get("cogs", {}).get("total", 0) or 0
        opex_total = is_.get("expenses", {}).get("total", 0) or 0
        if cogs_total:
            raw["cogs"] = [{"account_code":"", "account_name":"COGS", "amount": round(cogs_total,2)}]
        if opex_total:
            raw["admin_other"] = [{"account_code":"", "account_name":"Operating Expenses", "amount": round(opex_total,2)}]

    groups: dict[str, dict] = {}
    for ck, items in raw.items():
        total_val = sum(i["amount"] for i in items)
        sorted_items = sorted(items, key=lambda x: x["amount"], reverse=True)
        top_n = sorted_items[:3]
        other = sum(i["amount"] for i in sorted_items[3:])
        ratio = _pct(total_val, revenue)
        groups[ck] = {
            "category_key": ck,
            "label_key":    _CAT_I18N.get(ck, "exp_group_admin"),
            "icon":         _CAT_ICON.get(ck, "📋"),
            "current":      round(total_val, 2),
            "ratio_pct":    ratio,
            "top_items":    top_n,
            "other_total":  round(other, 2),
            "heatmap":      _heatmap(ratio, ck),
        }
    return groups


# ── Main builder ──────────────────────────────────────────────────────────────

def build_expense_intelligence(
    period_statements: list[dict],
    branch_financials: list[dict] | None = None,   # [{branch_id, branch_name, kpis:{expense_ratio}}]
    lang: str = "en",
) -> dict:
    """
    Full CFO-grade expense intelligence.
    Reads from existing period_statements (from _build_period_statements).
    Branch data reuses existing branch_intelligence kpis — no recomputation.
    """
    if not period_statements:
        return {"error": "No statements"}

    latest = period_statements[-1]
    prior  = period_statements[-2] if len(period_statements) >= 2 else None

    is_     = latest.get("income_statement", {})
    revenue_raw = is_.get("revenue", {}).get("total") or 0
    revenue = revenue_raw if revenue_raw else None  # None = unavailable, no fake fallback

    # ── Groups for latest and prior period ───────────────────────────────────
    groups_now  = _build_groups(latest, revenue)
    groups_prev = _build_groups(prior, prior.get("income_statement",{}).get("revenue",{}).get("total") or None) if prior else {}

    # ── Variance + direction per group ────────────────────────────────────────
    all_keys = sorted(
        set(list(groups_now.keys()) + list(groups_prev.keys())),
        key=lambda k: groups_now.get(k, {}).get("current", 0),
        reverse=True,
    )

    enriched_groups: dict[str, dict] = {}
    for ck in all_keys:
        g     = groups_now.get(ck, {})
        g_prev= groups_prev.get(ck, {})
        curr  = g.get("current", 0)
        prev  = g_prev.get("current")
        var   = round(curr - prev, 2) if prev is not None else None
        var_p = _mom(curr, prev)
        enriched_groups[ck] = {
            **g,
            "previous":     _r2(prev),
            "variance":     var,
            "variance_pct": var_p,
            "direction":    _direction(var_p),
        }

    # ── Summary ───────────────────────────────────────────────────────────────
    cogs  = is_.get("cogs",     {}).get("total", 0) or 0
    opex  = is_.get("expenses", {}).get("total", 0) or 0
    uncls = float((is_.get("unclassified_pnl_debits") or {}).get("total") or 0)
    total = float(cogs) + float(opex) + uncls
    opex_r = opex_ratio_pct(float(opex), float(revenue) if revenue is not None else None)
    cogs_r = cogs_ratio_pct(float(cogs), float(revenue) if revenue is not None else None)
    tc_r = total_cost_ratio_pct(
        float(cogs), float(opex),
        float(revenue) if revenue is not None else None,
        uncls,
    )
    # Legacy: expense_ratio_pct = full cost load (COGS + OpEx + unclassified) / revenue
    exp_ratio = tc_r
    cogs_ratio = cogs_r
    gm_pct    = _pct(revenue - cogs, revenue)
    nm        = is_.get("net_margin_pct") or _pct(is_.get("net_profit", 0) or 0, revenue)

    # Primary pressure = highest-variance increasing group
    primary_pressure = next(
        (ck for ck in all_keys
         if enriched_groups.get(ck, {}).get("direction") == "increasing"
         and (enriched_groups[ck].get("variance_pct") or 0) > 5),
        (all_keys[0] if all_keys else "cogs")
    )

    # ── Top movers ────────────────────────────────────────────────────────────
    top_movers = sorted(
        [{"group": ck, "label_key": _CAT_I18N.get(ck,""), "icon": _CAT_ICON.get(ck,""),
          "variance_pct": enriched_groups[ck].get("variance_pct"),
          "direction": enriched_groups[ck].get("direction", "stable"),
          "amount_delta": enriched_groups[ck].get("variance")}
         for ck in all_keys if enriched_groups[ck].get("variance_pct") is not None],
        key=lambda x: abs(x["variance_pct"] or 0),
        reverse=True,
    )[:3]

    # ── Thresholds ────────────────────────────────────────────────────────────
    def _thr_status(val, thr_key):
        thr = THRESHOLDS.get(thr_key)
        if not thr or val is None: return "unknown"
        if val >= thr["critical"]: return "critical"
        if val >= thr["warning"]:  return "warning"
        if val >= thr["target_max"]: return "elevated"
        return "ok"

    thresholds = {
        "total_cost_ratio_pct": {
            "value": tc_r, "target_max": THRESHOLDS["expense_ratio_pct"]["target_max"],
            "status": _thr_status(tc_r, "expense_ratio_pct"),
            "threshold_source": THRESHOLD_SOURCE,
        },
        "opex_ratio_pct": {
            "value": opex_r, "target_max": THRESHOLDS["expense_ratio_pct"]["target_max"],
            "status": _thr_status(opex_r, "expense_ratio_pct"),
            "threshold_source": THRESHOLD_SOURCE,
        },
        # legacy key: same ceiling as total cost
        "expense_ratio_pct": {
            "value": exp_ratio, "target_max": THRESHOLDS["expense_ratio_pct"]["target_max"],
            "status": _thr_status(exp_ratio, "expense_ratio_pct"),
            "threshold_source": THRESHOLD_SOURCE,
        },
        "cogs_ratio_pct": {
            "value": cogs_ratio, "target_max": THRESHOLDS["cogs_ratio_pct"]["target_max"],
            "status": _thr_status(cogs_ratio, "cogs_ratio_pct"),
            "threshold_source": THRESHOLD_SOURCE,
        },
    }
    payroll_g = enriched_groups.get("payroll")
    if payroll_g:
        thresholds["payroll_ratio_pct"] = {
            "value": payroll_g.get("ratio_pct"), "target_max": THRESHOLDS["payroll_ratio_pct"]["target_max"],
            "status": _thr_status(payroll_g.get("ratio_pct"), "payroll_ratio_pct"),
            "threshold_source": THRESHOLD_SOURCE,
        }
    fuel_g = enriched_groups.get("fuel")
    if fuel_g:
        thresholds["fuel_ratio_pct"] = {
            "value": fuel_g.get("ratio_pct"), "target_max": THRESHOLDS["fuel_ratio_pct"]["target_max"],
            "status": _thr_status(fuel_g.get("ratio_pct"), "fuel_ratio_pct"),
            "threshold_source": THRESHOLD_SOURCE,
        }

    # ── Expense heatmap ───────────────────────────────────────────────────────
    expense_heatmap = {
        ck: {
            "heatmap":   enriched_groups[ck].get("heatmap", "normal"),
            "ratio_pct": enriched_groups[ck].get("ratio_pct"),
            "label_key": enriched_groups[ck].get("label_key", ""),
        }
        for ck in all_keys
    }

    # ── CFO-grade insights — structured, actionable, language-aware ──────────
    insights: list[dict] = []
    _ar = lang == "ar"; _tr = lang == "tr"

    cogs_g = enriched_groups.get("cogs", {})
    rev_mom_approx = None
    if prior:
        prev_rev = prior.get("income_statement",{}).get("revenue",{}).get("total",0) or 0
        rev_mom_approx = _mom(revenue, prev_rev)

    def _sev_to_priority(sev): return {"critical":"high","warning":"medium","info":"low"}.get(sev,"medium")
    def _sev_to_urgency(sev):  return {"critical":"immediate","warning":"short_term","info":"monitor"}.get(sev,"monitor")

    # ── COGS spike ────────────────────────────────────────────────────────────
    cogs_mom = cogs_g.get("variance_pct")
    if cogs_mom and cogs_mom > 5 and (rev_mom_approx is None or cogs_mom > (rev_mom_approx or 0)):
        sev = "warning" if cogs_mom < 15 else "high"
        if _ar:
            wh  = f"تكلفة البضاعة ارتفعت {cogs_mom:.1f}٪ شهرياً — تتجاوز نمو الإيرادات"
            wim = "ضغط على هامش الربح الإجمالي — كل ريال إضافي في التكلفة يأكل مباشرةً من الربحية"
            wtd = "مراجعة العقود مع الموردين وتحليل مكونات تكلفة البضاعة للحد من الضغط على الهامش"
        elif _tr:
            wh  = f"SMM aylık {cogs_mom:.1f}% arttı — gelir artışını aştı"
            wim = "Brüt marjda sıkışma — her ek maliyet birimi kârlılığı doğrudan etkiler"
            wtd = "Tedarikçi sözleşmelerini ve SMM bileşenlerini gözden geçirerek marj baskısını azaltın"
        else:
            wh  = f"COGS grew {cogs_mom:.1f}% MoM — outpacing revenue growth"
            wim = "Gross margin compression — each unit of cost increase directly erodes profitability"
            wtd = "Review supplier contracts and COGS components to reduce margin pressure"
        insights.append({"type":"cogs_spike","severity":sev,"what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":_sev_to_priority(sev),"urgency":_sev_to_urgency(sev),"decision_hint":"reduce_cogs","source_metrics":["cogs_ratio_pct","revenue_mom_pct"]})

    # ── Opex creep ────────────────────────────────────────────────────────────
    opex_g = {ck: g for ck, g in enriched_groups.items() if ck != "cogs"}
    total_opex_now  = sum(g.get("current", 0) for g in opex_g.values())
    total_opex_prev = sum(g.get("previous", 0) or 0 for g in opex_g.values())
    opex_mom = _mom(total_opex_now, total_opex_prev)
    if opex_mom and opex_mom > 8:
        if _ar:
            wh  = f"المصروفات التشغيلية ارتفعت {opex_mom:.1f}٪ شهرياً"
            wim = "تسرب تكلفة متراكم — الزيادات المتكررة في المصروفات تضغط على صافي الهامش"
            wtd = "تدقيق بنود المصروفات التشغيلية وتحديد القطع التي تتجاوز الميزانية"
        elif _tr:
            wh  = f"Faaliyet giderleri aylık {opex_mom:.1f}% arttı"
            wim = "Birikimli maliyet sızıntısı — tekrarlayan artışlar net marjı sıkıştırıyor"
            wtd = "Faaliyet gideri kalemlerini denetleyin ve bütçeyi aşan kalemleri belirleyin"
        else:
            wh  = f"Operating expenses rose {opex_mom:.1f}% MoM"
            wim = "Cumulative cost leakage — recurring expense increases are compressing net margin"
            wtd = "Audit operating expense line items and identify categories exceeding budget"
        insights.append({"type":"opex_creep","severity":"warning","what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":"medium","urgency":"short_term","decision_hint":"review_opex","source_metrics":["expense_ratio_pct","net_margin_pct"]})

    # ── Payroll pressure ──────────────────────────────────────────────────────
    if payroll_g and (payroll_g.get("ratio_pct") or 0) > THRESHOLDS["payroll_ratio_pct"]["warning"]:
        pr = payroll_g["ratio_pct"]
        if _ar:
            wh  = f"الرواتب والأجور تمثل {pr:.1f}٪ من الإيرادات — فوق الحد الأمثل البالغ 30٪"
            wim = "كثافة عمالة مرتفعة — هيكل التكاليف الثابتة يحد من مرونة الربحية"
            wtd = "مراجعة كفاءة الإنتاجية لكل موظف وتقييم فرص إعادة هيكلة القوى العاملة"
        elif _tr:
            wh  = f"Bordro gelirin {pr:.1f}%'ini oluşturuyor — %30 optimum eşiğinin üzerinde"
            wim = "Yüksek işgücü yoğunluğu — sabit maliyet yapısı kârlılık esnekliğini kısıtlıyor"
            wtd = "Çalışan başına verimlilik ve işgücü yeniden yapılandırma fırsatlarını değerlendirin"
        else:
            wh  = f"Payroll represents {pr:.1f}% of revenue — above the 30% optimal threshold"
            wim = "High labor intensity — fixed cost structure limits profitability flexibility"
            wtd = "Review per-employee productivity and assess workforce optimization opportunities"
        insights.append({"type":"payroll_pressure","severity":"warning","what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":"medium","urgency":"short_term","decision_hint":"workforce_optimization","source_metrics":["payroll_ratio_pct","net_margin_pct"]})

    # ── Fuel volatility ───────────────────────────────────────────────────────
    if fuel_g and abs(fuel_g.get("variance_pct") or 0) > 15:
        fv = fuel_g["variance_pct"] or 0; direction = "سارت بشكل" if _ar else ("artış" if fv>0 else "düşüş")
        if _ar:
            wh  = f"تكاليف الوقود تحركت {abs(fv):.1f}٪ شهرياً — تعرض واضح لتقلبات أسعار الطاقة"
            wim = "الأسطول حساس لتقلبات الوقود — بدون تحوط، هذه التكاليف تضغط على الهوامش التشغيلية"
            wtd = "تقييم خيارات التحوط من أسعار الوقود وتحسين الكفاءة التشغيلية لخفض تكلفة الوحدة"
        elif _tr:
            wh  = f"Yakıt maliyetleri aylık {abs(fv):.1f}% hareket etti — enerji fiyatı dalgalanmasına açıklık"
            wim = "Filo yakıt fiyat dalgalanmalarına duyarlı — korumasız, bu maliyetler faaliyet marjını baskılar"
            wtd = "Yakıt fiyatı riskinden korunma seçeneklerini ve operasyonel verimliliği değerlendirin"
        else:
            wh  = f"Fuel costs moved {abs(fv):.1f}% MoM — exposure to energy price volatility"
            wim = "Fleet operations sensitive to fuel price swings — unhedged, these costs compress operational margin"
            wtd = "Evaluate fuel price hedging options and improve Operational Efficiency to reduce unit costs"
        sev = "warning" if abs(fv) > 20 else "info"
        insights.append({"type":"fuel_volatility","severity":sev,"what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":_sev_to_priority(sev),"urgency":_sev_to_urgency(sev),"decision_hint":"logistics_efficiency","source_metrics":["fuel_ratio_pct","expense_ratio_pct"]})

    # ── Maintenance increase ──────────────────────────────────────────────────
    maint_g = enriched_groups.get("maintenance", {})
    if maint_g and (maint_g.get("variance_pct") or 0) > 10:
        mv = maint_g["variance_pct"]
        if _ar:
            wh  = f"مصاريف الصيانة ارتفعت {mv:.1f}٪ — قد يشير إلى تدهور في حالة الأصول"
            wim = "تصاعد الصيانة هو مؤشر مبكر على قرب نهاية دورة حياة الأصول أو إهمال الصيانة الوقائية"
            wtd = "تقييم حالة الأسطول والمعدات وجدولة الصيانة الوقائية لتجنب أعطال مكلفة"
        elif _tr:
            wh  = f"Bakım giderleri {mv:.1f}% arttı — varlık durumunun bozulmasına işaret edebilir"
            wim = "Artan bakım, varlık yaşam döngüsünün sonuna yaklaşıldığının veya önleyici bakımın ihmal edildiğinin erken göstergesi"
            wtd = "Filo ve ekipman durumunu değerlendirin, maliyetli arızaları önlemek için önleyici bakım planlayın"
        else:
            wh  = f"Maintenance costs rose {mv:.1f}% — possible indicator of asset condition deterioration"
            wim = "Rising maintenance is an early signal of approaching asset lifecycle end or deferred preventive care"
            wtd = "Assess fleet and equipment condition; schedule preventive maintenance to avoid costly breakdowns"
        insights.append({"type":"maintenance_increase","severity":"warning","what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":"medium","urgency":"short_term","decision_hint":"asset_lifecycle_review","source_metrics":["maintenance_ratio_pct","expense_ratio_pct"]})

    # ── Margin squeeze ────────────────────────────────────────────────────────
    if exp_ratio and exp_ratio > THRESHOLDS["expense_ratio_pct"]["warning"]:
        sev = "critical" if (exp_ratio or 0) > THRESHOLDS["expense_ratio_pct"]["critical"] else "warning"
        if _ar:
            wh  = f"إجمالي نسبة المصروفات {exp_ratio:.1f}٪ — يقترب من سقف الربحية"
            wim = "ضغط الهامش الحرج — الأداء المالي الإجمالي معرض لخطر الدخول في منطقة الخسارة"
            wtd = "مراجعة فورية لبنود التكلفة الكبرى وتطبيق ضوابط صارمة على الإنفاق"
        elif _tr:
            wh  = f"Toplam gider oranı {exp_ratio:.1f}% — kârlılık tavanına yaklaşıyor"
            wim = "Kritik marj sıkışması — genel finansal performans zarar bölgesine girme riskiyle karşı karşıya"
            wtd = "Büyük maliyet kalemlerini acil olarak gözden geçirin ve katı harcama kontrolleri uygulayın"
        else:
            wh  = f"Total expense ratio at {exp_ratio:.1f}% — approaching profitability ceiling"
            wim = "Critical margin compression — overall financial performance at risk of entering loss territory"
            wtd = "Immediate review of major cost line items; implement strict spending controls"
        insights.append({"type":"margin_squeeze","severity":sev,"what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":_sev_to_priority(sev),"urgency":_sev_to_urgency(sev),"decision_hint":"immediate_cost_review","source_metrics":["expense_ratio_pct","net_margin_pct"]})

    # ── COGS improving (positive) ─────────────────────────────────────────────
    if cogs_mom and cogs_mom < -3 and (gm_pct or 0) > 40:
        if _ar:
            wh  = f"تكلفة البضاعة انخفضت {abs(cogs_mom):.1f}٪ — توسع في هامش الربح الإجمالي"
            wim = "تحسين في كفاءة الشراء أو انخفاض في أسعار المواد — يجب الحفاظ عليه"
            wtd = "توثيق مصادر توفير التكاليف والحفاظ على الانضباط في الشراء"
        elif _tr:
            wh  = f"SMM {abs(cogs_mom):.1f}% düştü — brüt marj genişliyor"
            wim = "Satın alma verimliliğinde iyileşme veya malzeme fiyatlarında düşüş — korunmalı"
            wtd = "Maliyet tasarrufu kaynaklarını belgeleyin ve satın alma disiplinini koruyun"
        else:
            wh  = f"COGS declined {abs(cogs_mom):.1f}% — gross margin expanding"
            wim = "Procurement efficiency improvement or input price reduction — must be sustained"
            wtd = "Document cost-saving sources and maintain purchasing discipline"
        insights.append({"type":"cogs_improving","severity":"info","what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":"low","urgency":"monitor","decision_hint":"sustain_cost_discipline","source_metrics":["cogs_ratio_pct","gross_margin_pct"]})

    # ── Branch comparison (reuse existing kpis — no recomputation) ────────────
    branch_comparison: list[dict] = []
    if branch_financials:
        br_ratios = [b["kpis"].get("expense_ratio") for b in branch_financials
                     if isinstance(b.get("kpis"), dict) and b["kpis"].get("expense_ratio") is not None]
        company_avg = round(sum(br_ratios) / len(br_ratios), 2) if br_ratios else exp_ratio
        for b in branch_financials:
            br_exp = b.get("kpis", {}).get("expense_ratio")
            if br_exp is None:
                continue
            delta = round(br_exp - (company_avg or 0), 2)
            branch_comparison.append({
                "branch_id":      b.get("branch_id", ""),
                "branch_name":    b.get("branch_name", ""),
                "expense_ratio":  br_exp,
                "vs_company_avg": delta,
                "pressure_flag":  br_exp > THRESHOLDS["expense_ratio_pct"]["warning"],
                "heatmap":        _heatmap(br_exp, "expense_ratio_pct"),
            })
        branch_comparison.sort(key=lambda x: x["expense_ratio"], reverse=True)

    return {
        "period_count":    len(period_statements),
        "periods":         [s.get("period","") for s in period_statements],
        "latest_period":   latest.get("period", ""),

        "summary": {
            "total_cost_amount": round(total, 2),
            "total_expenses":    round(total, 2),
            "total_cogs":        round(cogs, 2),
            "total_opex":        round(opex, 2),
            "total_unclassified_pnl_debits": round(uncls, 2),
            "opex_ratio_pct":    opex_r,
            "cogs_ratio_pct":    cogs_ratio,
            "total_cost_ratio_pct": tc_r,
            "expense_ratio_pct": exp_ratio,
            "gross_margin_pct":  gm_pct,
            "net_margin_pct":    _r2(nm),
            "primary_pressure":  primary_pressure,
        },

        "groups":           enriched_groups,
        "top_movers":       top_movers,
        "expense_heatmap":  expense_heatmap,
        "thresholds":       thresholds,
        "insights":         insights,
        "branch_comparison":branch_comparison,
    }
