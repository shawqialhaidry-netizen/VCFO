"""
management_report.py — Phase 20
Composes a board-ready management report from existing VCFO outputs.

Design rules:
  - Pure function — no DB, no HTTP
  - All inputs are pre-built dicts from existing services
  - Output is a structured JSON ready for PDF/board formatting
  - Language-aware section titles via embedded templates
  - Safe on any missing section — each block degrades gracefully
"""
from __future__ import annotations
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
#  Format helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmtK(v) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
        a = abs(f)
        s = "-" if f < 0 else ""
        if a >= 1_000_000: return f"{s}{a/1_000_000:.1f}M"
        if a >= 1_000:     return f"{s}{a/1_000:.0f}K"
        return f"{s}{a:.0f}"
    except (TypeError, ValueError):
        return str(v)


def _fmtP(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return str(v)


def _chg(v) -> str:
    if v is None:
        return ""
    try:
        f = float(v)
        return f"{'+' if f >= 0 else ''}{f:.1f}%"
    except (TypeError, ValueError):
        return str(v)


def _management_limitation(lang: str, topic: str) -> str:
    if lang == "ar":
        return f"لا توجد أدلة كمية كافية لصياغة قراءة إدارية موثوقة بشأن {topic}."
    if lang == "tr":
        return f"{topic} için güvenilir yönetim anlatısı kurmaya yetecek nicel kanıt yok."
    return f"There is not enough quantitative evidence to produce a management-grade narrative for {topic}."


# ──────────────────────────────────────────────────────────────────────────────
#  Section builders
# ──────────────────────────────────────────────────────────────────────────────

def _build_kpi_snapshot(annual: dict, currency: str) -> dict:
    ytd     = annual.get("ytd")     or {}
    latest  = annual.get("latest_month") or {}
    comp    = annual.get("comparisons") or {}
    ytd_cmp = (comp.get("ytd_vs_prior_ytd") or {}).get("changes") or {}
    mom     = (comp.get("latest_month_vs_prior_month") or {}).get("changes") or {}

    return {
        "currency": currency or "USD",
        "latest_month": {
            "period":          latest.get("period"),
            "revenue":         latest.get("revenue"),
            "revenue_fmt":     _fmtK(latest.get("revenue")),
            "net_profit":      latest.get("net_profit"),
            "net_profit_fmt":  _fmtK(latest.get("net_profit")),
            "net_margin_pct":  latest.get("net_margin_pct"),
            "net_margin_fmt":  _fmtP(latest.get("net_margin_pct")),
            "gross_margin_pct": latest.get("gross_margin_pct"),
        },
        "ytd": {
            "year":            ytd.get("year"),
            "month_count":     ytd.get("month_count"),
            "revenue":         ytd.get("revenue"),
            "revenue_fmt":     _fmtK(ytd.get("revenue")),
            "net_profit":      ytd.get("net_profit"),
            "net_profit_fmt":  _fmtK(ytd.get("net_profit")),
            "net_margin_pct":  ytd.get("net_margin_pct"),
            "net_margin_fmt":  _fmtP(ytd.get("net_margin_pct")),
            "revenue_vs_prior_pct":    ytd_cmp.get("revenue"),
            "net_profit_vs_prior_pct": ytd_cmp.get("net_profit"),
            "margin_vs_prior_pp":      ytd_cmp.get("net_margin_pct"),
            "has_gaps":        ytd.get("has_gaps", False),
        },
        "mom_net_margin_pp": mom.get("net_margin_pct"),
    }


def _build_annual_summary(annual: dict, currency: str) -> dict:
    fy_list = annual.get("full_years") or []
    ytd     = annual.get("ytd") or {}
    ytd_pr  = annual.get("ytd_prior") or {}

    fy_rows = []
    for fy in fy_list[:3]:   # max 3 years
        fy_rows.append({
            "year":            fy.get("year"),
            "complete":        fy.get("complete", False),
            "month_count":     fy.get("month_count"),
            "revenue":         fy.get("revenue"),
            "revenue_fmt":     _fmtK(fy.get("revenue")),
            "net_profit":      fy.get("net_profit"),
            "net_profit_fmt":  _fmtK(fy.get("net_profit")),
            "net_margin_fmt":  _fmtP(fy.get("net_margin_pct")),
            "has_gaps":        fy.get("has_gaps", False),
        })

    ytd_comparison = None
    if ytd and ytd_pr:
        comp    = annual.get("comparisons") or {}
        ytd_cmp = (comp.get("ytd_vs_prior_ytd") or {}).get("changes") or {}
        ytd_comparison = {
            "current_year":    ytd.get("year"),
            "prior_year":      ytd_pr.get("year"),
            "months_compared": ytd.get("month_count"),
            "revenue_chg_pct": ytd_cmp.get("revenue"),
            "np_chg_pct":      ytd_cmp.get("net_profit"),
            "margin_pp":       ytd_cmp.get("net_margin_pct"),
        }

    return {
        "full_years":    fy_rows,
        "ytd_comparison": ytd_comparison,
        "currency":       currency or "USD",
    }


def _build_decision_summary(decisions: dict, lang: str = "en") -> dict:
    best    = decisions.get("best_scenario") or {}
    ranking = decisions.get("ranking") or []
    packs   = decisions.get("scenario_pack_results") or {}

    SC_LABELS = {
        "combined":         "Accelerate Growth",
        "increase_revenue": "Grow Revenue",
        "reduce_cogs":      "Optimize Cost of Goods Sold",
        "reduce_opex":      "Reduce Operating Expenses",
    }

    best_block = {
            "id":             best.get("id"),
            "label":          SC_LABELS.get(best.get("id",""), best.get("id","")),
            "score":          best.get("score"),
            "priority":       best.get("priority"),
            "confidence":     best.get("confidence"),
            "justification":  best.get("justification"),
            "insight":        best.get("insight"),
            "np_delta":       (best.get("impact") or {}).get("net_profit_delta"),
            "np_delta_fmt":   _fmtK((best.get("impact") or {}).get("net_profit_delta")),
            "np_pct":         (best.get("impact") or {}).get("net_profit_pct_change"),
            "margin_pp":      (best.get("impact") or {}).get("net_margin_pp"),
        } if best else None

    narrative = _management_limitation(lang, "the decision set")
    if best_block:
        label = best_block.get("label") or "the leading scenario"
        np_pct = best_block.get("np_pct")
        margin_pp = best_block.get("margin_pp")
        if lang == "ar":
            narrative = f"أفضل سيناريو حالياً هو {label} بنتيجة {best_block.get('score')}/100"
            if np_pct is not None:
                narrative += f"، مع أثر متوقع على صافي الربح {np_pct:+.1f}%"
            if margin_pp is not None:
                narrative += f" وتحسن هامش بنحو {margin_pp:+.1f} نقطة."
        elif lang == "tr":
            narrative = f"Şu an en güçlü senaryo {label}; skor {best_block.get('score')}/100"
            if np_pct is not None:
                narrative += f", net kâr etkisi yaklaşık %{np_pct:+.1f}"
            if margin_pp is not None:
                narrative += f" ve marj etkisi {margin_pp:+.1f} puan."
        else:
            narrative = f"The leading scenario is {label} with a score of {best_block.get('score')}/100"
            if np_pct is not None:
                narrative += f", implying about {np_pct:+.1f}% net profit change"
            if margin_pp is not None:
                narrative += f" and {margin_pp:+.1f}pp margin impact."

    return {
        "best": best_block,
        "ranking_top3": [
            {
                "rank":  sc.get("rank"),
                "id":    sc.get("id"),
                "label": SC_LABELS.get(sc.get("id",""), sc.get("id","")),
                "score": sc.get("score"),
                "priority": sc.get("priority"),
                "np_pct": sc.get("np_pct_change"),
                "margin_pp": sc.get("margin_pp"),
            }
            for sc in ranking[:3]
        ],
        "scenario_packs": {
            pid: {
                "id":          pid,
                "np_pct":      pk.get("net_profit_pct_change"),
                "margin_pp":   pk.get("net_margin_pp"),
                "np_delta_fmt": _fmtK(pk.get("net_profit_delta")),
            }
            for pid, pk in packs.items()
        },
        "narrative": narrative,
    }


def _build_what_if_summary(what_if: dict, lang: str = "en") -> Optional[dict]:
    if not what_if or what_if.get("error"):
        return None
    imp  = what_if.get("impact") or {}
    inp  = what_if.get("inputs") or {}
    base = what_if.get("baseline") or {}
    sc   = what_if.get("scenario") or {}
    narrative = _management_limitation(lang, "the what-if case")
    np_pct = imp.get("net_profit_pct_change")
    margin_pp = imp.get("net_margin_pp")
    if lang == "ar":
        narrative = "يعرض هذا السيناريو أثر المدخلات المفترضة على الإيراد والربحية"
        if np_pct is not None:
            narrative += f"، مع تغير متوقع في صافي الربح {np_pct:+.1f}%"
        if margin_pp is not None:
            narrative += f" وتغير هامش {margin_pp:+.1f} نقطة."
    elif lang == "tr":
        narrative = "Bu senaryo, varsayılan girdilerin gelir ve kârlılık üzerindeki etkisini gösteriyor"
        if np_pct is not None:
            narrative += f"; net kâr değişimi yaklaşık %{np_pct:+.1f}"
        if margin_pp is not None:
            narrative += f" ve marj etkisi {margin_pp:+.1f} puan."
    else:
        narrative = "This scenario translates the selected inputs into revenue and profitability impact"
        if np_pct is not None:
            narrative += f", with about {np_pct:+.1f}% net profit change"
        if margin_pp is not None:
            narrative += f" and {margin_pp:+.1f}pp margin movement."

    return {
        "inputs":            inp,
        "baseline_revenue":  _fmtK(base.get("revenue")),
        "baseline_np":       _fmtK(base.get("net_profit")),
        "baseline_nm":       _fmtP(base.get("net_margin_pct")),
        "scenario_revenue":  _fmtK(sc.get("revenue")),
        "scenario_np":       _fmtK(sc.get("net_profit")),
        "scenario_nm":       _fmtP(sc.get("net_margin_pct")),
        "np_delta":          imp.get("net_profit_delta"),
        "np_delta_fmt":      _fmtK(imp.get("net_profit_delta")),
        "np_pct":            _chg(imp.get("net_profit_pct_change")),
        "margin_pp":         imp.get("net_margin_pp"),
        "narrative":         narrative,
    }


def _extract_risks(narrative: dict, warnings: list) -> list[str]:
    risks = list(narrative.get("risks") or [])
    for w in (warnings or []):
        if w and w not in risks:
            risks.append(w)
    return risks[:6]   # cap at 6 for board readability


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_management_report(
    company:      dict,
    basis:        str,
    period_label: str,
    status:       str,
    annual:       dict,
    decisions:    dict,
    what_if:      dict,
    narrative:    dict,
    warnings:     list,
    currency:     str = "",
    lang:         str = "en",
) -> dict:
    """
    Compose a structured management/board report.

    Returns a single JSON-serialisable dict with clearly named sections,
    ready for PDF rendering, board presentation, or API consumption.
    """
    kpi       = _build_kpi_snapshot(annual, currency)
    ann       = _build_annual_summary(annual, currency)
    dec       = _build_decision_summary(decisions, lang)
    wi_sum    = _build_what_if_summary(what_if, lang)
    risks     = _extract_risks(narrative, warnings)
    exec_summary = narrative.get("executive_summary") or _management_limitation(lang, "the executive summary")
    rec_action = narrative.get("recommended_action") or _management_limitation(lang, "the recommended action")

    return {
        # ── Meta ──────────────────────────────────────────────────────────────
        "report_type":   "management_report",
        "version":       "20.0",
        "lang":          lang,
        "company": {
            "id":       company.get("id"),
            "name":     company.get("name"),
            "currency": currency or "USD",
        },
        "basis":         basis,
        "period_label":  period_label,
        "status":        status,

        # ── Sections ──────────────────────────────────────────────────────────
        "sections": {

            "executive_summary": {
                "title":   "executive_summary",
                "content": exec_summary,
                "status":  status,
            },

            "kpi_snapshot": {
                "title":   "kpi_snapshot",
                "data":    kpi,
            },

            "annual_summary": {
                "title":   "annual_summary",
                "data":    ann,
            },

            "what_if_summary": {
                "title":   "what_if_summary",
                "data":    wi_sum,
            },

            "decision_summary": {
                "title":   "decision_summary",
                "data":    dec,
            },

            "key_takeaways": {
                "title":   "key_takeaways",
                "items":   narrative.get("key_takeaways") or [],
            },

            "key_risks": {
                "title":   "key_risks",
                "items":   risks,
            },

            "recommended_action": {
                "title":   "recommended_action",
                "content": rec_action,
                "scenario_id":    (dec.get("best") or {}).get("id"),
                "scenario_label": (dec.get("best") or {}).get("label"),
                "priority":       (dec.get("best") or {}).get("priority"),
                "confidence":     (dec.get("best") or {}).get("confidence"),
            },
        },

        "warnings": warnings or [],
    }
