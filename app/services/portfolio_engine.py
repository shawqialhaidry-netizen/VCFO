"""
portfolio_engine.py — Phase 28
Portfolio-level intelligence: compare and rank multiple companies.

Input:  list of { company_id, company_name, intelligence } dicts
        where intelligence = output of fin_intelligence.build_intelligence()

Logic:
  1. Extract key metrics per company
  2. Normalise to 0–100 score per dimension
  3. Rank by: health, profitability, liquidity, efficiency, growth
  4. Detect outliers (best/worst performers per metric)
  5. Compute portfolio summary averages and distribution

Output:
  {
    "companies":  [ranked company cards],
    "rankings":   { health, profitability, liquidity, efficiency },
    "outliers":   { best, worst, at_risk },
    "summary":    { avg_health, avg_margin, ... },
    "distribution": { excellent, good, warning, risk },
  }

Design:
  - Pure function — no DB
  - Normalisation uses min-max within the portfolio
  - Outlier = value > 1.5 std-devs from portfolio mean
  - Fully localized EN / AR / TR
  - Industry-agnostic
"""
from __future__ import annotations
import math
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


def _v(intel: dict, category: str, metric: str) -> Optional[float]:
    return _get(intel, "ratios", category, metric, "value")


def _r2(v) -> Optional[float]:
    try:    return round(float(v), 2)
    except: return None


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def _norm_score(val: Optional[float], vals: list[float], higher_is_better: bool = True) -> int:
    """
    Normalise val to 0–100 within the portfolio.
    Returns 50 (neutral) if only one company or val is None.
    """
    clean = [v for v in vals if v is not None]
    if val is None or len(clean) <= 1:
        return 50
    lo, hi = min(clean), max(clean)
    if abs(hi - lo) < 0.001:
        return 50
    frac = (val - lo) / (hi - lo)
    if not higher_is_better:
        frac = 1 - frac
    return round(frac * 100)


def _status_from_health(score: int) -> str:
    if score >= 80: return "excellent"
    if score >= 60: return "good"
    if score >= 40: return "warning"
    return "risk"


# ──────────────────────────────────────────────────────────────────────────────
#  Dimension scorers
# ──────────────────────────────────────────────────────────────────────────────

def _profitability_score(intel: dict) -> Optional[float]:
    nm  = _v(intel, "profitability", "net_margin_pct")
    gm  = _v(intel, "profitability", "gross_margin_pct")
    if nm is None and gm is None:
        return None
    parts = [x for x in [nm, (gm or 0) * 0.5] if x is not None]
    return round(sum(parts) / len(parts), 2)


def _liquidity_score(intel: dict) -> Optional[float]:
    cr = _v(intel, "liquidity", "current_ratio")
    qr = _v(intel, "liquidity", "quick_ratio")
    if cr is None:
        return None
    parts = [v for v in [cr * 20, (qr or 0) * 15] if v is not None]
    return round(min(100, sum(parts) / len(parts)), 2)


def _efficiency_score(intel: dict) -> Optional[float]:
    dso = _v(intel, "efficiency", "dso_days")
    ccc = _v(intel, "efficiency", "ccc_days")
    it  = _v(intel, "efficiency", "inventory_turnover")
    # Lower DSO/CCC is better; higher IT is better
    parts = []
    if dso is not None: parts.append(max(0, 100 - dso))          # 0 days = 100
    if ccc is not None: parts.append(max(0, 100 - ccc * 0.5))    # 0 days = 100
    if it  is not None: parts.append(min(100, it * 10))           # 10x/yr = 100
    return round(sum(parts) / len(parts), 2) if parts else None


def _growth_score(intel: dict) -> Optional[float]:
    rev_dir = _get(intel, "trends", "revenue", "direction")
    ytd_rev = _get(intel, "trends", "revenue", "ytd_vs_prior")
    score = 50  # neutral baseline
    if rev_dir == "up":    score += 25
    elif rev_dir == "stable": score += 10
    elif rev_dir == "down":   score -= 20
    if ytd_rev is not None:
        score += min(25, max(-25, ytd_rev))
    return round(min(100, max(0, float(score))), 2)


# ──────────────────────────────────────────────────────────────────────────────
#  Outlier detection
# ──────────────────────────────────────────────────────────────────────────────

def _detect_outliers(companies: list[dict], metric: str,
                     values: list[Optional[float]],
                     higher_is_better: bool = True) -> dict:
    """Identify best, worst, and at-risk companies for a given metric."""
    pairs = [(c["company_id"], c["company_name"], v)
             for c, v in zip(companies, values) if v is not None]
    if not pairs:
        return {"best": None, "worst": None}

    pairs.sort(key=lambda x: x[2], reverse=higher_is_better)
    best  = {"company_id": pairs[0][0],  "company_name": pairs[0][1],  "value": _r2(pairs[0][2])}
    worst = {"company_id": pairs[-1][0], "company_name": pairs[-1][1], "value": _r2(pairs[-1][2])}

    # Statistical outliers (beyond 1.5 std)
    vals  = [p[2] for p in pairs]
    mean  = _mean(vals)
    std   = _std(vals)
    at_risk = [
        {"company_id": cid, "company_name": name, "value": _r2(v),
         "deviation": _r2((mean - v) / std if std else 0)}
        for cid, name, v in pairs
        if std > 0 and (mean - v) / std > 1.5  # below mean by 1.5σ (bad for higher_is_better)
    ]

    return {"best": best, "worst": worst, "at_risk": at_risk}


# ──────────────────────────────────────────────────────────────────────────────
#  Localized insight generator
# ──────────────────────────────────────────────────────────────────────────────

_INSIGHT_T = {
    "portfolio_healthy": {
        "en": "The portfolio is broadly healthy. Most companies show adequate financial ratios with no critical outliers detected.",
        "ar": "المحفظة بصحة جيدة عموماً. معظم الشركات تُظهر نسباً مالية مناسبة دون شذوذات حرجة.",
        "tr": "Portföy genel olarak sağlıklı. Çoğu şirket kritik aykırı değer olmaksızın yeterli finansal oranlar gösteriyor.",
    },
    "portfolio_mixed": {
        "en": "Performance is mixed across the portfolio. Some companies are performing well while others show financial pressure. Focus management attention on the at-risk companies.",
        "ar": "الأداء متفاوت عبر المحفظة. بعض الشركات تؤدي بشكل جيد بينما أخرى تُظهر ضغطاً مالياً. ركّز اهتمام الإدارة على الشركات المعرضة للخطر.",
        "tr": "Portföy genelinde performans karışık. Bazı şirketler iyi performans gösterirken diğerleri finansal baskı sergiliyor.",
    },
    "portfolio_at_risk": {
        "en": "Multiple companies in the portfolio show financial risk signals. Immediate management review recommended across liquidity and profitability dimensions.",
        "ar": "شركات متعددة في المحفظة تُظهر إشارات خطر مالي. يُوصى بمراجعة إدارية فورية عبر أبعاد السيولة والربحية.",
        "tr": "Portföydeki birden fazla şirket finansal risk sinyalleri gösteriyor. Likidite ve karlılık boyutlarında acil yönetim incelemesi önerilir.",
    },
    "single_company": {
        "en": "Portfolio analysis requires at least 2 companies. Add more companies to enable comparison.",
        "ar": "يتطلب تحليل المحفظة شركتين على الأقل. أضف المزيد من الشركات لتمكين المقارنة.",
        "tr": "Portföy analizi en az 2 şirket gerektirir. Karşılaştırmayı etkinleştirmek için daha fazla şirket ekleyin.",
    },
}


def _portfolio_insight(distribution: dict, n: int, lang: str) -> str:
    loc = lambda key: (_INSIGHT_T.get(key, {}).get(lang)
                       or _INSIGHT_T.get(key, {}).get("en") or "")
    if n < 2:
        return loc("single_company")
    risk_count = distribution.get("risk", 0) + distribution.get("warning", 0)
    good_count = distribution.get("excellent", 0) + distribution.get("good", 0)
    if risk_count == 0:
        return loc("portfolio_healthy")
    if risk_count >= n * 0.5:
        return loc("portfolio_at_risk")
    return loc("portfolio_mixed")


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_portfolio(
    company_data: list[dict],
    lang:         str = "en",
) -> dict:
    """
    Build portfolio-level intelligence from multiple company intelligence outputs.

    Args:
        company_data: list of {
            company_id:   str,
            company_name: str,
            currency:     str,
            intelligence: output of fin_intelligence.build_intelligence(),
        }
        lang: "en" | "ar" | "tr"

    Returns:
        {
          "companies":    [ranked company cards],
          "rankings":     { health, profitability, liquidity, efficiency, growth },
          "outliers":     { health, profitability, liquidity, efficiency },
          "summary":      { n, avg_health, avg_margin, avg_cr, distribution },
          "insight":      str,
          "available":    bool,
          "reason":       str | None,
        }
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"

    n = len(company_data)

    if n == 0:
        return {"available": False, "reason": "No company data provided.", "companies": []}

    # ── Extract per-company metrics ───────────────────────────────────────────
    cards = []
    for entry in company_data:
        intel = entry.get("intelligence") or {}
        cid   = entry.get("company_id",   "")
        cname = entry.get("company_name", cid)

        nm  = _v(intel, "profitability", "net_margin_pct")
        gm  = _v(intel, "profitability", "gross_margin_pct")
        cr  = _v(intel, "liquidity",     "current_ratio")
        qr  = _v(intel, "liquidity",     "quick_ratio")
        dso = _v(intel, "efficiency",    "dso_days")
        ccc = _v(intel, "efficiency",    "ccc_days")
        de  = _v(intel, "leverage",      "debt_to_equity")
        rev_ytd = _get(intel, "trends", "revenue", "ytd_vs_prior")
        rev_dir = _get(intel, "trends", "revenue", "direction")
        health  = intel.get("health_score_v2") or 0

        cards.append({
            "company_id":   cid,
            "company_name": cname,
            "currency":     entry.get("currency", ""),
            "health_score_v2": health,
            "status":       _status_from_health(health),
            "metrics": {
                "net_margin_pct":   _r2(nm),
                "gross_margin_pct": _r2(gm),
                "current_ratio":    _r2(cr),
                "quick_ratio":      _r2(qr),
                "dso_days":         _r2(dso),
                "ccc_days":         _r2(ccc),
                "debt_to_equity":   _r2(de),
                "revenue_ytd_vs_prior": _r2(rev_ytd),
                "revenue_direction":    rev_dir,
            },
            "_dim": {
                "profitability": _profitability_score(intel),
                "liquidity":     _liquidity_score(intel),
                "efficiency":    _efficiency_score(intel),
                "growth":        _growth_score(intel),
            },
        })

    # ── Normalise dimension scores within portfolio ───────────────────────────
    for dim in ("profitability", "liquidity", "efficiency", "growth"):
        raw_vals = [c["_dim"][dim] for c in cards]
        for c in cards:
            c["_dim"][f"{dim}_norm"] = _norm_score(c["_dim"][dim], raw_vals, True)

    # ── Rank tables ───────────────────────────────────────────────────────────
    def _rank_by(key: str, dim: bool = False, reverse: bool = True) -> list[dict]:
        if dim:
            ranked = sorted(cards, key=lambda c: c["_dim"].get(key) or 0, reverse=reverse)
        else:
            ranked = sorted(cards, key=lambda c: c["metrics"].get(key) or 0, reverse=reverse)
        return [
            {
                "rank":         i + 1,
                "company_id":   c["company_id"],
                "company_name": c["company_name"],
                "value":        c["_dim"].get(key) if dim else c["metrics"].get(key),
                "health_score_v2": c["health_score_v2"],
                "status":       c["status"],
            }
            for i, c in enumerate(ranked)
        ]

    rankings = {
        "health":        sorted([{"rank": i+1, "company_id": c["company_id"],
                                   "company_name": c["company_name"],
                                   "value": c["health_score_v2"],
                                   "status": c["status"]}
                                  for i, c in enumerate(
                                      sorted(cards, key=lambda x: x["health_score_v2"], reverse=True)
                                  )], key=lambda x: x["rank"]),
        "profitability": _rank_by("profitability", dim=True),
        "liquidity":     _rank_by("liquidity",     dim=True),
        "efficiency":    _rank_by("efficiency",    dim=True),
        "growth":        _rank_by("growth",        dim=True),
    }

    # Add portfolio rank to each card
    health_rank = {r["company_id"]: r["rank"] for r in rankings["health"]}
    for c in cards:
        c["portfolio_rank"] = health_rank.get(c["company_id"], n)

    # ── Outliers ──────────────────────────────────────────────────────────────
    outliers = {
        "health":        _detect_outliers(cards, "health_score_v2",
                          [c["health_score_v2"] for c in cards], True),
        "net_margin":    _detect_outliers(cards, "net_margin_pct",
                          [c["metrics"]["net_margin_pct"] for c in cards], True),
        "current_ratio": _detect_outliers(cards, "current_ratio",
                          [c["metrics"]["current_ratio"] for c in cards], True),
        "dso_days":      _detect_outliers(cards, "dso_days",
                          [c["metrics"]["dso_days"] for c in cards], False),
    }

    # ── Portfolio summary ─────────────────────────────────────────────────────
    def _avg(metric_key: str) -> Optional[float]:
        vals = [c["metrics"].get(metric_key) for c in cards if c["metrics"].get(metric_key) is not None]
        return _r2(_mean(vals)) if vals else None

    health_vals   = [c["health_score_v2"] for c in cards]
    distribution = {
        "excellent": sum(1 for c in cards if c["status"] == "excellent"),
        "good":      sum(1 for c in cards if c["status"] == "good"),
        "warning":   sum(1 for c in cards if c["status"] == "warning"),
        "risk":      sum(1 for c in cards if c["status"] == "risk"),
    }

    # Named summary companies (for spec compliance)
    sorted_by_health = sorted(cards, key=lambda c: c["health_score_v2"], reverse=True)
    sorted_by_margin = sorted(
        [c for c in cards if c["metrics"].get("net_margin_pct") is not None],
        key=lambda c: c["metrics"]["net_margin_pct"] or 0, reverse=True,
    )

    def _named(c: dict) -> dict:
        return {"company_id": c["company_id"], "company_name": c["company_name"],
                "health_score_v2": c["health_score_v2"], "status": c["status"]}

    summary = {
        # Spec-required fields
        "best_company":            _named(sorted_by_health[0])  if sorted_by_health else None,
        "worst_company":           _named(sorted_by_health[-1]) if sorted_by_health else None,
        "highest_risk_company":    _named(sorted_by_health[-1]) if sorted_by_health else None,
        "strongest_margin_company":_named(sorted_by_margin[0])  if sorted_by_margin else None,
        "portfolio_health_avg":    _r2(_mean(health_vals)),
        "risk_companies":          distribution.get("risk", 0),
        # Extended fields
        "n":                _r2(n),
        "max_health_score": max(health_vals),
        "min_health_score": min(health_vals),
        "avg_net_margin":   _avg("net_margin_pct"),
        "avg_current_ratio":_avg("current_ratio"),
        "avg_dso_days":     _avg("dso_days"),
        "distribution":     distribution,
    }

    insight = _portfolio_insight(distribution, n, lang)

    # Clean _dim internals from output
    clean_cards = []
    for c in cards:
        card = {k: v for k, v in c.items() if k != "_dim"}
        card["dimension_scores"] = {
            k: v for k, v in c["_dim"].items() if not k.endswith("_norm")
        }
        card["dimension_norm_scores"] = {
            k.replace("_norm", ""): v
            for k, v in c["_dim"].items() if k.endswith("_norm")
        }
        clean_cards.append(card)

    # Sort final cards by portfolio rank
    clean_cards.sort(key=lambda c: c["portfolio_rank"])

    # Build flat outliers list for spec
    flat_outliers = []
    for metric, out in outliers.items():
        if out.get("at_risk"):
            for ar in out["at_risk"]:
                flat_outliers.append({
                    "company_id":   ar["company_id"],
                    "company_name": ar["company_name"],
                    "metric":       metric,
                    "value":        ar["value"],
                    "deviation":    ar.get("deviation"),
                    "severity":     "high" if abs(ar.get("deviation") or 0) > 2 else "medium",
                })
        if out.get("worst"):
            w = out["worst"]
            # Only add as outlier if not already in at_risk
            if not any(f["company_id"]==w["company_id"] and f["metric"]==metric
                       for f in flat_outliers):
                flat_outliers.append({
                    "company_id":   w["company_id"],
                    "company_name": w["company_name"],
                    "metric":       metric,
                    "value":        w["value"],
                    "deviation":    None,
                    "severity":     "low",
                })

    return {
        "available": True,
        "reason":    None,
        "companies": clean_cards,
        "ranking":   rankings,    # spec field name
        "rankings":  rankings,    # backward-compat alias
        "outliers":  flat_outliers,
        "outliers_by_metric": outliers,
        "summary":   summary,
        "insight":   insight,
    }
