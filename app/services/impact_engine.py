"""
impact_engine.py — Phase 32
CFO Impact Engine: quantifies the financial effect of each decision.

Answers: "If we act on this decision — what will happen financially?"

Design principles:
  - Simple explainable math only (no ML)
  - Always provide a range (low / base / high)
  - Avoid fake precision — round meaningfully
  - Confidence reflects data quality + assumption strength
  - Industry-agnostic language
  - Fully localized EN / AR / TR

Input:  decisions list + intelligence dict (from /executive)
Output: list of impact dicts, one per decision
"""
from __future__ import annotations
from typing import Optional
import math


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get(d: dict, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict): return default
        d = d.get(k, default)
    return d


def _v(ratios: dict, cat: str, metric: str) -> Optional[float]:
    return _get(ratios, cat, metric, "value")


def _round_sig(v: float, sig: int = 2) -> float:
    """Round to sig significant figures."""
    if v == 0: return 0
    try:
        magnitude = 10 ** (sig - 1 - int(math.floor(math.log10(abs(v)))))
        return round(v * magnitude) / magnitude
    except (ValueError, OverflowError):
        return round(v, 2)


def _fmt_currency(v: float) -> str:
    """Format a currency value cleanly."""
    if v is None: return "—"
    a = abs(v)
    s = "+" if v >= 0 else "-"
    if a >= 1_000_000: return f"{s}{a/1_000_000:.1f}M"
    if a >= 1_000:     return f"{s}{a/1_000:.0f}K"
    return f"{s}{a:.0f}"


def _fmt_pct(v: float) -> str:
    if v is None: return "—"
    return f"{'+' if v >= 0 else ''}{v:.1f}%"


# ──────────────────────────────────────────────────────────────────────────────
#  Localized impact descriptions
# ──────────────────────────────────────────────────────────────────────────────

_IT = {
    # Liquidity
    "cash_from_dso": {
        "en": "Reducing DSO by {dso_days} days could unlock approximately {value} in cash within {timeframe}.",
        "ar": "تخفيض أيام القبض بـ {dso_days} يوم قد يحرر تقريباً {value} نقداً خلال {timeframe}.",
        "tr": "DSO'yu {dso_days} gün azaltmak {timeframe} içinde yaklaşık {value} nakit serbest bırakabilir.",
    },
    "cash_from_wc": {
        "en": "Improving working capital management could release approximately {value} within {timeframe}.",
        "ar": "تحسين إدارة رأس المال العامل قد يحرر تقريباً {value} خلال {timeframe}.",
        "tr": "İşletme sermayesi yönetimini iyileştirmek {timeframe} içinde yaklaşık {value} serbest bırakabilir.",
    },
    # Profitability
    "margin_improvement": {
        "en": "Reducing costs or improving pricing by {action_pct}% could add approximately {value} to annual profit.",
        "ar": "تخفيض التكاليف أو تحسين التسعير بنسبة {action_pct}% قد يضيف تقريباً {value} للأرباح السنوية.",
        "tr": "Maliyetleri %{action_pct} azaltmak veya fiyatlandırmayı iyileştirmek yıllık kâra yaklaşık {value} ekleyebilir.",
    },
    "margin_from_cogs": {
        "en": "A {action_pct}% reduction in cost of service could improve net profit by approximately {value}.",
        "ar": "تخفيض تكلفة الخدمة بـ {action_pct}% قد يحسن صافي الربح بحوالي {value}.",
        "tr": "Hizmet maliyetini %{action_pct} azaltmak net kârı yaklaşık {value} iyileştirebilir.",
    },
    # Efficiency
    "cash_from_ccc": {
        "en": "Reducing the cash cycle by {ccc_days} days could free approximately {value} in working capital.",
        "ar": "تخفيض دورة النقد بـ {ccc_days} يوم قد يحرر تقريباً {value} من رأس المال العامل.",
        "tr": "Nakit döngüsünü {ccc_days} gün kısaltmak işletme sermayesinde yaklaşık {value} serbest bırakabilir.",
    },
    "cash_from_inventory": {
        "en": "Improving inventory turnover to {target_it}x could release approximately {value} in tied-up capital.",
        "ar": "تحسين دوران المخزون إلى {target_it} مرة قد يحرر تقريباً {value} من رأس المال المُجمَّد.",
        "tr": "Stok devir hızını {target_it}x'e çıkarmak yaklaşık {value} bağlı sermaye serbest bırakabilir.",
    },
    # Leverage
    "risk_reduction": {
        "en": "Reducing debt by {reduction_pct}% could lower annual interest burden by approximately {value}.",
        "ar": "تخفيض الديون بـ {reduction_pct}% قد يخفض عبء الفائدة السنوي بحوالي {value}.",
        "tr": "Borcu %{reduction_pct} azaltmak yıllık faiz yükünü yaklaşık {value} düşürebilir.",
    },
    # Growth
    "revenue_upside": {
        "en": "A {rev_pct}% revenue improvement could add approximately {value} to annual profit at current margins.",
        "ar": "تحسين الإيرادات بـ {rev_pct}% قد يضيف تقريباً {value} للأرباح السنوية بالهوامش الحالية.",
        "tr": "Geliri %{rev_pct} artırmak mevcut marjlarla yıllık kâra yaklaşık {value} ekleyebilir.",
    },
    # Fallback
    "generic_improvement": {
        "en": "This action should improve the financial position within {timeframe}, but the current dataset is not sufficient to quantify the effect responsibly.",
        "ar": "تنفيذ هذا الإجراء من المتوقع أن يحسن الوضع المالي بشكل ملموس خلال {timeframe}.",
        "tr": "Bu aksiyonu uygulamak {timeframe} içinde finansal pozisyonu önemli ölçüde iyileştirmesi bekleniyor.",
    },
}


def _desc(key: str, lang: str, **kwargs) -> str:
    entry = _IT.get(key, _IT["generic_improvement"])
    tpl   = entry.get(lang) or entry.get("en") or ""
    try:    return tpl.format(**kwargs)
    except: return tpl


# ──────────────────────────────────────────────────────────────────────────────
#  Per-domain impact calculators
# ──────────────────────────────────────────────────────────────────────────────

def _estimate_daily_revenue(ratios: dict, kpi_block: dict) -> Optional[float]:
    """Estimate daily revenue from available data."""
    # Try KPI block first (most accurate)
    rev_monthly = _get(kpi_block, "kpis", "revenue", "value")
    if rev_monthly and rev_monthly > 0:
        return rev_monthly / 30

    # Fallback: back-calculate from net profit + net margin
    nm  = _v(ratios, "profitability", "net_margin_pct")
    np_ = _v(ratios, "profitability", "net_profit")
    if nm and nm > 0 and np_ and np_ > 0:
        rev_est = abs(np_) / (nm / 100)
        return rev_est / 30  # approximate monthly → daily

    return None


def _liquidity_impact(decision: dict, ratios: dict, kpi_block: dict,
                       lang: str) -> dict:
    """Quantify cash impact of liquidity-related decisions."""
    dso = _v(ratios, "efficiency", "dso_days")
    wc  = _v(ratios, "liquidity",  "working_capital")
    daily_rev = _estimate_daily_revenue(ratios, kpi_block)

    # DSO reduction scenario
    if dso and dso > 45 and daily_rev:
        dso_reduction = min(15, dso - 30)  # aim to cut to ~30d, max 15d reduction
        base  = _round_sig(daily_rev * dso_reduction)
        low   = _round_sig(base * 0.6)
        high  = _round_sig(base * 1.5)
        conf  = 75 if dso > 60 else 65
        return {
            "type":        "cash",
            "metric":      "dso_reduction",
            "value":       base,
            "unit":        "currency",
            "description": _desc("cash_from_dso", lang,
                                  dso_days=round(dso_reduction),
                                  value=_fmt_currency(base),
                                  timeframe=decision.get("timeframe","30 days")),
            "assumption":  f"Reduce DSO by ~{round(dso_reduction)} days",
            "range":       {"low": low, "high": high},
            "confidence":  conf,
        }

    # Working capital improvement
    if wc and wc < 0 and daily_rev:
        base  = _round_sig(daily_rev * 10)  # 10 days improvement
        low   = _round_sig(base * 0.5)
        high  = _round_sig(base * 1.4)
        return {
            "type":        "cash",
            "metric":      "working_capital",
            "value":       base,
            "unit":        "currency",
            "description": _desc("cash_from_wc", lang,
                                  value=_fmt_currency(base),
                                  timeframe=decision.get("timeframe","60 days")),
            "assumption":  "Improve collections + extend payables by ~10 days",
            "range":       {"low": low, "high": high},
            "confidence":  60,
        }

    return _generic_impact(decision, daily_rev, lang)


def _profitability_impact(decision: dict, ratios: dict, kpi_block: dict,
                           lang: str) -> dict:
    """Quantify profit impact of margin-related decisions."""
    nm   = _v(ratios, "profitability", "net_margin_pct")
    gm   = _v(ratios, "profitability", "gross_margin_pct")
    daily_rev = _estimate_daily_revenue(ratios, kpi_block)

    if daily_rev:
        rev_annual = daily_rev * 365

        # If gross margin is weak: target cost reduction
        if gm is not None and gm < 38:
            action_pct = 2.0   # 2% cost reduction assumption
            base  = _round_sig(rev_annual * (action_pct / 100))
            low   = _round_sig(base * 0.5)
            high  = _round_sig(base * 1.8)
            conf  = 70 if gm < 30 else 60
            return {
                "type":        "margin",
                "metric":      "gross_margin_improvement",
                "value":       base,
                "unit":        "currency",
                "description": _desc("margin_from_cogs", lang,
                                      action_pct=action_pct,
                                      value=_fmt_currency(base)),
                "assumption":  f"2% reduction in cost of service on ~{_fmt_currency(rev_annual)} annual revenue",
                "range":       {"low": low, "high": high},
                "confidence":  conf,
            }

        # Net margin weak: general overhead reduction
        if nm is not None and nm < 10:
            action_pct = 1.5
            base  = _round_sig(rev_annual * (action_pct / 100))
            low   = _round_sig(base * 0.5)
            high  = _round_sig(base * 2.0)
            return {
                "type":        "margin",
                "metric":      "net_margin_improvement",
                "value":       base,
                "unit":        "currency",
                "description": _desc("margin_improvement", lang,
                                      action_pct=action_pct,
                                      value=_fmt_currency(base)),
                "assumption":  f"1.5% overhead reduction on {_fmt_currency(rev_annual)} revenue",
                "range":       {"low": low, "high": high},
                "confidence":  65,
            }

    return _generic_impact(decision, daily_rev, lang)


def _efficiency_impact(decision: dict, ratios: dict, kpi_block: dict,
                        lang: str) -> dict:
    """Quantify working capital freed by efficiency improvements."""
    ccc = _v(ratios, "efficiency", "ccc_days")
    it  = _v(ratios, "efficiency", "inventory_turnover")
    daily_rev = _estimate_daily_revenue(ratios, kpi_block)

    # Long cash cycle → reduce by 15 days
    if ccc and ccc > 60 and daily_rev:
        reduction = min(20, ccc - 40)
        base  = _round_sig(daily_rev * reduction)
        low   = _round_sig(base * 0.55)
        high  = _round_sig(base * 1.6)
        conf  = 70 if ccc > 80 else 60
        return {
            "type":        "cash",
            "metric":      "ccc_reduction",
            "value":       base,
            "unit":        "currency",
            "description": _desc("cash_from_ccc", lang,
                                  ccc_days=round(reduction),
                                  value=_fmt_currency(base)),
            "assumption":  f"Reduce CCC by ~{round(reduction)} days",
            "range":       {"low": low, "high": high},
            "confidence":  conf,
        }

    # Slow inventory → improve turnover
    if it and it < 4 and daily_rev:
        target_it = 6.0
        rev_annual = daily_rev * 365
        # Inventory estimate: COGS / IT; COGS ≈ revenue × (1 - gm%)
        gm = _v(ratios, "profitability", "gross_margin_pct") or 35
        cogs = rev_annual * (1 - gm / 100)
        inv_current = cogs / it
        inv_target  = cogs / target_it
        base  = _round_sig(inv_current - inv_target)
        low   = _round_sig(base * 0.5)
        high  = _round_sig(base * 1.4)
        return {
            "type":        "cash",
            "metric":      "inventory_reduction",
            "value":       base,
            "unit":        "currency",
            "description": _desc("cash_from_inventory", lang,
                                  target_it=target_it,
                                  value=_fmt_currency(base)),
            "assumption":  f"Improve inventory turns from {it:.1f}x to {target_it:.1f}x",
            "range":       {"low": low, "high": high},
            "confidence":  60,
        }

    return _generic_impact(decision, daily_rev, lang)


def _leverage_impact(decision: dict, ratios: dict, kpi_block: dict,
                      lang: str) -> dict:
    """Quantify risk reduction from debt management."""
    de  = _v(ratios, "leverage", "debt_to_equity")
    dr  = _v(ratios, "leverage", "debt_ratio_pct")
    daily_rev = _estimate_daily_revenue(ratios, kpi_block)

    if de and de > 1.5:
        # Estimate interest burden: assume 8% avg rate on total debt
        rev_annual  = (daily_rev or 0) * 365
        # Rough debt estimate: de × equity; equity ≈ assets × (1 - dr/100)
        np_  = _v(ratios, "profitability", "net_profit")
        nm   = _v(ratios, "profitability", "net_margin_pct")
        if np_ and nm and nm > 0:
            rev_est = abs(np_) / (nm / 100)
            total_liab = rev_est * (dr / 100) if dr else rev_est * 0.5
            interest_saved = _round_sig(total_liab * 0.08 * 0.20)  # 20% debt reduction × 8%
            low  = _round_sig(interest_saved * 0.5)
            high = _round_sig(interest_saved * 2.0)
            reduction_pct = 20
            return {
                "type":        "risk",
                "metric":      "interest_burden",
                "value":       interest_saved,
                "unit":        "currency",
                "description": _desc("risk_reduction", lang,
                                      reduction_pct=reduction_pct,
                                      value=_fmt_currency(interest_saved)),
                "assumption":  f"20% debt reduction at assumed 8% average interest rate",
                "range":       {"low": low, "high": high},
                "confidence":  55,
            }

    return _generic_impact(decision, daily_rev, lang)


def _growth_impact(decision: dict, ratios: dict, kpi_block: dict,
                    lang: str) -> dict:
    """Quantify profit upside from revenue growth."""
    nm = _v(ratios, "profitability", "net_margin_pct")
    daily_rev = _estimate_daily_revenue(ratios, kpi_block)

    if daily_rev and nm and nm > 0:
        rev_annual = daily_rev * 365
        rev_pct    = 5.0   # 5% revenue growth assumption
        base  = _round_sig(rev_annual * (rev_pct / 100) * (nm / 100))
        low   = _round_sig(base * 0.4)
        high  = _round_sig(base * 2.5)
        return {
            "type":        "margin",
            "metric":      "revenue_growth",
            "value":       base,
            "unit":        "currency",
            "description": _desc("revenue_upside", lang,
                                  rev_pct=rev_pct,
                                  value=_fmt_currency(base)),
            "assumption":  f"5% revenue growth at {nm:.1f}% current net margin",
            "range":       {"low": low, "high": high},
            "confidence":  60,
        }

    return _generic_impact(decision, daily_rev, lang)


def _generic_impact(decision: dict, daily_rev: Optional[float], lang: str) -> dict:
    """Fallback: no numeric estimate available."""
    return {
        "type":        "qualitative",
        "metric":      "general",
        "value":       None,
        "unit":        "qualitative",
        "description": _desc("generic_improvement", lang,
                               timeframe=decision.get("timeframe","30-60 days")),
        "assumption":  "Qualitative only — insufficient evidence for a responsible numeric estimate",
        "range":       {"low": None, "high": None},
        "confidence":  40,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

_DOMAIN_FN = {
    "liquidity":     _liquidity_impact,
    "profitability": _profitability_impact,
    "efficiency":    _efficiency_impact,
    "leverage":      _leverage_impact,
    "growth":        _growth_impact,
}


def build_decision_impacts(
    decisions:    list,
    intelligence: dict,
    kpi_block:    dict,
    lang:         str = "en",
) -> list[dict]:
    """
    For each decision, estimate the financial impact of executing it.

    Args:
        decisions:    output of build_cfo_decisions()["decisions"]
        intelligence: output of build_intelligence()
        kpi_block:    output of build_kpi_block()
        lang:         "en" | "ar" | "tr"

    Returns:
        list of {
            decision_key, domain, impact, range, confidence
        }
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"

    ratios = intelligence.get("ratios", {})
    kpis   = kpi_block    or {}
    result = []

    for dec in decisions:
        domain = dec.get("domain", "")
        fn     = _DOMAIN_FN.get(domain)

        if fn:
            impact_data = fn(dec, ratios, kpis, lang)
        else:
            daily_rev = _estimate_daily_revenue(ratios, kpis)
            impact_data = _generic_impact(dec, daily_rev, lang)

        result.append({
            "decision_key": dec.get("key", domain),
            "domain":       domain,
            "impact":       impact_data,
        })

    return result
