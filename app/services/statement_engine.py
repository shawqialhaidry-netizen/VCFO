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
from app.services.structured_income_statement import build_structured_income_statement_bundle
from app.services.structured_income_statement_variance import (
    build_structured_income_statement_variance_bundle_from_window,
)
from app.services.structured_profit_bridge import (
    build_structured_profit_bridge_bundle_from_window,
)
from app.services.structured_profit_story import build_structured_profit_story_from_window
from app.services.statement_hierarchy import build_statement_hierarchy


# Keys duplicated at executive root via extract_structured_financial_overlay — omit from nested `statements` to avoid payload drift.
STRUCTURED_FINANCIAL_KEYS = frozenset({
    "structured_income_statement",
    "structured_income_statement_meta",
    "structured_income_statement_variance",
    "structured_income_statement_margin_variance",
    "structured_income_statement_variance_meta",
    "structured_profit_bridge",
    "structured_profit_bridge_interpretation",
    "structured_profit_bridge_meta",
    "structured_profit_story",
    "statement_hierarchy",
})


def extract_structured_financial_overlay(bundle: dict) -> dict:
    """Lift canonical structured blocks from build_statement_bundle (single construction site)."""
    if not isinstance(bundle, dict):
        return {}
    return {k: bundle[k] for k in STRUCTURED_FINANCIAL_KEYS if k in bundle}


def strip_structured_keys_for_nested_statements(bundle: dict) -> dict:
    """Remove structured keys from the nested `data.statements` object only."""
    if not isinstance(bundle, dict):
        return bundle
    return {k: v for k, v in bundle.items() if k not in STRUCTURED_FINANCIAL_KEYS}


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

def _integrity_status(proven: bool = False, partial: bool = False, available: bool = True) -> str:
    if not available:
        return "unavailable"
    if proven:
        return "proven"
    if partial:
        return "partial"
    return "unavailable"


def _extract_balance_sheet_cash(balance_sheet: dict) -> Optional[float]:
    asset_items = _get(balance_sheet, "assets", "items") or []
    total = 0.0
    found = False
    for item in asset_items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("account_code", "")).strip()
        try:
            num = int(code[:4]) if len(code) >= 4 else int(code)
        except (TypeError, ValueError):
            num = -1
        if 1000 <= num <= 1099:
            total += abs(float(item.get("amount", 0) or 0))
            found = True
    return _r2(total) if found else None


def _values_match(a, b, tolerance: float = 0.01) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tolerance
    except (TypeError, ValueError):
        return False


def _build_cross_statement_integrity(latest: dict, cashflow_raw: dict) -> dict:
    is_ = latest.get("income_statement") or {}
    bs_ = latest.get("balance_sheet") or {}
    bs_cash = _extract_balance_sheet_cash(bs_)

    is_net_profit = _r2(_get(is_, "net_profit"))
    cf_net_profit = _r2(_get(cashflow_raw, "debug", "net_profit"))
    net_income_to_cashflow_proven = _values_match(is_net_profit, cf_net_profit)
    net_income_to_cashflow_available = is_net_profit is not None and cf_net_profit is not None

    synthetic_equity_support = bool(_get(bs_, "equity", "synthetic_equity_support"))
    retained_earnings_continuity_proven = bool(_get(bs_, "equity", "retained_earnings_continuity_proven"))
    equity_rollforward_available = bool(_get(bs_, "equity", "equity_rollforward_available"))
    equity_warning = _get(bs_, "equity", "equity_integrity_warning")

    net_income_to_equity_status = _integrity_status(
        proven=retained_earnings_continuity_proven,
        partial=synthetic_equity_support or bool(equity_warning),
        available=(
            retained_earnings_continuity_proven
            or synthetic_equity_support
            or equity_rollforward_available
            or bool(equity_warning)
        ),
    )

    ending_cash = _r2(cashflow_raw.get("ending_cash", cashflow_raw.get("cash_balance")))
    opening_cash = _r2(cashflow_raw.get("opening_cash"))
    ending_cash_to_bs_proven = _values_match(ending_cash, bs_cash)
    ending_cash_to_bs_available = ending_cash is not None and bs_cash is not None

    cf_reconciles = cashflow_raw.get("reconciles")
    opening_to_ending_status = _integrity_status(
        proven=cf_reconciles is True,
        partial=cf_reconciles is False,
        available=(opening_cash is not None and ending_cash is not None and cf_reconciles is not None),
    )

    equity_status = _integrity_status(
        proven=(retained_earnings_continuity_proven and equity_rollforward_available),
        partial=(synthetic_equity_support or bool(equity_warning)),
        available=(
            retained_earnings_continuity_proven
            or equity_rollforward_available
            or synthetic_equity_support
            or bool(equity_warning)
        ),
    )

    statuses = [
        _integrity_status(
            proven=net_income_to_cashflow_proven,
            partial=(not net_income_to_cashflow_proven and net_income_to_cashflow_available),
            available=net_income_to_cashflow_available,
        ),
        net_income_to_equity_status,
        _integrity_status(
            proven=ending_cash_to_bs_proven,
            partial=(not ending_cash_to_bs_proven and ending_cash_to_bs_available),
            available=ending_cash_to_bs_available,
        ),
        opening_to_ending_status,
        equity_status,
    ]
    if any(s == "partial" for s in statuses):
        overall = "partial"
    elif statuses and all(s == "proven" for s in statuses):
        overall = "proven"
    else:
        overall = "unavailable"

    return {
        "status": overall,
        "net_income": {
            "income_statement_to_cashflow_start": {
                "status": _integrity_status(
                    proven=net_income_to_cashflow_proven,
                    partial=(not net_income_to_cashflow_proven and net_income_to_cashflow_available),
                    available=net_income_to_cashflow_available,
                ),
                "income_statement_net_profit": is_net_profit,
                "cashflow_starting_profit": cf_net_profit,
            },
            "income_statement_to_equity_handling": {
                "status": net_income_to_equity_status,
                "synthetic_equity_support": synthetic_equity_support,
                "synthetic_equity_support_reason": _get(bs_, "equity", "synthetic_equity_support_reason"),
                "retained_earnings_continuity_proven": retained_earnings_continuity_proven,
                "equity_rollforward_available": equity_rollforward_available,
                "warning": equity_warning,
            },
        },
        "cash": {
            "ending_cash_to_balance_sheet_cash": {
                "status": _integrity_status(
                    proven=ending_cash_to_bs_proven,
                    partial=(not ending_cash_to_bs_proven and ending_cash_to_bs_available),
                    available=ending_cash_to_bs_available,
                ),
                "cashflow_ending_cash": ending_cash,
                "balance_sheet_cash": bs_cash,
            },
            "opening_to_ending_continuity": {
                "status": opening_to_ending_status,
                "opening_cash": opening_cash,
                "ending_cash": ending_cash,
                "reconciles": cf_reconciles,
                "working_capital_basis": _get(cashflow_raw, "statement_meta", "working_capital_basis"),
                "operating_cashflow_basis": _get(cashflow_raw, "statement_meta", "operating_cashflow_basis"),
            },
        },
        "equity": {
            "status": equity_status,
            "synthetic_equity_support": synthetic_equity_support,
            "retained_earnings_continuity_proven": retained_earnings_continuity_proven,
            "equity_rollforward_available": equity_rollforward_available,
            "warning": equity_warning,
        },
    }


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
        return {
            "available": False,
            "reason": "No period data",
            **build_structured_income_statement_variance_bundle_from_window([]),
            **build_structured_profit_bridge_bundle_from_window([]),
            "structured_profit_story": build_structured_profit_story_from_window([]),
            "statement_hierarchy": {"schema_version": 1, "available": False},
        }

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

    # current_ratio — Phase 2: statement-derived only (no intelligence ratio fallback / drift)
    cr  = _r2(ca / cl) if (ca is not None and cl is not None and float(cl) != 0) else None
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

    _sis = build_structured_income_statement_bundle(latest)
    _var = build_structured_income_statement_variance_bundle_from_window(windowed)
    _bridge = build_structured_profit_bridge_bundle_from_window(windowed)
    _ratio_prof = (intelligence.get("ratios") or {}).get("profitability") or {}
    _profit_story = build_structured_profit_story_from_window(
        windowed, latest_profitability=_ratio_prof
    )

    _stmt_hierarchy = build_statement_hierarchy(
        latest.get("income_statement") or {},
        latest.get("balance_sheet") or {},
        cashflow_raw,
        period=period,
    )
    _cross_statement_integrity = _build_cross_statement_integrity(latest, cashflow_raw)

    return {
        "available":       True,
        "period":          period,
        "income_statement": income_statement,
        "balance_sheet":   balance_sheet,
        "cashflow":        cashflow_stmt,
        "cross_statement_integrity": _cross_statement_integrity,
        "series":          series,
        "summary":         summary,
        "insights":        insights,
        "structured_income_statement": _sis["structured_income_statement"],
        "structured_income_statement_meta": _sis["structured_income_statement_meta"],
        **_var,
        **_bridge,
        "structured_profit_story": _profit_story,
        "statement_hierarchy": _stmt_hierarchy,
    }
