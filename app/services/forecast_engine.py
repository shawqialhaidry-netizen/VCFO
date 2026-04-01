"""
forecast_engine.py — Phase 27
3-month forward financial forecast with base / risk / optimistic scenarios.

Method:
  - Weighted moving-average MoM growth (most-recent = highest weight)
  - Scenarios modify the base growth rate with ± adjustments
  - Confidence degrades each additional month projected
  - Minimum 3 periods of history required

Inputs:   analysis dict (from run_analysis) + decisions list (optional context)
Output:   { periods, actuals, forecasts, scenarios, summary, confidence, risk_level }

Design:
  - No ML — deterministic, explainable math only
  - Fast: single pass over series
  - Industry-agnostic language throughout
"""
from __future__ import annotations
import math
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────────

MIN_PERIODS   = 3    # minimum history required
FORECAST_N    = 3    # months to project forward

# Scenario adjustments to base MoM growth rate (percentage points)
SCENARIO_DELTA = {
    "base":       {"revenue": 0.0,  "expenses": 0.0,  "net_profit": 0.0},
    "optimistic": {"revenue": +2.0, "expenses": -1.0, "net_profit": +4.0},
    "risk":       {"revenue": -3.0, "expenses": +1.5, "net_profit": -5.0},
}

# Confidence penalty per additional forecast month (percentage points)
CONFIDENCE_DECAY = 10


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _r2(v) -> Optional[float]:
    try:    return round(float(v), 2)
    except: return None


def _clean(series: list) -> list[float]:
    return [float(v) for v in series if v is not None]


def _next_period(p: str) -> str:
    """Advance YYYY-MM by one month."""
    try:
        y, m = int(p[:4]), int(p[5:7])
        m += 1
        if m > 12:
            m, y = 1, y + 1
        return f"{y:04d}-{m:02d}"
    except (ValueError, IndexError):
        return p


def _generate_future_periods(last: str, n: int) -> list[str]:
    periods = []
    cur = last
    for _ in range(n):
        cur = _next_period(cur)
        periods.append(cur)
    return periods


def _weighted_avg_mom(series: list[float], last_n: int = 6) -> float:
    """
    Weighted moving-average of MoM % changes.
    Uses last_n periods with linearly increasing weights (most recent = highest).
    """
    tail = series[-last_n:] if len(series) >= last_n else series
    if len(tail) < 2:
        return 0.0

    mom_vals = []
    for i in range(1, len(tail)):
        if tail[i - 1] and abs(tail[i - 1]) > 0.001:
            mom_vals.append((tail[i] - tail[i - 1]) / abs(tail[i - 1]) * 100)

    if not mom_vals:
        return 0.0

    weights = list(range(1, len(mom_vals) + 1))
    w_sum   = sum(weights)
    return sum(w * m for w, m in zip(weights, mom_vals)) / w_sum


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return abs(values[0]) * 0.3 if values else 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _base_confidence(series: list[float], std_pct: float, n_periods: int) -> int:
    """
    Base confidence (0–100) for a forecast.
    Penalised by: high volatility, few data points.
    """
    base = 80
    if n_periods >= 12: base += 10
    elif n_periods >= 6: base += 5
    elif n_periods <= 3: base -= 15
    if std_pct > 20: base -= 20
    elif std_pct > 10: base -= 10
    return max(30, min(90, base))


def _risk_level(std_rev: float, trend_mom: float, np_trend: float) -> str:
    """Classify overall forecast risk."""
    if std_rev > 20 or trend_mom < -5 or np_trend < -8:
        return "high"
    if std_rev > 10 or trend_mom < -1 or np_trend < -3:
        return "medium"
    return "low"


# ──────────────────────────────────────────────────────────────────────────────
#  Single-series projector
# ──────────────────────────────────────────────────────────────────────────────

def _project_series(
    series:       list[float],
    label:        str,
    scenario_key: str,
    base_conf:    int,
    n:            int = FORECAST_N,
) -> list[dict]:
    """
    Project n months forward for one series using adjusted MoM growth.
    Returns a list of forecast dicts, one per future month.
    """
    delta   = SCENARIO_DELTA.get(scenario_key, {}).get(label, 0.0)
    mom_pct = _weighted_avg_mom(series) + delta

    # Compute bands: ± std-dev of last 6 MoM values
    tail = series[-7:] if len(series) >= 7 else series
    mom_hist = []
    for i in range(1, len(tail)):
        if abs(tail[i - 1]) > 0.001:
            mom_hist.append((tail[i] - tail[i - 1]) / abs(tail[i - 1]) * 100)

    std = _stddev(mom_hist) if mom_hist else abs(mom_pct) * 0.3

    result = []
    current = series[-1]
    for step in range(1, n + 1):
        current = current * (1 + mom_pct / 100)
        band    = current * (std / 100) * step   # band widens each month
        conf    = max(20, base_conf - (step - 1) * CONFIDENCE_DECAY)
        result.append({
            "step":       step,
            "point":      _r2(current),
            "low":        _r2(min(current - band, current + band)),
            "high":       _r2(max(current - band, current + band)),
            "mom_applied": _r2(mom_pct),
            "confidence": conf,
        })
    return result


# ──────────────────────────────────────────────────────────────────────────────
#  Summary insight builder
# ──────────────────────────────────────────────────────────────────────────────

def _insight(rev_mom: float, np_mom: float, risk: str, lang: str) -> str:
    _T = {
        "up_up": {
            "en": "Revenue and profit both trending upward. The base forecast projects continued growth over the next 3 months, supported by current momentum.",
            "ar": "الإيرادات والأرباح في اتجاه تصاعدي. يتوقع السيناريو الأساسي استمرار النمو خلال الأشهر الثلاثة القادمة.",
            "tr": "Gelir ve kâr her ikisi de yukarı yönlü. Baz senaryo önümüzdeki 3 ayda büyümenin devam edeceğini öngörüyor.",
        },
        "up_down": {
            "en": "Revenue growing but margin compression means profits are not keeping pace. Cost control is the near-term priority.",
            "ar": "الإيرادات في نمو لكن ضغط الهوامش يعني أن الأرباح لا تواكب. السيطرة على التكاليف هي الأولوية القريبة.",
            "tr": "Gelir büyüyor ancak marj baskısı kârın adım tutamadığı anlamına geliyor. Maliyet kontrolü kısa vadeli önceliktir.",
        },
        "down_up": {
            "en": "Revenue is under pressure, but profitability is holding. Watch for potential revenue recovery needed to sustain current margins long-term.",
            "ar": "الإيرادات تحت ضغط لكن الربحية صامدة. تابع التعافي المحتمل في الإيرادات اللازم للحفاظ على الهوامش الحالية.",
            "tr": "Gelir baskı altında ancak karlılık tutuyor. Uzun vadede mevcut marjları sürdürmek için gelir toparlanmasını izleyin.",
        },
        "down_down": {
            "en": "Both revenue and profit are declining. The risk scenario suggests further deterioration without corrective action. Immediate management attention required.",
            "ar": "كل من الإيرادات والأرباح في تراجع. يشير سيناريو المخاطر إلى مزيد من التدهور بدون إجراء تصحيحي. مطلوب اهتمام فوري من الإدارة.",
            "tr": "Hem gelir hem de kâr düşüyor. Risk senaryosu, düzeltici eylem olmadan daha fazla bozulma olduğunu öne sürüyor.",
        },
        "stable": {
            "en": "Financial performance is broadly stable. The base forecast shows marginal changes with limited upside or downside risk.",
            "ar": "الأداء المالي مستقر بشكل عام. يُظهر السيناريو الأساسي تغييرات هامشية مع محدودية المخاطر الصعودية أو الهبوطية.",
            "tr": "Finansal performans genel olarak stabil. Baz senaryo, sınırlı yukarı veya aşağı riskle marjinal değişiklikler gösteriyor.",
        },
        "high_risk": {
            "en": "High forecast volatility detected. Historical data shows significant swings in revenue, making projections less reliable. Treat all scenarios as indicative only.",
            "ar": "رُصدت تقلبية عالية في التوقعات. البيانات التاريخية تُظهر تذبذبات كبيرة في الإيرادات، مما يجعل التوقعات أقل موثوقية.",
            "tr": "Yüksek tahmin oynaklığı tespit edildi. Geçmiş veriler gelirde önemli dalgalanmalar gösteriyor, bu da projeksiyonları daha az güvenilir kılıyor.",
        },
    }

    if lang not in ("en", "ar", "tr"):
        lang = "en"

    if risk == "high":
        key = "high_risk"
    elif abs(rev_mom) < 1.5 and abs(np_mom) < 2:
        key = "stable"
    elif rev_mom >= 0 and np_mom >= 0:
        key = "up_up"
    elif rev_mom >= 0 and np_mom < 0:
        key = "up_down"
    elif rev_mom < 0 and np_mom >= 0:
        key = "down_up"
    else:
        key = "down_down"

    return _T.get(key, {}).get(lang) or _T.get(key, {}).get("en") or ""


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_forecast(
    analysis:   dict,
    lang:       str = "en",
    n_months:   int = FORECAST_N,
) -> dict:
    """
    Build a 3-month financial forecast with base / optimistic / risk scenarios.

    Args:
        analysis:  output of run_analysis()
        lang:      "en" | "ar" | "tr"
        n_months:  number of months to project (default 3)

    Returns:
        {
          "available":        bool,
          "reason":           str | None,   -- set if not available
          "periods":          [YYYY-MM],    -- historical periods
          "future_periods":   [YYYY-MM],    -- forecast periods
          "actuals": {
              "revenue":     [float],
              "net_profit":  [float],
              "expenses":    [float],
          },
          "scenarios": {
              "base":       { revenue: [...], net_profit: [...], expenses: [...] },
              "optimistic": { ... },
              "risk":       { ... },
          },
          "summary": {
              "trend_mom_revenue":    float,  -- base weighted MoM %
              "trend_mom_net_profit": float,
              "risk_level":           str,
              "insight":              str,
              "base_confidence":      int,
          },
          "method": "weighted_moving_average",
        }
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"

    trends  = analysis.get("trends") or {}
    periods = trends.get("periods")  or analysis.get("periods") or []

    rev_series  = _clean(trends.get("revenue_series",        []))
    np_series   = _clean(trends.get("net_profit_series",     []))
    exp_series  = _clean(trends.get("expenses_series",       []))
    cogs_series = _clean(trends.get("cogs_series",           []))
    op_series   = _clean(trends.get("operating_profit_series") or [])

    # Fallback: if expenses_series missing, derive from revenue - gross_profit
    if not exp_series and rev_series and len(rev_series) == len(np_series):
        gm_series = _clean(trends.get("gross_margin_series", []) or [])
        if gm_series and len(gm_series) == len(rev_series):
            exp_series = [r * (1 - gm / 100)
                          for r, gm in zip(rev_series, gm_series)]

    # Minimum data check
    n_hist = min(len(rev_series), len(np_series))
    if n_hist < MIN_PERIODS:
        return {
            "available": False,
            "reason":    f"Minimum {MIN_PERIODS} historical periods required (found {n_hist}).",
        }

    # Align all series to same length
    n = min(len(rev_series), len(np_series), len(exp_series) or len(np_series))
    rev_s  = rev_series[-n:]
    np_s   = np_series[-n:]
    exp_s  = (exp_series[-n:] if exp_series else
              [r - p for r, p in zip(rev_s, np_s)])  # approx if missing

    # Generate future period labels
    last_period  = periods[-1] if periods else "2026-01"
    future_labels = _generate_future_periods(last_period, n_months)

    # Base weighted MoM rates
    rev_mom  = _weighted_avg_mom(rev_s)
    np_mom   = _weighted_avg_mom(np_s)
    exp_mom  = _weighted_avg_mom(exp_s)

    # Volatility (std of MoM changes)
    def _mom_changes(s):
        return [(s[i]-s[i-1])/abs(s[i-1])*100 for i in range(1,len(s)) if abs(s[i-1])>0.001]

    std_rev = _stddev(_mom_changes(rev_s)) if len(rev_s) > 2 else 0.0
    std_np  = _stddev(_mom_changes(np_s))  if len(np_s)  > 2 else 0.0

    base_conf   = _base_confidence(rev_s, std_rev, n)
    risk_lvl    = _risk_level(std_rev, rev_mom, np_mom)
    insight_txt = _insight(rev_mom, np_mom, risk_lvl, lang)

    # Build scenarios
    def _build_scenario(key: str) -> dict:
        return {
            "revenue":    _project_series(rev_s,  "revenue",    key, base_conf, n_months),
            "net_profit": _project_series(np_s,   "net_profit", key, base_conf, n_months),
            "expenses":   _project_series(exp_s,  "expenses",   key, base_conf, n_months),
        }

    scenarios = {k: _build_scenario(k) for k in ("base", "optimistic", "risk")}

    return {
        "available":      True,
        "reason":         None,
        "periods":        list(periods[-n:]),
        "future_periods": future_labels,
        "actuals": {
            "revenue":    [_r2(v) for v in rev_s],
            "net_profit": [_r2(v) for v in np_s],
            "expenses":   [_r2(v) for v in exp_s],
        },
        "scenarios":   scenarios,
        "summary": {
            "trend_mom_revenue":    _r2(rev_mom),
            "trend_mom_net_profit": _r2(np_mom),
            "risk_level":           risk_lvl,
            "insight":              insight_txt,
            "base_confidence":      base_conf,
            "std_revenue_pct":      _r2(std_rev),
            "n_historical":         n,
        },
        "method":  "weighted_moving_average",
        "version": "phase27",
    }
