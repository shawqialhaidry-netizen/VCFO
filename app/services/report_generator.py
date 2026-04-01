"""
report_generator.py — Board Report Generator
Phase: Board Report Layer

Assembles a CFO-grade board report from existing analysis + executive outputs.
NO financial recalculation. Pure assembly + narrative layer.

Input sources:
  analysis:  output of GET /api/v1/analysis/{company_id}
  executive: output of GET /api/v1/companies/{company_id}/executive

Output: structured board report dict with 7 sections.
"""
from __future__ import annotations


def _g(d: dict, *keys, default=None):
    """Safe nested get."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
        if d is None:
            return default
    return d


def _fmt_m(v) -> str:
    """Format a monetary value concisely."""
    if v is None:
        return "—"
    try:
        v = float(v)
        if abs(v) >= 1_000_000:
            return f"{v/1_000_000:.2f}M"
        if abs(v) >= 1_000:
            return f"{v/1_000:.0f}K"
        return f"{v:.0f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return "—"


# ── Summary builder ────────────────────────────────────────────────────────────


_HEALTH_LABEL_AR = {
    "strong": "قوي", "good": "جيد", "stable": "مستقر",
    "weak": "ضعيف", "critical": "حرج"
}
_HEALTH_LABEL_TR = {
    "strong": "güçlü", "good": "iyi", "stable": "istikrarlı",
    "weak": "zayıf", "critical": "kritik"
}


def _build_summary(analysis: dict, executive: dict, lang: str) -> str:
    """
    2–4 sentence executive summary: health + top issue + top opportunity.
    Fully language-aware. No calculation — text drawn from existing signals.
    """
    ar = lang == "ar"; tr_ = lang == "tr"

    # Health
    health  = _g(executive, "health") or {}
    score   = health.get("score") or 0
    label   = health.get("label") or ("strong" if score >= 80 else "stable")
    nm      = _g(executive, "quick_metrics", "net_margin_pct")
    rev_mom = _g(executive, "quick_metrics", "revenue_mom_pct")

    # Top priority
    pris   = executive.get("top_priorities") or []
    top_p  = pris[0].get("summary", "") if pris else ""

    # Top opportunity
    opps  = executive.get("opportunities") or []
    top_o = opps[0].get("description", "") if opps else ""

    if ar:
        health_sent = (
            f"يُصنَّف الوضع المالي للشركة على أنه «{_HEALTH_LABEL_AR.get(label, label)}» بنسبة ربح صافٍ {_fmt_pct(nm)} "
            f"{'وإيرادات في ارتفاع ' + _fmt_pct(rev_mom) + ' شهرياً' if rev_mom and rev_mom > 0 else ''}."
        )
        issue_sent  = f"أبرز القضية الحالية: {top_p}" if top_p else ""
        opp_sent    = f"وفي المقابل، {top_o}" if top_o else ""
    elif tr_:
        health_sent = (
            f"Şirketin mali durumu «{_HEALTH_LABEL_TR.get(label, label)}» olarak sınıflandırılıyor; "
            f"net marj {_fmt_pct(nm)}"
            f"{', aylık ' + _fmt_pct(rev_mom) + ' gelir büyümesi ile' if rev_mom and rev_mom > 0 else ''}."
        )
        issue_sent  = f"Öne çıkan konu: {top_p}" if top_p else ""
        opp_sent    = f"Öte yandan, {top_o}" if top_o else ""
    else:
        health_sent = (
            f"The company's financial position is classified as «{label}» with a net margin of "
            f"{_fmt_pct(nm)}"
            f"{' and revenue growing ' + _fmt_pct(rev_mom) + ' MoM' if rev_mom and rev_mom > 0 else ''}."
        )
        issue_sent  = f"The primary issue requiring attention: {top_p}" if top_p else ""
        opp_sent    = f"On the positive side, {top_o}" if top_o else ""

    parts = [s for s in [health_sent, issue_sent, opp_sent] if s.strip()]
    return " ".join(parts)


# ── Risks builder ──────────────────────────────────────────────────────────────

def _build_risks(analysis: dict, executive: dict) -> list[dict]:
    """
    Primary: executive.risks (high + medium only).
    Fallback: analysis.anomalies.
    Deduplicated by type.
    """
    VALID_SEV = {"high", "critical", "medium"}
    seen: set = set()
    risks: list[dict] = []

    # Primary: executive risks
    for r in (executive.get("risks") or []):
        sev  = str(r.get("severity", "")).lower()
        rtype = r.get("type", "")
        if sev in VALID_SEV and rtype not in seen:
            seen.add(rtype)
            risks.append({
                "type":        rtype,
                "severity":    sev,
                "description": r.get("description") or r.get("what_happened", ""),
                "source":      r.get("source", "executive"),
            })

    # Fallback: analysis anomalies
    for a in (analysis.get("anomalies") or []):
        sev  = str(a.get("severity", "")).lower()
        atype = a.get("type", "")
        if sev in VALID_SEV and atype not in seen:
            seen.add(atype)
            risks.append({
                "type":        atype,
                "severity":    sev,
                "description": a.get("what_happened", ""),
                "source":      "anomaly_engine",
            })

    return risks


# ── Opportunities builder ──────────────────────────────────────────────────────

def _build_opportunities(executive: dict, analysis: dict) -> list[dict]:
    """Positive signals: strong_profitability, growth_momentum, and low-priority narratives."""
    POSITIVE_TYPES = {"strong_profitability", "growth_momentum", "strong_margin",
                      "cogs_improving", "margin_leader"}
    opps: list[dict] = []
    seen: set = set()

    for o in (executive.get("opportunities") or []):
        otype = o.get("type", "")
        if otype not in seen:
            seen.add(otype)
            opps.append({
                "type":           otype,
                "description":    o.get("description", ""),
                "source_metrics": o.get("source_metrics", []),
            })

    for n in (analysis.get("narratives") or []):
        otype = n.get("type", "")
        if n.get("priority") == "low" and otype in POSITIVE_TYPES and otype not in seen:
            seen.add(otype)
            opps.append({
                "type":           otype,
                "description":    n.get("what_happened", ""),
                "source_metrics": list((n.get("source_metrics") or {}).keys()),
            })

    return opps


# ── Priorities builder ─────────────────────────────────────────────────────────

def _build_priorities(executive: dict) -> list[dict]:
    """Top 3 from executive.top_priorities with priority + urgency + decision_hint."""
    result = []
    for p in (executive.get("top_priorities") or [])[:3]:
        result.append({
            "rank":          p.get("rank"),
            "summary":       p.get("summary", ""),
            "priority":      p.get("priority") or p.get("severity", "medium"),
            "urgency":       p.get("urgency", "soon"),
            "type":          p.get("type", ""),
            "source":        p.get("source", ""),
            "decision_hint": p.get("decision_hint", ""),
        })
    return result


# ── Snapshot builder ───────────────────────────────────────────────────────────

def _build_snapshot(analysis: dict, executive: dict) -> dict:
    """Key financial metrics — no calculation, pure assembly.
    Revenue, net_profit, and margins come from quick_metrics (windowed aggregated).
    Liquidity/efficiency ratios come from latest-period analysis (ratio-based, not summed).
    """
    qm  = executive.get("quick_metrics") or {}
    rat = analysis.get("ratios") or {}
    prof= rat.get("profitability") or {}
    liq = rat.get("liquidity") or {}
    eff = rat.get("efficiency") or {}

    return {
        # P&L — windowed values from quick_metrics (aggregated across window)
        "revenue":             qm.get("revenue"),
        "net_profit":          qm.get("net_profit"),
        "window_revenue_total": qm.get("window_revenue_total"),
        "latest_revenue":      qm.get("latest_revenue"),
        "window_net_profit_total": qm.get("window_net_profit_total"),
        "latest_net_profit":   qm.get("latest_net_profit"),
        "net_margin_pct":      qm.get("net_margin_pct"),
        "latest_net_margin_pct": qm.get("latest_net_margin_pct"),
        "gross_margin_pct":    qm.get("gross_margin_pct") or prof.get("gross_margin_pct"),
        "latest_gross_margin_pct": qm.get("latest_gross_margin_pct"),
        "operating_margin_pct": prof.get("operating_margin_pct"),
        "operating_cashflow":  qm.get("operating_cashflow"),
        # Liquidity
        "current_ratio":       liq.get("current_ratio"),
        "working_capital":     liq.get("working_capital"),
        # Efficiency
        "dso_days":            eff.get("dso_days"),
        "ccc_days":            eff.get("ccc_days"),
        "inventory_turnover":  eff.get("inventory_turnover"),
        # MoM
        "revenue_mom_pct":     qm.get("revenue_mom_pct"),
        "net_profit_mom_pct":  qm.get("net_profit_mom_pct"),
        # Cost ratios (% of revenue) — prefer explicit names; expense_ratio = total cost load (legacy)
        "opex_ratio_pct":      qm.get("opex_ratio_pct"),
        "cogs_ratio_pct":      qm.get("cogs_ratio_pct"),
        "total_cost_ratio_pct": qm.get("total_cost_ratio_pct"),
        "latest_opex_ratio_pct": qm.get("latest_opex_ratio_pct"),
        "latest_cogs_ratio_pct": qm.get("latest_cogs_ratio_pct"),
        "latest_total_cost_ratio_pct": qm.get("latest_total_cost_ratio_pct"),
        "expense_ratio":       qm.get("expense_ratio") or qm.get("total_cost_ratio_pct"),
    }


# ── Outlook builder ────────────────────────────────────────────────────────────

def _build_outlook(analysis: dict, lang: str) -> str:
    """
    Short forward-looking narrative from trends + forecast insight.
    No financial calculation.
    """
    ar = lang == "ar"; tr_ = lang == "tr"

    trends    = analysis.get("trends") or {}
    rev_trend = (trends.get("revenue") or {})
    np_trend  = (trends.get("net_profit") or {})
    rev_dir   = rev_trend.get("direction", "stable")
    np_dir    = np_trend.get("direction", "stable")
    np_loss   = np_trend.get("loss_flag", False)

    # Try to get forecast insight from narratives or trends
    narratives = analysis.get("narratives") or []
    fc_insight = ""
    for n in narratives:
        if n.get("domain") in ("revenue", "profit") and n.get("what_happened"):
            fc_insight = n.get("what_happened", "")
            break

    if ar:
        if np_loss:
            outlook = "المؤشرات تُشير إلى استمرار الضغط على الربحية؛ التدفق النقدي يستدعي مراقبة مستمرة."
        elif rev_dir == "improving" and np_dir == "improving":
            outlook = "الزخم الإيجابي في الإيرادات والأرباح يُشير إلى استمرار التحسن إذا حافظت الشركة على انضباطها في التكاليف."
        elif rev_dir == "improving":
            outlook = "الإيرادات في نمو، لكن الأرباح تحتاج إلى مراقبة دقيقة لضمان ترجمة النمو إلى ربحية فعلية."
        else:
            outlook = "المؤشرات المالية مستقرة؛ التركيز على كفاءة التكاليف وجودة النمو هو الأولوية للفترة القادمة."
    elif tr_:
        if np_loss:
            outlook = "Göstergeler kârlılık üzerindeki baskının devam ettiğine işaret ediyor; nakit akışı sürekli izlem gerektiriyor."
        elif rev_dir == "improving" and np_dir == "improving":
            outlook = "Gelir ve kârdaki olumlu ivme, şirketin maliyet disiplinini koruması halinde iyileşmenin süreceğine işaret ediyor."
        elif rev_dir == "improving":
            outlook = "Gelir büyüyor ancak büyümenin gerçek kâra dönüşmesi için kâr marjlarının yakından izlenmesi gerekiyor."
        else:
            outlook = "Mali göstergeler istikrarlı; önümüzdeki dönem için maliyet verimliliği ve büyüme kalitesi öncelikli odak alanları."
    else:
        if np_loss:
            outlook = "Indicators point to continued profitability pressure; cash flow requires close monitoring."
        elif rev_dir == "improving" and np_dir == "improving":
            outlook = "Positive momentum in both revenue and profit suggests continued improvement, provided cost discipline is maintained."
        elif rev_dir == "improving":
            outlook = "Revenue is growing, but profit margins need close monitoring to ensure growth translates into actual profitability."
        else:
            outlook = "Financial indicators are stable; cost efficiency and growth quality are the priority focus areas for the coming period."

    if fc_insight and fc_insight != outlook:
        return f"{outlook} {fc_insight}" if len(fc_insight) < 120 else outlook
    return outlook


# ── Board-grade narrative sections (deterministic, evidence-based) ─────────────

def _last_non_null(values: list):
    for v in reversed(values or []):
        if v is not None:
            return v
    return None


def _pp(v) -> str:
    """Format percentage points (already in % units)."""
    if v is None:
        return "—"
    try:
        v = float(v)
        s = "+" if v >= 0 else ""
        return f"{s}{v:.1f} pp"
    except (TypeError, ValueError):
        return "—"


def _build_highlights(analysis: dict, executive: dict, lang: str) -> list[dict]:
    """
    3–6 factual highlights with explicit metric references.
    No new calculation; uses snapshot + trends + priorities.
    """
    ar = lang == "ar"; tr_ = lang == "tr"
    snap = _build_snapshot(analysis, executive)
    trends = analysis.get("trends") or {}
    rev = (trends.get("revenue") or {})
    np_ = (trends.get("net_profit") or {})
    rev_dir = rev.get("direction", "stable")
    np_dir  = np_.get("direction", "stable")
    rev_mom = snap.get("revenue_mom_pct")
    np_mom  = snap.get("net_profit_mom_pct")

    items: list[dict] = []

    nm = snap.get("net_margin_pct")
    if nm is not None:
        msg = (f"Net margin is {_fmt_pct(nm)}." if not ar and not tr_
               else (f"هامش الربح الصافي {_fmt_pct(nm)}." if ar
                     else f"Net marj {_fmt_pct(nm)}."))
        items.append({"type": "profitability_snapshot", "message": msg, "metrics": ["net_margin_pct"]})

    if rev_mom is not None:
        msg = (f"Revenue momentum: {_fmt_pct(rev_mom)} MoM." if not ar and not tr_
               else (f"زخم الإيرادات: {_fmt_pct(rev_mom)} شهرياً." if ar
                     else f"Gelir momentumu: aylık {_fmt_pct(rev_mom)}."))
        items.append({"type": "revenue_momentum", "message": msg, "metrics": ["revenue_mom_pct"]})

    if np_mom is not None:
        msg = (f"Net profit momentum: {_fmt_pct(np_mom)} MoM." if not ar and not tr_
               else (f"زخم صافي الربح: {_fmt_pct(np_mom)} شهرياً." if ar
                     else f"Net kâr momentumu: aylık {_fmt_pct(np_mom)}."))
        items.append({"type": "profit_momentum", "message": msg, "metrics": ["net_profit_mom_pct"]})

    if rev_dir in ("improving", "declining") or np_dir in ("improving", "declining"):
        msg = (f"Trend direction: revenue {rev_dir}, net profit {np_dir}." if not ar and not tr_
               else (f"اتجاه الاتجاهات: الإيرادات {rev_dir}، وصافي الربح {np_dir}." if ar
                     else f"Eğilim yönü: gelir {rev_dir}, net kâr {np_dir}."))
        items.append({"type": "trend_direction", "message": msg, "metrics": ["revenue_series", "net_profit_series"]})

    pris = (executive.get("top_priorities") or [])
    if pris:
        p0 = pris[0]
        if p0.get("summary"):
            msg = (f"Top priority: {p0.get('summary')}" if not ar and not tr_
                   else (f"الأولوية الأولى: {p0.get('summary')}" if ar
                         else f"Öncelik: {p0.get('summary')}"))
            items.append({"type": "top_priority", "message": msg, "metrics": []})

    return items[:6]


def _build_major_risks(analysis: dict, executive: dict, lang: str) -> list[dict]:
    """Board-facing risk statements derived from existing risk signals."""
    ar = lang == "ar"; tr_ = lang == "tr"
    risks = _build_risks(analysis, executive)
    out: list[dict] = []
    for r in risks[:6]:
        desc = r.get("description") or "—"
        sev  = r.get("severity")
        if ar:
            msg = f"مخاطر ({sev}): {desc}"
        elif tr_:
            msg = f"Risk ({sev}): {desc}"
        else:
            msg = f"Risk ({sev}): {desc}"
        out.append({"type": r.get("type"), "severity": sev, "message": msg, "source": r.get("source")})
    return out


def _build_cost_drivers(analysis: dict, executive: dict, lang: str) -> dict:
    """Cost structure notes from existing expense_ratio and existing priority signals."""
    ar = lang == "ar"; tr_ = lang == "tr"
    snap = _build_snapshot(analysis, executive)
    tc = snap.get("total_cost_ratio_pct") or snap.get("expense_ratio")
    ox = snap.get("opex_ratio_pct")
    if tc is not None:
        if ar:
            summary = f"إجمالي حمل التكلفة (SMM + مصاريف + غير مصنف) من الإيراد: {_fmt_pct(tc)}."
        elif tr_:
            summary = f"Toplam maliyet yükü (SMM + gider + sınıflandırılmamış) / gelir: {_fmt_pct(tc)}."
        else:
            summary = (
                f"Total cost load (COGS + OpEx + unclassified P&L debits) is {_fmt_pct(tc)} of revenue."
            )
    elif ox is not None:
        if ar:
            summary = f"نسبة المصاريف التشغيلية إلى الإيراد: {_fmt_pct(ox)}."
        elif tr_:
            summary = f"Faaliyet giderlerinin gelire oranı: {_fmt_pct(ox)}."
        else:
            summary = f"Operating expenses are {_fmt_pct(ox)} of revenue."
    else:
        summary = "—"

    pri = executive.get("top_priorities") or []
    exp_related = [p for p in pri if (p.get("source") == "expense" or "cost" in str(p.get("type","")))]
    return {
        "total_cost_ratio_pct": tc,
        "opex_ratio_pct": ox,
        "expense_ratio": tc or snap.get("expense_ratio"),
        "summary":       summary,
        "signals":       exp_related[:3],
    }


def _build_recommendations(analysis: dict, executive: dict, lang: str) -> list[dict]:
    """
    Board-level actions: reuse executive priorities + deterministic governance note on loss_flag.
    """
    ar = lang == "ar"; tr_ = lang == "tr"
    pris = executive.get("top_priorities") or []
    recs: list[dict] = []

    for p in pris[:5]:
        text = p.get("summary") or ""
        if not text:
            continue
        recs.append({"priority": p.get("severity") or p.get("priority", "medium"), "action": text})

    np_loss = _g(analysis, "trends", "net_profit", "loss_flag", default=False)
    if np_loss:
        if ar:
            recs.insert(0, {"priority": "high", "action": "اعتماد خطة ضبط تكاليف قصيرة الأجل ومراجعة شهرية للأداء المالي حتى عودة الربحية."})
        elif tr_:
            recs.insert(0, {"priority": "high", "action": "Kısa vadeli maliyet kontrol planı ve kârlılık geri dönene kadar aylık performans gözden geçirme."})
        else:
            recs.insert(0, {"priority": "high", "action": "Adopt a short-term cost control plan and run monthly performance reviews until profitability stabilizes."})

    return recs[:6]


# ── Main builder ───────────────────────────────────────────────────────────────

def build_board_report(
    analysis:  dict,
    executive: dict,
    lang:      str = "en",
    *,
    deep_intelligence: dict | None = None,
    phase43_root_causes: list | None = None,
    cfo_decisions: list | None = None,
) -> dict:
    """
    Assemble a CFO board report from analysis + executive outputs.
    No financial recalculation. Pure assembly and narrative layer.

    Args:
        analysis:  output of GET /api/v1/analysis/{company_id}
        executive: output of GET /api/v1/companies/{company_id}/executive
        lang:      "en" | "ar" | "tr"

    Returns:
        structured board report dict
    """
    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company_id   = analysis.get("company_id") or executive.get("company_id", "")
    company_name = analysis.get("company_name") or executive.get("company_name", "")
    period       = analysis.get("latest_period") or executive.get("latest_period", "")
    period_count = analysis.get("period_count") or executive.get("period_count", 0)
    health       = executive.get("health") or {}

    di = deep_intelligence or {}
    exp = di.get("expense_intelligence") or {}
    trn = di.get("trend_intelligence") or {}
    prof = di.get("profitability_intelligence") or {}

    brain_pack = {
        "expense_pressure":    (exp.get("pressure_assessment") or {}),
        "expense_top_drivers": (exp.get("top_drivers") or [])[:5],
        "trend_signals":       (trn.get("signals") or [])[:12],
        "trend_series_stats":  trn.get("series_stats") or {},
        "profitability":       {
            "interpretation": (prof.get("interpretation") or {}),
            "drivers":        (prof.get("drivers") or []),
            "margin_change_pp": (prof.get("margin_change_pp") or {}),
        } if prof.get("available") else {},
    }

    out = {
        "company_id":   company_id,
        "company_name": company_name,
        "period":       period,
        "period_count": period_count,
        "lang":         safe_lang,
        "generated_at": None,   # caller injects timestamp if needed

        "health": {
            "score":  health.get("score"),
            "label":  health.get("label"),
            "method": health.get("score_method", "rule_based"),
        },

        "summary":       _build_summary(analysis, executive, safe_lang),
        "risks":         _build_risks(analysis, executive),
        "opportunities": _build_opportunities(executive, analysis),
        "priorities":    _build_priorities(executive),
        "snapshot":      _build_snapshot(analysis, executive),
        "outlook":       _build_outlook(analysis, safe_lang),
        # Additive board-grade sections
        "highlights":     _build_highlights(analysis, executive, safe_lang),
        "major_risks":    _build_major_risks(analysis, executive, safe_lang),
        "cost_drivers":   _build_cost_drivers(analysis, executive, safe_lang),
        "recommendations": _build_recommendations(analysis, executive, safe_lang),
        # Phase 1 — financial brain (deterministic; optional inputs)
        "brain_pack":         brain_pack,
        "structured_root_causes": list(phase43_root_causes or []),
        "structured_decisions":   list(cfo_decisions or []),
    }
    return out
