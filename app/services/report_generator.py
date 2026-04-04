"""
report_generator.py — Board Report Generator
Phase: Board Report Layer

Assembles a CFO-grade board report from existing analysis + executive outputs.
NO financial recalculation. Pure assembly + narrative layer.

Input sources:
  analysis:  output of GET /api/v1/analysis/{company_id}
  executive: output of GET /api/v1/companies/{company_id}/executive

Output: structured board report dict with 7 sections.

Wave 2B: summary / outlook / highlights use realize_ref (board.* i18n) and, when
present, realize_causal_items output — avoiding mixed-language concatenation of
raw narrative strings when a causal path exists.
"""
from __future__ import annotations

from app.services.causal_realize import realize_causal_items, realize_ref


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


# ── Wave 2B: causal merge + realization helpers ──────────────────────────────


def _board_merge_causal_items(analysis: dict, extra: list | None) -> list[dict]:
    """Dedup by item id; analysis list first, then optional caller-supplied items."""
    merged: list[dict] = []
    seen: set[str] = set()
    for it in list(analysis.get("causal_items") or []) + list(extra or []):
        if not isinstance(it, dict):
            continue
        uid = str(it.get("id") or "") or f"_:{len(seen)}"
        if uid in seen:
            continue
        seen.add(uid)
        merged.append(it)
    return merged


def _realization_usable(text: str) -> bool:
    if not (text or "").strip():
        return False
    t = text.strip()
    return not (
        t.startswith("[missing:")
        or t.startswith("[invalid_lang:")
        or t.startswith("[format_error:")
    )


def _board_health_label(label: str, realize_lang: str) -> str:
    slug = str(label or "stable").lower().replace(" ", "_")
    r = realize_ref({"key": f"board.health_label.{slug}", "params": {}}, realize_lang)
    if _realization_usable(r):
        return r
    return realize_ref(
        {"key": "board.health_label.unknown", "params": {"label": str(label or "")}},
        realize_lang,
    )


# ── Summary builder ────────────────────────────────────────────────────────────


def _build_summary(
    analysis: dict,
    executive: dict,
    realize_lang: str,
    realized_causal: list[dict],
) -> str:
    """
    2–4 sentence executive summary: health + top issue + top opportunity.
    Health and wrappers use realize_ref (board.*). Issues/opportunities prefer
    realized causal text when usable; otherwise legacy executive strings via i18n
    wrappers (#legacy_mixed_source risk when executive copy locale ≠ request).
    """
    # Health
    health = _g(executive, "health") or {}
    score = health.get("score") or 0
    label = health.get("label") or ("strong" if score >= 80 else "stable")
    nm = _g(executive, "quick_metrics", "net_margin_pct")
    rev_mom = _g(executive, "quick_metrics", "revenue_mom_pct")

    health_lbl = _board_health_label(str(label), realize_lang)
    nm_s = _fmt_pct(nm)
    if rev_mom is not None and rev_mom > 0:
        health_sent = realize_ref(
            {
                "key": "board.summary.health_with_mom",
                "params": {"health_label": health_lbl, "nm": nm_s, "rev_mom": _fmt_pct(rev_mom)},
            },
            realize_lang,
        )
    else:
        health_sent = realize_ref(
            {"key": "board.summary.health_no_mom", "params": {"health_label": health_lbl, "nm": nm_s}},
            realize_lang,
        )

    pris = executive.get("top_priorities") or []
    top_p = pris[0].get("summary", "") if pris else ""
    opps = executive.get("opportunities") or []
    top_o = opps[0].get("description", "") if opps else ""

    issue_sent = ""
    for it in realized_causal:
        if str(it.get("severity", "")).lower() not in ("high", "medium"):
            continue
        ct = it.get("change_text") or ""
        if _realization_usable(ct):
            issue_sent = ct
            break
    if not issue_sent.strip() and top_p:
        # LEGACY: executive summary may not match realize_lang
        issue_sent = realize_ref(
            {"key": "board.summary.issue_executive", "params": {"summary": top_p}},
            realize_lang,
        )

    opp_sent = ""
    for it in realized_causal:
        sev = str(it.get("severity", "")).lower()
        topic = str(it.get("topic", "")).lower()
        if sev != "low" and topic != "growth":
            continue
        ct = it.get("change_text") or ""
        if _realization_usable(ct):
            opp_sent = ct
            break
    if not opp_sent.strip() and top_o:
        # LEGACY: opportunity description locale may not match request
        opp_sent = realize_ref(
            {"key": "board.summary.opportunity_executive", "params": {"description": top_o}},
            realize_lang,
        )

    parts = [s for s in [health_sent, issue_sent, opp_sent] if (s or "").strip()]
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

def _build_outlook(
    analysis: dict,
    realize_lang: str,
    realized_causal: list[dict],
    *,
    had_raw_causal: bool,
) -> str:
    """
    Forward-looking narrative: base branch via realize_ref (board.outlook.*).
    When causal_items were supplied, prefer a realized change_text for revenue /
    margin / cost topics instead of appending raw narrative what_happened (mixed-language risk).
    LEGACY: if no causal_items input, retain prior behavior using narrative prose for fc_insight.
    """
    trends = analysis.get("trends") or {}
    rev_trend = (trends.get("revenue") or {})
    np_trend = (trends.get("net_profit") or {})
    rev_dir = rev_trend.get("direction", "stable")
    np_dir = np_trend.get("direction", "stable")
    np_loss = np_trend.get("loss_flag", False)

    if np_loss:
        outlook_key = "board.outlook.np_loss"
    elif rev_dir == "improving" and np_dir == "improving":
        outlook_key = "board.outlook.rev_np_improving"
    elif rev_dir == "improving":
        outlook_key = "board.outlook.rev_improving"
    else:
        outlook_key = "board.outlook.stable_focus"

    outlook = realize_ref({"key": outlook_key, "params": {}}, realize_lang)

    extra = ""
    topics_outlook = {"revenue", "margin", "cost"}
    for it in realized_causal:
        if str(it.get("topic", "")).lower() not in topics_outlook:
            continue
        ct = it.get("change_text") or ""
        if _realization_usable(ct):
            extra = ct
            break

    if extra:
        if len(extra) < 120:
            return f"{outlook} {extra}".strip()
        return outlook

    # LEGACY: only when no causal_items were merged into this report path
    if not had_raw_causal:
        narratives = analysis.get("narratives") or []
        fc_insight = ""
        for n in narratives:
            if n.get("domain") in ("revenue", "profit") and n.get("what_happened"):
                fc_insight = n.get("what_happened", "")
                break
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


def _build_highlights(
    analysis: dict,
    executive: dict,
    realize_lang: str,
    realized_causal: list[dict],
) -> list[dict]:
    """
    3–6 factual highlights: metric lines via realize_ref (board.highlight.*), plus
    up to two usable realized causal change lines (single realization path for those).
    LEGACY: top priority line still uses raw executive summary (locale may differ).
    """
    snap = _build_snapshot(analysis, executive)
    trends = analysis.get("trends") or {}
    rev = (trends.get("revenue") or {})
    np_ = (trends.get("net_profit") or {})
    rev_dir = rev.get("direction", "stable")
    np_dir = np_.get("direction", "stable")
    rev_mom = snap.get("revenue_mom_pct")
    np_mom = snap.get("net_profit_mom_pct")

    items: list[dict] = []

    nm = snap.get("net_margin_pct")
    if nm is not None:
        msg = realize_ref(
            {"key": "board.highlight.net_margin", "params": {"nm": _fmt_pct(nm)}},
            realize_lang,
        )
        items.append({"type": "profitability_snapshot", "message": msg, "metrics": ["net_margin_pct"]})

    if rev_mom is not None:
        msg = realize_ref(
            {"key": "board.highlight.rev_momentum", "params": {"rev_mom": _fmt_pct(rev_mom)}},
            realize_lang,
        )
        items.append({"type": "revenue_momentum", "message": msg, "metrics": ["revenue_mom_pct"]})

    if np_mom is not None:
        msg = realize_ref(
            {"key": "board.highlight.np_momentum", "params": {"np_mom": _fmt_pct(np_mom)}},
            realize_lang,
        )
        items.append({"type": "profit_momentum", "message": msg, "metrics": ["net_profit_mom_pct"]})

    if rev_dir in ("improving", "declining") or np_dir in ("improving", "declining"):
        msg = realize_ref(
            {
                "key": "board.highlight.trend_direction",
                "params": {"rev_dir": str(rev_dir), "np_dir": str(np_dir)},
            },
            realize_lang,
        )
        items.append({"type": "trend_direction", "message": msg, "metrics": ["revenue_series", "net_profit_series"]})

    n_causal_hl = 0
    for it in realized_causal:
        if n_causal_hl >= 2:
            break
        ct = it.get("change_text") or ""
        if not _realization_usable(ct):
            continue
        ev = it.get("evidence") if isinstance(it.get("evidence"), dict) else {}
        sm = ev.get("source_metrics") if isinstance(ev.get("source_metrics"), dict) else {}
        mkeys = list(sm.keys())[:8]
        items.append({
            "type": "causal",
            "source": it.get("source"),
            "message": ct,
            "metrics": mkeys,
        })
        n_causal_hl += 1

    pris = (executive.get("top_priorities") or [])
    if pris:
        p0 = pris[0]
        if p0.get("summary"):
            # LEGACY: {summary} text may not match realize_lang
            msg = realize_ref(
                {"key": "board.highlight.top_priority", "params": {"summary": p0.get("summary", "")}},
                realize_lang,
            )
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
    causal_items: list | None = None,
) -> dict:
    """
    Assemble a CFO board report from analysis + executive outputs.
    No financial recalculation. Pure assembly and narrative layer.

    Args:
        analysis:  output of GET /api/v1/analysis/{company_id}
        executive: output of GET /api/v1/companies/{company_id}/executive
        lang:      "en" | "ar" | "tr"

    Returns:
        structured board report dict (same top-level keys as before; optional causal_items input
        merges with analysis[\"causal_items\"] for Wave 2B realization in summary/outlook/highlights).

    """
    safe_lang = lang if lang in ("en", "ar", "tr") else "en"
    realize_lang = (lang or "").strip().lower()

    merged_causal = _board_merge_causal_items(analysis, causal_items)
    realized_causal = realize_causal_items(merged_causal, realize_lang)

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

        "summary":       _build_summary(analysis, executive, realize_lang, realized_causal),
        "risks":         _build_risks(analysis, executive),
        "opportunities": _build_opportunities(executive, analysis),
        "priorities":    _build_priorities(executive),
        "snapshot":      _build_snapshot(analysis, executive),
        "outlook":       _build_outlook(
            analysis,
            realize_lang,
            realized_causal,
            had_raw_causal=bool(merged_causal),
        ),
        # Additive board-grade sections
        "highlights":     _build_highlights(analysis, executive, realize_lang, realized_causal),
        "major_risks":    _build_major_risks(analysis, executive, safe_lang),
        "cost_drivers":   _build_cost_drivers(analysis, executive, safe_lang),
        "recommendations": _build_recommendations(analysis, executive, safe_lang),
        # Phase 1 — financial brain (deterministic; optional inputs)
        "brain_pack":         brain_pack,
        "structured_root_causes": list(phase43_root_causes or []),
        "structured_decisions":   list(cfo_decisions or []),
        "realized_causal_items":  list(realized_causal),
    }
    return out
