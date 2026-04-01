"""
statement_engine.py — Phase 32.9
Aggregates existing financial statement, cashflow, and intelligence outputs
into a single unified bundle for the executive endpoint and Statements screen.

Does NOT recalculate — consumes outputs from:
  - financial_statements.build_statements() / statements_to_dict()
  - cashflow_engine.build_cashflow()
  - fin_intelligence.build_intelligence()

Adds:
  - statement-level insights linked to decisions + root causes
  - series data for charts (from windowed period list)
  - clean summary numbers for the Statements screen header cards
  - quality flags and linking logic
"""
from __future__ import annotations
from typing import Optional
from app.i18n import translate as _i18n_translate


# ── Helpers ───────────────────────────────────────────────────────────────────

def _r2(v) -> Optional[float]:
    try:    return round(float(v), 2)
    except: return None


def _get(d: dict, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict): return default
        d = d.get(k, default)
    return d


def _fmt_currency(v: float) -> str:
    if v is None: return "—"
    a = abs(v); s = "+" if v >= 0 else "-"
    if a >= 1_000_000: return f"{s}{a/1_000_000:.1f}M"
    if a >= 1_000:     return f"{s}{a/1_000:.0f}K"
    return f"{s}{a:.0f}"


# ── Localized insight text — loaded from i18n JSON files (no hardcoded strings) ──

def _t(key: str, lang: str, **kw) -> str:
    """
    Translate a statement insight key using the central i18n system.
    Keys are prefixed with 'stmt_insight_' in the JSON files.
    Falls back to the key itself if not found.
    """
    i18n_key = f"stmt_insight_{key}"
    tpl = _i18n_translate(i18n_key, lang)
    if not tpl or tpl == i18n_key:
        # Last-resort fallback: try English
        tpl = _i18n_translate(i18n_key, "en")
    if not tpl or tpl == i18n_key:
        return key  # return raw key rather than empty string
    try:
        return tpl.format(**kw)
    except Exception:
        return tpl


# ── Build statement series from windowed period list ──────────────────────────

def _build_series(windowed: list[dict]) -> dict:
    """Extract 6-month series for charts from the period list."""
    tail = windowed[-6:] if len(windowed) >= 6 else windowed
    periods, rev_s, np_s, gm_s, ocf_s = [], [], [], [], []
    for s in tail:
        periods.append(s.get("period",""))
        is_ = s.get("income_statement") or {}
        rev_s.append(_r2(_get(is_, "revenue","total")))
        np_s.append(_r2(_get(is_, "net_profit")))
        gm_s.append(_r2(_get(is_, "gross_margin_pct")))
    return {
        "periods":            periods,
        "revenue":            rev_s,
        "net_profit":         np_s,
        "gross_margin_pct":   gm_s,
    }


def _mom_change(series: list, idx: int = -1) -> Optional[float]:
    try:
        cur  = series[idx]
        prev = series[idx - 1]
        if prev and abs(prev) > 0.001:
            return _r2((cur - prev) / abs(prev) * 100)
    except (IndexError, TypeError): pass
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def build_statement_bundle(
    windowed:     list[dict],
    cashflow_raw: dict,
    intelligence: dict,
    lang:         str = "en",
) -> dict:
    """
    Build a unified statement bundle for the executive endpoint.

    Args:
        windowed:     list of period statement dicts (from _build_period_statements)
        cashflow_raw: output of build_cashflow()
        intelligence: output of build_intelligence()
        lang:         "en" | "ar" | "tr"

    Returns:
        {
            "income_statement": {...},
            "balance_sheet":    {...},
            "cashflow":         {...},
            "series":           {...},
            "summary":          {...},   ← header cards
            "insights":         [...],   ← linked to decisions
        }
    """
    if lang not in ("en", "ar", "tr"):
        lang = "en"

    if not windowed:
        return {"available": False, "reason": "No period data"}

    latest = windowed[-1]
    prev   = windowed[-2] if len(windowed) >= 2 else None

    is_   = latest.get("income_statement") or {}
    bs_   = latest.get("balance_sheet")    or {}
    period = latest.get("period", "")

    ratios = intelligence.get("ratios", {})
    prof   = ratios.get("profitability", {})
    liq_r  = ratios.get("liquidity",    {})

    # ── Series ────────────────────────────────────────────────────────────────
    series = _build_series(windowed)

    # ── Income Statement ──────────────────────────────────────────────────────
    rev       = _get(is_, "revenue",  "total")
    cogs      = _get(is_, "cogs",     "total")
    gp        = _get(is_, "gross_profit")
    gm_pct    = _get(is_, "gross_margin_pct")
    opex      = _get(is_, "expenses", "total")
    op_profit = _get(is_, "operating_profit")
    tax       = _get(is_, "tax",      "total")
    np_       = _get(is_, "net_profit")
    nm_pct    = _get(is_, "net_margin_pct")

    rev_mom = _mom_change(series["revenue"])
    np_mom  = _mom_change(series["net_profit"])

    # YoY if available (compare to period - 12 months)
    rev_yoy = None
    if len(windowed) >= 13:
        old     = windowed[-13].get("income_statement", {})
        old_rev = _get(old, "revenue", "total")
        if old_rev and abs(old_rev) > 0.001 and rev:
            rev_yoy = _r2((rev - old_rev) / abs(old_rev) * 100)

    income_statement = {
        "period":           period,
        "revenue":          _r2(rev),
        "cogs":             _r2(cogs),
        "gross_profit":     _r2(gp),
        "gross_margin_pct": _r2(gm_pct),
        "operating_expenses": _r2(opex),
        "operating_profit": _r2(op_profit),
        "tax":              _r2(tax),
        "net_profit":       _r2(np_),
        "net_margin_pct":   _r2(nm_pct),
        "mom_change_rev":   rev_mom,
        "mom_change_np":    np_mom,
        "yoy_change_rev":   rev_yoy,
        "items": {
            "revenue":  _get(is_, "revenue",  "items") or [],
            "cogs":     _get(is_, "cogs",     "items") or [],
            "expenses": _get(is_, "expenses", "items") or [],
            "tax":      _get(is_, "tax",      "items") or [],
        },
    }

    # ── Balance Sheet ─────────────────────────────────────────────────────────
    total_assets = _get(bs_, "assets",      "total")
    total_liab   = _get(bs_, "liabilities", "total")
    total_eq     = _get(bs_, "equity",      "total")
    is_balanced  = _get(bs_, "is_balanced",  False)

    # Working capital — READ DIRECTLY from statement_engine output (financial_statements.py)
    # NEVER read from intelligence ratios — that would create a circular dependency
    # financial_statements.py sets bs["working_capital"] = current_assets - current_liabilities
    wc  = bs_.get("working_capital")  # single source of truth
    ca  = bs_.get("current_assets")
    cl  = bs_.get("current_liabilities")

    # current_ratio derived here from the authoritative ca/cl values
    cr  = _r2(ca / cl) if (ca and cl and cl != 0) else _get(liq_r, "current_ratio", "value")
    dr  = None
    if total_assets and total_assets > 0 and total_liab:
        dr = _r2(total_liab / total_assets * 100)

    balance_sheet = {
        "period":               period,
        "total_assets":         _r2(total_assets),
        "total_liabilities":    _r2(total_liab),
        "total_equity":         _r2(total_eq),
        "current_assets":       _r2(ca),
        "current_liabilities":  _r2(cl),
        "noncurrent_assets":    _r2(bs_.get("noncurrent_assets")),
        "noncurrent_liabilities": _r2(bs_.get("noncurrent_liabilities")),
        "working_capital":      _r2(wc),   # ← single source of truth
        "is_balanced":          is_balanced,
        "ratios": {
            "current_ratio":  _r2(cr),
            "debt_ratio_pct": dr,
        },
        "items": {
            "assets":      _get(bs_, "assets",      "items") or [],
            "liabilities": _get(bs_, "liabilities", "items") or [],
            "equity":      _get(bs_, "equity",      "items") or [],
        },
    }

    # ── Cash Flow ─────────────────────────────────────────────────────────────
    ocf     = cashflow_raw.get("operating_cashflow")
    ocf_mom = cashflow_raw.get("operating_cashflow_mom")
    # cashflow_engine returns quality as a dict: {cash_conversion_quality, ...}
    _quality_raw = cashflow_raw.get("quality", {})
    if isinstance(_quality_raw, dict):
        quality = _quality_raw.get("cash_conversion_quality", "unknown")
    else:
        quality = str(_quality_raw)  # legacy string format
    cf_series_raw = _get(cashflow_raw, "series", "operating_cashflow") or []
    wc_change = cashflow_raw.get("working_capital_change", {})

    # Quality flag — map cashflow_engine quality to UI flag
    if quality in ("strong",):
        cf_flag = "good"
    elif quality in ("moderate",):
        cf_flag = "warning"
    elif quality in ("weak", "indeterminate") or (ocf is not None and ocf < 0):
        cf_flag = "risk"
    else:
        cf_flag = "neutral"

    cashflow_stmt = {
        "period":              period,
        "operating_cashflow":  _r2(ocf),
        "operating_cashflow_mom": _r2(ocf_mom),
        "free_cashflow":       cashflow_raw.get("free_cashflow"),
        "cash_balance":        cashflow_raw.get("cash_balance"),
        "reliability":         cf_flag,
        "wc_change":           wc_change,
        "trend":               cf_series_raw[-6:] if cf_series_raw else [],
        "da_estimate":         cashflow_raw.get("da_estimate"),
        "flags":               cashflow_raw.get("flags", {}),
    }

    # ── Summary cards ─────────────────────────────────────────────────────────
    # Flow metrics (revenue, expenses, net_profit) = SUM across all windowed periods.
    # Rate metrics (net_margin_pct) = latest period snapshot.
    # This matches kpi_block semantics: enrich_kpi() SUMs flow, uses LAST for rates.
    def _sum_field(stmts, *path):
        total = 0.0
        for s in stmts:
            cur = s
            for k in path:
                cur = cur.get(k) if isinstance(cur, dict) else None
            total += float(cur or 0)
        return _r2(total) if total != 0 else None

    w_rev_sum = _sum_field(windowed, "income_statement", "revenue", "total")
    w_np_sum  = _sum_field(windowed, "income_statement", "net_profit")
    # net_margin from latest (ratio, not sum)
    w_nm      = _r2(nm_pct)
    # OCF is already aggregated by cashflow engine across the window
    summary = {
        "metric_basis": "window_totals_plus_latest_rates",
        "window_revenue_total":   w_rev_sum if w_rev_sum is not None else _r2(rev),
        "window_net_profit_total": w_np_sum if w_np_sum is not None else _r2(np_),
        "latest_revenue":         _r2(rev),
        "latest_net_profit":      _r2(np_),
        "latest_net_margin_pct":  _r2(nm_pct),
        "latest_gross_margin_pct": _r2(gm_pct),
        "revenue":        w_rev_sum if w_rev_sum is not None else _r2(rev),
        "net_profit":     w_np_sum  if w_np_sum  is not None else _r2(np_),
        "net_margin_pct": w_nm,
        "operating_cashflow": _r2(ocf),
        "working_capital": _r2(wc),
        "period":         period,
        "mom_rev":        rev_mom,
        "mom_np":         np_mom,
        "mom_ocf":        _r2(ocf_mom),
    }

    # ── Insights (linked to decisions) ────────────────────────────────────────
    insights = []

    # Low net margin → profitability decision
    if nm_pct is not None and nm_pct < 10:
        insights.append({
            "domain":           "profitability",
            "key":              "low_net_margin",
            "message":          _t("low_net_margin", lang, val=f"{nm_pct:.1f}"),
            "severity":         "high" if nm_pct < 5 else "medium",
            "linked_decision":  "profitability",
            "metric":           "net_margin_pct",
            "value":            _r2(nm_pct),
        })

    # Negative working capital → liquidity issue
    if wc is not None and wc < 0:
        insights.append({
            "domain":           "liquidity",
            "key":              "negative_working_capital",
            "message":          _t("negative_working_capital", lang, val=_fmt_currency(wc)),
            "severity":         "high",
            "linked_decision":  "liquidity",
            "metric":           "working_capital",
            "value":            _r2(wc),
        })

    # Cash flow below net profit → collections lag
    if ocf is not None and np_ is not None and np_ > 0 and ocf < np_ * 0.7:
        insights.append({
            "domain":           "efficiency",
            "key":              "cashflow_below_profit",
            "message":          _t("cashflow_below_profit", lang,
                                   cf=_fmt_currency(ocf), np=_fmt_currency(np_)),
            "severity":         "medium",
            "linked_decision":  "efficiency",
            "metric":           "operating_cashflow",
            "value":            _r2(ocf),
        })

    # Low current ratio → liquidity alert
    if cr is not None and cr < 1.2:
        insights.append({
            "domain":           "liquidity",
            "key":              "low_current_ratio",
            "message":          _t("low_current_ratio", lang, val=f"{cr:.2f}"),
            "severity":         "high" if cr < 1.0 else "medium",
            "linked_decision":  "liquidity",
            "metric":           "current_ratio",
            "value":            _r2(cr),
        })

    # Positive cashflow — opportunity
    if ocf is not None and ocf > 0:
        insights.append({
            "domain":           "growth",
            "key":              "cashflow_positive",
            "message":          _t("cashflow_positive", lang),
            "severity":         "info",
            "linked_decision":  "growth",
            "metric":           "operating_cashflow",
            "value":            _r2(ocf),
        })

    # Strong gross margin — opportunity
    if gm_pct is not None and gm_pct >= 38:
        insights.append({
            "domain":           "profitability",
            "key":              "strong_gross_margin",
            "message":          _t("strong_gross_margin", lang, val=f"{gm_pct:.1f}"),
            "severity":         "info",
            "linked_decision":  "growth",
            "metric":           "gross_margin_pct",
            "value":            _r2(gm_pct),
        })

    # Sort: high first
    sev_rank = {"high": 0, "medium": 1, "info": 2}
    insights.sort(key=lambda x: sev_rank.get(x["severity"], 3))

    return {
        "available":       True,
        "period":          period,
        "income_statement": income_statement,
        "balance_sheet":   balance_sheet,
        "cashflow":        cashflow_stmt,
        "series":          series,
        "summary":         summary,
        "insights":        insights,
    }
