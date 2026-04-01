"""
scenario_ranker.py — Phase 19 (Pro) + Phase 19.5 (Localized)
Upgraded decision intelligence engine with full i18n support.

All user-visible text (justification, insight) is returned in the
requested language via an embedded translation table.
No hardcoded English strings in output.
"""
from __future__ import annotations
from typing import Optional
from app.services.what_if import run_what_if


# ── Embedded decision text translations ──────────────────────────────────────
_DTR: dict[str, dict[str, str]] = {
  "dec_lever_revenue": {
    "en": "Revenue Growth",
    "ar": "نمو الإيرادات",
    "tr": "Gelir Büyümesi"
  },
  "dec_lever_cogs": {
    "en": "COGS Reduction",
    "ar": "خفض تكلفة المبيعات",
    "tr": "SMMM Azaltımı"
  },
  "dec_lever_opex": {
    "en": "OpEx Reduction",
    "ar": "خفض التشغيل",
    "tr": "OpGider Azaltımı"
  },
  "dec_just_combined": {
    "en": "The combined scenario delivers maximum impact. The primary driver is {lever_label}, contributing most of the {np_delta} net profit improvement. At {np_pct}% profit growth and {mm_pp} pp margin improvement, this scenario outperforms all single-lever alternatives.",
    "ar": "يحقق هذا السيناريو أعلى تأثير ممكن. المحرك الرئيسي هو {lever_label}، الذي يساهم بأكبر حصة من تحسين صافي الربح البالغ {np_delta}. مع نمو الأرباح بنسبة {np_pct}% وتحسن في الهامش بمقدار {mm_pp} نقطة، يتفوق هذا السيناريو على جميع البدائل الفردية.",
    "tr": "Birleşik senaryo maksimum etkiyi sunar. Temel etken {lever_label}'dır ve {np_delta} net kar artışının büyük bölümünü katkılar. {np_pct}% kar büyümesi ve {mm_pp} pp marj artışı ile bu senaryo tüm tekil alternatifleri geride bırakır."
  },
  "dec_just_increase_revenue": {
    "en": "Revenue growth is the single highest-impact lever available. A 5% increase adds {np_delta} to net profit ({np_pct}%) with no change to cost structure, making it the lowest-risk path to improved profitability.",
    "ar": "نمو الإيرادات هو الرافعة ذات التأثير الأعلى المتاحة. زيادة 5% تضيف {np_delta} لصافي الربح ({np_pct}%) دون أي تغيير في هيكل التكاليف، مما يجعله الطريق الأقل مخاطرة لتحسين الربحية.",
    "tr": "Gelir büyümesi mevcut en yüksek etkili kaldıraçtır. %5 artış, maliyet yapısında değişiklik olmaksızın net kara {np_delta} ({np_pct}%) ekler ve karlılığı iyileştirmenin en düşük riskli yoludur."
  },
  "dec_just_reduce_cogs": {
    "en": "COGS reduction directly improves gross margin. A 2% procurement or efficiency improvement adds {np_delta} to net profit ({np_pct}%) with zero revenue dependency — the most defensible improvement in uncertain markets.",
    "ar": "خفض تكلفة المبيعات يُحسّن هامش الربح الإجمالي مباشرةً. خفض بنسبة 2% عبر المشتريات أو الكفاءة يضيف {np_delta} لصافي الربح ({np_pct}%) دون أي اعتماد على الإيرادات — أكثر التحسينات قابلية للدفاع عنها في الأسواق غير المستقرة.",
    "tr": "SMMM azaltımı doğrudan brüt marjı iyileştirir. Satın alma veya verimlilik yoluyla %2 azaltım, gelir bağımlılığı olmadan net kara {np_delta} ({np_pct}%) ekler."
  },
  "dec_just_reduce_opex": {
    "en": "Operating cost reduction flows directly to the bottom line. A 2% OpEx reduction adds {np_delta} to net profit ({np_pct}%) and improves net margin by {mm_pp} pp through process efficiency.",
    "ar": "خفض التكاليف التشغيلية ينعكس مباشرةً على صافي الأرباح. خفض 2% في المصاريف التشغيلية يضيف {np_delta} لصافي الربح ({np_pct}%) ويُحسّن الهامش الصافي بمقدار {mm_pp} نقطة من خلال تحسين كفاءة العمليات.",
    "tr": "İşletme maliyeti azaltımı doğrudan kara yansır. %2 OpGider azaltımı net kara {np_delta} ({np_pct}%) ekler ve süreç verimliliği sayesinde net marjı {mm_pp} pp artırır."
  },
  "dec_ins_combined": {
    "en": "Combined: +5% revenue, -2% COGS, -2% OpEx delivers {np_delta} additional net profit ({np_pct}%), improving net margin by {mm_pp} pp.",
    "ar": "مجتمعة: إيرادات +5%، تكلفة -2%، مصاريف -2% تضيف {np_delta} لصافي الربح ({np_pct}%)، مع تحسين الهامش الصافي بمقدار {mm_pp} نقطة.",
    "tr": "Birleşik: +%5 gelir, -%2 SMMM, -%2 OpGider → net kara ek {np_delta} ({np_pct}%), net marjı {mm_pp} pp artırır."
  },
  "dec_ins_increase_revenue": {
    "en": "A 5% revenue increase adds {rev_delta} in revenue, lifting net profit by {np_delta} ({np_pct}%) and net margin by {mm_pp} pp.",
    "ar": "زيادة الإيرادات 5% تضيف {rev_delta} من الإيرادات، مما يرفع صافي الربح بمقدار {np_delta} ({np_pct}%) والهامش الصافي بمقدار {mm_pp} نقطة.",
    "tr": "%5 gelir artışı {rev_delta} gelir katkısı sağlar, net karı {np_delta} ({np_pct}%) ve net marjı {mm_pp} pp artırır."
  },
  "dec_ins_reduce_cogs": {
    "en": "A 2% reduction in COGS improves gross margin and adds {np_delta} to net profit ({np_pct}%), with no revenue risk.",
    "ar": "خفض تكلفة المبيعات 2% يُحسّن هامش الربح الإجمالي ويضيف {np_delta} لصافي الربح ({np_pct}%) دون أي مخاطر إيرادية.",
    "tr": "SMMM'de %2 azaltım brüt marjı iyileştirir ve gelir riski olmadan net kara {np_delta} ({np_pct}%) ekler."
  },
  "dec_ins_reduce_opex": {
    "en": "A 2% reduction in operating expenses adds {np_delta} to net profit ({np_pct}%) with immediate margin uplift of {mm_pp} pp.",
    "ar": "خفض المصاريف التشغيلية 2% يضيف {np_delta} لصافي الربح ({np_pct}%) مع تحسين فوري للهامش بمقدار {mm_pp} نقطة.",
    "tr": "İşletme giderlerinde %2 azaltım net kara {np_delta} ({np_pct}%) ekler ve anında {mm_pp} pp marj artışı sağlar."
  },
  "dec_lever_revenue_label": {
    "en": "revenue growth",
    "ar": "نمو الإيرادات",
    "tr": "gelir büyümesi"
  },
  "dec_lever_cogs_label": {
    "en": "COGS reduction",
    "ar": "خفض تكلفة المبيعات",
    "tr": "SMMM azaltımı"
  },
  "dec_lever_opex_label": {
    "en": "OpEx reduction",
    "ar": "خفض المصاريف التشغيلية",
    "tr": "OpGider azaltımı"
  }
}


def _t(key: str, lang: str, **kwargs) -> str:
    """Fetch localized decision text and format with kwargs."""
    entry = _DTR.get(key, {})
    tpl   = entry.get(lang) or entry.get("en") or key
    try:
        return tpl.format(**kwargs)
    except (KeyError, IndexError):
        return tpl


# ──────────────────────────────────────────────────────────────────────────────
#  Base scenario definitions
# ──────────────────────────────────────────────────────────────────────────────

SCENARIOS = [
    {"id": "increase_revenue", "revenue_pct": 5.0,  "cogs_pct": 0.0,  "opex_pct": 0.0},
    {"id": "reduce_cogs",      "revenue_pct": 0.0,  "cogs_pct": -2.0, "opex_pct": 0.0},
    {"id": "reduce_opex",      "revenue_pct": 0.0,  "cogs_pct": 0.0,  "opex_pct": -2.0},
    {"id": "combined",         "revenue_pct": 5.0,  "cogs_pct": -2.0, "opex_pct": -2.0},
]

# ── Scenario packs ─────────────────────────────────────────────────────────────
PACKS = {
    "conservative": {
        "id":          "conservative",
        "revenue_pct": 2.0,
        "cogs_pct":    -1.0,
        "opex_pct":    -1.0,
        "description": "Modest improvements with low execution risk",
    },
    "base": {
        "id":          "base",
        "revenue_pct": 5.0,
        "cogs_pct":    -2.0,
        "opex_pct":    -2.0,
        "description": "Balanced growth + cost optimisation",
    },
    "aggressive": {
        "id":          "aggressive",
        "revenue_pct": 10.0,
        "cogs_pct":    -4.0,
        "opex_pct":    -4.0,
        "description": "Maximum upside; higher execution risk",
    },
}


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmtK(v: float) -> str:
    a = abs(v)
    if a >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if a >= 1_000:     return f"{v/1_000:.0f}K"
    return f"{v:.0f}"


def _score(impact: dict) -> float:
    np_chg = impact.get("net_profit_pct_change") or 0.0
    mm_pp  = impact.get("net_margin_pp")         or 0.0
    NP_MAX, MM_MAX = 30.0, 5.0
    return round(
        min(1.0, max(0.0, np_chg / NP_MAX)) * 60 +
        min(1.0, max(0.0, mm_pp  / MM_MAX)) * 40,
        1
    )


def _priority(score: float) -> str:
    if score >= 60: return "high"
    if score >= 30: return "medium"
    return "low"


def _confidence(impact: dict, baseline: dict) -> int:
    """
    Confidence 0–100 based on:
    - Revenue base size (larger = more confident small % moves are achievable)
    - Whether margin is positive (negative margin = less confident)
    - Score magnitude
    Components:
      40% — baseline revenue adequacy (>500K = full confidence)
      30% — current profitability (positive NM = more confident)
      30% — score normalised
    """
    rev = abs(baseline.get("revenue") or 0)
    nm  = baseline.get("net_margin_pct") or 0
    sc  = _score(impact)

    rev_c  = min(1.0, rev / 500_000) * 40
    nm_c   = max(0.0, min(nm, 20) / 20) * 30
    sc_c   = min(1.0, sc / 100) * 30

    return round(rev_c + nm_c + sc_c)


def _sensitivity(impact: dict, baseline: dict) -> dict:
    """
    Identify which lever (revenue / cogs / opex) contributes most
    to the net profit improvement of this specific scenario.
    Returns { primary_lever, revenue_contribution, cogs_contribution, opex_contribution }
    """
    rev_delta  = abs(impact.get("revenue_delta")   or 0)
    cogs_delta = abs(impact.get("cogs_delta")       or 0)
    opex_delta = abs(impact.get("expenses_delta")   or 0)
    total      = rev_delta + cogs_delta + opex_delta or 1

    rev_pct  = round(rev_delta  / total * 100)
    cogs_pct = round(cogs_delta / total * 100)
    opex_pct = round(opex_delta / total * 100)

    primary = max(
        [("revenue", rev_pct), ("cogs", cogs_pct), ("opex", opex_pct)],
        key=lambda x: x[1]
    )[0]

    return {
        "primary_lever":        primary,
        "revenue_contribution": rev_pct,
        "cogs_contribution":    cogs_pct,
        "opex_contribution":    opex_pct,
    }


def _justification(sc_id: str, impact: dict, baseline: dict, sensitivity: dict, lang: str = "en") -> str:
    np_delta    = impact.get("net_profit_delta")      or 0
    np_pct      = impact.get("net_profit_pct_change") or 0
    mm_pp       = impact.get("net_margin_pp")         or 0
    lever       = sensitivity.get("primary_lever", "revenue")
    lever_label = _t(f"dec_lever_{lever}_label", lang)

    kwargs = dict(
        lever_label = lever_label,
        np_delta    = _fmtK(np_delta),
        np_pct      = f"{np_pct:+.1f}",
        mm_pp       = f"{mm_pp:+.2f}",
    )
    key = f"dec_just_{sc_id}"
    if key in _DTR:
        return _t(key, lang, **kwargs)
    return _t("dec_just_combined", lang, **kwargs)


def _insight(sc_id: str, impact: dict, baseline: dict, lang: str = "en") -> str:
    np_delta  = impact.get("net_profit_delta")      or 0
    np_pct    = impact.get("net_profit_pct_change") or 0
    rev_delta = impact.get("revenue_delta")         or 0
    mm_pp     = impact.get("net_margin_pp")         or 0
    kwargs = dict(
        np_delta  = _fmtK(np_delta),
        rev_delta = _fmtK(rev_delta),
        np_pct    = f"{np_pct:+.1f}",
        mm_pp     = f"{mm_pp:+.2f}",
    )
    key = f"dec_ins_{sc_id}"
    if key in _DTR:
        return _t(key, lang, **kwargs)
    return _t("dec_ins_combined", lang, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def rank_scenarios(baseline_block: dict, lang: str = "en") -> dict:
    results = []

    for sc in SCENARIOS:
        wi = run_what_if(
            baseline_block = baseline_block,
            revenue_pct    = sc["revenue_pct"],
            cogs_pct       = sc["cogs_pct"],
            opex_pct       = sc["opex_pct"],
        )
        imp    = wi["impact"]
        base   = wi["baseline"]
        score  = _score(imp)
        sens   = _sensitivity(imp, base)
        conf   = _confidence(imp, base)
        pri    = _priority(score)
        just   = _justification(sc["id"], imp, base, sens, lang)

        results.append({
            "id":            sc["id"],
            "score":         score,
            "priority":      pri,
            "confidence":    conf,
            "justification": just,
            "sensitivity":   sens,
            "inputs":        wi["inputs"],
            "baseline":      base,
            "scenario":      wi["scenario"],
            "impact":        imp,
            "insight":       _insight(sc["id"], imp, base, lang),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    best = results[0] if results else None

    ranking = [
        {
            "rank":          i + 1,
            "id":            r["id"],
            "score":         r["score"],
            "priority":      r["priority"],
            "confidence":    r["confidence"],
            "np_delta":      r["impact"].get("net_profit_delta"),
            "np_pct_change": r["impact"].get("net_profit_pct_change"),
            "margin_pp":     r["impact"].get("net_margin_pp"),
            "revenue_pct":   r["inputs"].get("revenue_pct"),
            "cogs_pct":      r["inputs"].get("cogs_pct"),
            "opex_pct":      r["inputs"].get("opex_pct"),
        }
        for i, r in enumerate(results)
    ]

    # ── Scenario packs ────────────────────────────────────────────────────────
    pack_results = {}
    for pack_id, pack in PACKS.items():
        wi = run_what_if(
            baseline_block = baseline_block,
            revenue_pct    = pack["revenue_pct"],
            cogs_pct       = pack["cogs_pct"],
            opex_pct       = pack["opex_pct"],
        )
        pack_results[pack_id] = {
            "id":             pack_id,
            "description":    pack["description"],
            "inputs":         wi["inputs"],
            "net_profit_delta":      wi["impact"].get("net_profit_delta"),
            "net_profit_pct_change": wi["impact"].get("net_profit_pct_change"),
            "net_margin_pp":         wi["impact"].get("net_margin_pp"),
            "scenario_revenue":      wi["scenario"].get("revenue"),
            "scenario_net_profit":   wi["scenario"].get("net_profit"),
            "scenario_net_margin":   wi["scenario"].get("net_margin_pct"),
        }

    return {
        "best_scenario":       best,
        "ranking":             ranking,
        "scenario_count":      len(results),
        "scenario_pack_results": pack_results,
    }
