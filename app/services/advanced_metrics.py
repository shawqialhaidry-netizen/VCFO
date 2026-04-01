"""
advanced_metrics.py — Phase 8 Advanced Analytics
ADD-ONLY layer — does NOT modify financial_engine, analysis_engine, or any existing service.

Computes CFO-grade metrics from the output of run_analysis() + period statements.

Output shape (appended to analysis response as "advanced_metrics"):
{
  "profitability": { ebitda, ebitda_margin, contribution_margin,
                     operating_leverage, incremental_margin },
  "liquidity":     { cash_ratio, wc_trend, wc_series, cash_burn },
  "efficiency":    { inv_turnover, rec_turnover, pay_turnover,
                     asset_turnover, revenue_per_asset },
  "risk":          { margin_volatility, revenue_volatility, revenue_stability_score,
                     cogs_to_opex_ratio, cost_structure,
                     earnings_consistency_score, risk_rating }
}

All functions are pure — zero DB, zero HTTP, zero side effects.
Safe division throughout — never raises ZeroDivisionError.
Returns None (not 0) when data is insufficient.
"""
from __future__ import annotations

import math
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers — self-contained, do not import from other services
# ══════════════════════════════════════════════════════════════════════════════

def _sd(values: list[float]) -> Optional[float]:
    """Population std dev. Returns None if < 2 values."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    return round(math.sqrt(sum((x - mean) ** 2 for x in vals) / len(vals)), 4)


def _mean(values: list) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def _r2(v) -> Optional[float]:
    return round(float(v), 2) if v is not None else None


def _r4(v) -> Optional[float]:
    return round(float(v), 4) if v is not None else None


def _div(a, b) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return round(a / b, 4)


def _pct(a, b) -> Optional[float]:
    v = _div(a, b)
    return round(v * 100, 2) if v is not None else None


def _slope(series: list[float], window: int = 6) -> Optional[float]:
    """OLS slope of last `window` non-None values. Positive = upward."""
    vals = [v for v in series if v is not None][-window:]
    n = len(vals)
    if n < 2:
        return None
    x_mean = (n - 1) / 2
    y_mean = sum(vals) / n
    num = sum((i - x_mean) * (vals[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return round(num / den, 4) if den else 0.0


def _get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
        if cur is None:
            return default
    return cur


# ══════════════════════════════════════════════════════════════════════════════
#  1. Advanced Profitability
# ══════════════════════════════════════════════════════════════════════════════

def compute_advanced_profitability(
    period_statements: list[dict],
    ratios_by_period: dict[str, dict],
) -> dict:
    """
    Enhanced profitability metrics beyond basic margins.

    EBITDA Approximation:
      EBITDA ≈ Operating Profit + Depreciation & Amortization
      Since D&A is embedded in OpEx (no dedicated line), we use a heuristic:
        D&A ≈ 8–12% of non-current assets (industry average for asset-heavy ops)
      We expose this as ebitda_approx with a clear note.
      If depreciation account is present in 'expenses' with keyword match, we use it.

    Operating Leverage:
      DOL = % change in Operating Profit / % change in Revenue
      Measures sensitivity: high DOL → profits amplify revenue movements.

    Incremental Margin:
      (ΔNet Profit / ΔRevenue) over last 2 periods.
      Answers: "For every extra 1 SAR of revenue, how much flows to profit?"
    """
    if not period_statements:
        return {}

    IS = "income_statement"

    # Extract series
    rev_series  = [float(_get(s, IS, "revenue",   "total") or 0) for s in period_statements]
    cogs_series = [float(_get(s, IS, "cogs",      "total") or 0) for s in period_statements]
    opex_series = [float(_get(s, IS, "expenses",  "total") or 0) for s in period_statements]
    op_series   = [float(_get(s, IS, "operating_profit")   or 0) for s in period_statements]
    np_series   = [float(_get(s, IS, "net_profit")         or 0) for s in period_statements]
    gm_series   = [float(_get(s, IS, "gross_margin_pct")   or 0) for s in period_statements]
    tax_series  = [float(_get(s, IS, "tax", "total")       or 0) for s in period_statements]

    latest = period_statements[-1]
    is_    = _get(latest, IS) or {}
    bs     = _get(latest, "balance_sheet") or {}

    rev    = float(_get(is_, "revenue",   "total") or 0)
    cogs   = float(_get(is_, "cogs",      "total") or 0)
    opex   = float(_get(is_, "expenses",  "total") or 0)
    op     = float(_get(is_, "operating_profit")   or 0)
    np_    = float(_get(is_, "net_profit")         or 0)
    gp     = float(_get(is_, "gross_profit")       or 0)

    # ── EBITDA Approximation ──────────────────────────────────────────────────
    # Use noncurrent assets proxy for D&A — conservative 10% annual / 12 months
    nc_assets = float(_get(bs, "assets", "total") or 0)
    # Better: extract from latest ratios if available
    latest_ratios = ratios_by_period.get(period_statements[-1].get("period",""), {})
    nc_assets_from_bsc = 0.0
    # Try to get from the BS items directly
    asset_items = _get(bs, "assets", "items") or []
    da_estimate = 0.0
    da_source   = "none"

    # Scan expense items for depreciation keywords
    exp_items = _get(is_, "expenses", "items") or []
    da_from_items = 0.0
    for item in exp_items:
        name = str(item.get("account_name", "")).lower()
        if any(kw in name for kw in ["depreciation", "amortization", "استهلاك", "إهلاك", "amortisman"]):
            da_from_items += abs(float(item.get("amount", 0) or 0))
    if da_from_items > 0:
        da_estimate = da_from_items
        da_source   = "identified_from_expenses"
    else:
        # Proxy: noncurrent assets × 10% / 12 (monthly)
        for item in asset_items:
            code = str(item.get("account_code", "")).strip()
            try:
                num = int(code[:4]) if len(code) >= 4 else int(code)
            except (ValueError, TypeError):
                num = 0
            if 1400 <= num <= 1999:
                da_estimate += abs(float(item.get("amount", 0) or 0))
        da_estimate = da_estimate * 0.10 / 12   # 10% annual rate, monthly
        da_source   = "proxy_10pct_noncurrent_assets"

    ebitda          = _r2(op + da_estimate)
    ebitda_margin   = _pct(ebitda, rev) if rev else None

    # ── Contribution Margin ───────────────────────────────────────────────────
    # CM = Revenue - Variable Costs (COGS treated as variable; OpEx as semi-fixed)
    # Full variable cost contribution margin
    contribution_margin     = _r2(rev - cogs) if rev else None  # same as gross profit
    contribution_margin_pct = _pct(rev - cogs, rev) if rev else None

    # ── Operating Leverage (Degree of Operating Leverage) ─────────────────────
    dol: Optional[float] = None
    if len(rev_series) >= 2 and rev_series[-2] and op_series[-2]:
        delta_rev = rev_series[-1] - rev_series[-2]
        delta_op  = op_series[-1]  - op_series[-2]
        pct_rev   = delta_rev / abs(rev_series[-2])
        pct_op    = delta_op  / abs(op_series[-2])
        if pct_rev != 0:
            dol = _r2(pct_op / pct_rev)

    # ── Incremental Margin ────────────────────────────────────────────────────
    incremental_margin: Optional[float] = None
    if len(rev_series) >= 2 and len(np_series) >= 2:
        delta_r = rev_series[-1] - rev_series[-2]
        delta_p = np_series[-1]  - np_series[-2]
        incremental_margin = _pct(delta_p, delta_r) if delta_r != 0 else None

    # ── Average margins (full period history) ─────────────────────────────────
    avg_gross_margin    = _r2(_mean(gm_series))
    avg_net_margin      = _r2(_mean([_get(ratios_by_period.get(s.get("period",""), {}),
                                         "profitability", "net_margin_pct")
                                     for s in period_statements]))

    return {
        "ebitda":                    ebitda,
        "ebitda_margin_pct":         ebitda_margin,
        "ebitda_da_estimate":        _r2(da_estimate),
        "ebitda_da_source":          da_source,
        "contribution_margin":       contribution_margin,
        "contribution_margin_pct":   contribution_margin_pct,
        "operating_leverage_dol":    dol,
        "incremental_margin_pct":    incremental_margin,
        "avg_gross_margin_pct":      avg_gross_margin,
        "avg_net_margin_pct":        avg_net_margin,
        "_note": (
            "EBITDA is approximated. "
            "Contribution margin = Revenue - COGS (variable cost proxy). "
            "DOL = %ΔOperatingProfit / %ΔRevenue over last 2 periods."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  2. Advanced Liquidity
# ══════════════════════════════════════════════════════════════════════════════

def compute_advanced_liquidity(
    period_statements: list[dict],
    ratios_by_period:  dict[str, dict],
) -> dict:
    """
    Enhanced liquidity beyond current/quick ratios.

    Cash Ratio = Cash & Equivalents / Current Liabilities
    (Most conservative liquidity measure — no receivables or inventory)

    Working Capital Trend = slope of WC series over available periods

    Cash Burn = monthly average net cash outflow when NP < 0
    (uses net_profit as proxy when operating cash flow not available)
    """
    if not period_statements:
        return {}

    IS = "income_statement"
    BS = "balance_sheet"

    # Build WC series from ratios
    wc_series:    list[Optional[float]] = []
    cash_series:  list[Optional[float]] = []
    cl_series:    list[Optional[float]] = []
    periods_used: list[str] = []

    for s in period_statements:
        p    = s.get("period", "")
        rats = ratios_by_period.get(p, {})
        wc   = _get(rats, "liquidity", "working_capital")
        ca   = _get(rats, "liquidity", "current_assets")
        cl   = _get(rats, "liquidity", "current_liabilities")
        # Cash from BS items via account code 1000-1099
        bs_items = _get(s, BS, "assets", "items") or []
        cash = 0.0
        for item in bs_items:
            code = str(item.get("account_code", "")).strip()
            try:
                num = int(code[:4]) if len(code) >= 4 else int(code)
            except (ValueError, TypeError):
                num = -1
            if 1000 <= num <= 1099:
                cash += abs(float(item.get("amount", 0) or 0))

        wc_series.append(wc)
        cash_series.append(cash if cash > 0 else None)
        cl_series.append(cl)
        periods_used.append(p)

    # ── Cash Ratio (latest) ───────────────────────────────────────────────────
    latest_cash = cash_series[-1] if cash_series else None
    latest_cl   = cl_series[-1]   if cl_series   else None
    cash_ratio  = _r4(_div(latest_cash, latest_cl))

    # ── Working Capital Trend ─────────────────────────────────────────────────
    wc_slope     = _slope(wc_series, window=min(6, len(wc_series)))
    wc_direction = "improving" if (wc_slope and wc_slope > 0) else \
                   "deteriorating" if (wc_slope and wc_slope < 0) else "stable"

    # Last 6 periods of WC
    wc_last6 = [{"period": p, "working_capital": _r2(w)}
                for p, w in zip(periods_used[-6:], wc_series[-6:])]

    # ── Cash Burn Rate ────────────────────────────────────────────────────────
    np_series = [float(_get(s, IS, "net_profit") or 0) for s in period_statements]
    negative_np_periods = [v for v in np_series if v < 0]
    cash_burn: Optional[float] = None
    cash_burn_months_runway: Optional[float] = None
    if negative_np_periods:
        cash_burn = _r2(abs(sum(negative_np_periods) / len(negative_np_periods)))
        if latest_cash and cash_burn:
            cash_burn_months_runway = _r2(latest_cash / cash_burn)

    # ── Operating Cash Proxy ──────────────────────────────────────────────────
    # OCF ≈ Net Profit + D&A (D&A embedded — use NP as conservative floor)
    latest_np = np_series[-1] if np_series else None
    ocf_proxy = _r2(latest_np)  # conservative: no D&A addback

    return {
        "cash_ratio":                cash_ratio,
        "cash":                      _r2(latest_cash),
        "current_liabilities":       _r2(latest_cl),
        "wc_trend_slope":            wc_slope,
        "wc_direction":              wc_direction,
        "wc_series":                 wc_last6,
        "cash_burn_avg_monthly":     cash_burn,
        "cash_burn_months_runway":   cash_burn_months_runway,
        "ocf_proxy":                 ocf_proxy,
        "_note": (
            "Cash ratio = Cash / Current Liabilities (most conservative measure). "
            "WC trend = linear slope of last 6 periods. "
            "Cash burn only present if any period had negative net profit."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  3. Full Efficiency Layer
# ══════════════════════════════════════════════════════════════════════════════

def compute_advanced_efficiency(
    period_statements: list[dict],
    ratios_by_period:  dict[str, dict],
) -> dict:
    """
    Complete efficiency turnover ratios.

    All turnovers use annualised revenue/COGS × (Balance / Revenue or COGS)
    For monthly data: multiply by 12 to annualise, then apply 365 for days.

    Receivables Turnover = Revenue / Receivables
    Payables Turnover    = COGS    / Payables
    Asset Turnover       = Revenue / Total Assets
    """
    if not period_statements:
        return {}

    IS = "income_statement"
    BS = "balance_sheet"

    latest = period_statements[-1]
    is_    = _get(latest, IS) or {}
    bs     = _get(latest, BS) or {}

    rev  = float(_get(is_, "revenue",  "total") or 0)
    cogs = float(_get(is_, "cogs",     "total") or 0)

    # Extract BS components from items
    asset_items = _get(bs, "assets",      "items") or []
    liab_items  = _get(bs, "liabilities", "items") or []

    def _range_sum(items, lo, hi):
        total = 0.0
        for item in items:
            code = str(item.get("account_code", "")).strip()
            try:
                num = int(code[:4]) if len(code) >= 4 else int(code)
            except (ValueError, TypeError):
                num = -1
            if lo <= num <= hi:
                total += abs(float(item.get("amount", 0) or 0))
        return total

    inv  = _range_sum(asset_items, 1200, 1299)
    rec  = _range_sum(asset_items, 1100, 1199)
    pay  = _range_sum(liab_items,  2000, 2099)
    ta   = abs(float(_get(bs, "assets", "total") or 0))

    # ── Turnover Ratios ───────────────────────────────────────────────────────
    inv_turnover  = _r4(_div(cogs, inv))   # times per period
    rec_turnover  = _r4(_div(rev,  rec))   # times per period
    pay_turnover  = _r4(_div(cogs, pay))   # times per period
    asset_turnover= _r4(_div(rev,  ta))    # revenue per unit of assets

    # ── Days versions (using 30-day month) ────────────────────────────────────
    dio_days = _r2(_div(inv, cogs) * 30) if (inv and cogs) else None
    dso_days = _r2(_div(rec, rev)  * 30) if (rec and rev)  else None
    dpo_days = _r2(_div(pay, cogs) * 30) if (pay and cogs) else None
    ccc_days = _r2(dio_days + dso_days - dpo_days) \
               if (dio_days is not None and dso_days is not None and dpo_days is not None) else None

    # ── Revenue per unit of asset (efficiency reading) ────────────────────────
    rev_per_asset = _r4(_div(rev, ta))

    # ── Turnover trends over last 6 periods ───────────────────────────────────
    asset_turnover_series = []
    for s in period_statements[-6:]:
        p    = s.get("period", "")
        r    = float(_get(s, IS, "revenue", "total") or 0)
        bs_s = _get(s, BS) or {}
        ta_s = abs(float(_get(bs_s, "assets", "total") or 0))
        asset_turnover_series.append({
            "period": p,
            "asset_turnover": _r4(_div(r, ta_s)),
        })

    return {
        "inventory_turnover":          inv_turnover,
        "receivables_turnover":        rec_turnover,
        "payables_turnover":           pay_turnover,
        "asset_turnover":              asset_turnover,
        "revenue_per_asset":           rev_per_asset,
        "dio_days":                    dio_days,
        "dso_days":                    dso_days,
        "dpo_days":                    dpo_days,
        "ccc_days":                    ccc_days,
        "asset_turnover_series":       asset_turnover_series,
        "_balances": {
            "inventory":     _r2(inv),
            "receivables":   _r2(rec),
            "payables":      _r2(pay),
            "total_assets":  _r2(ta),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  4. Risk Analysis
# ══════════════════════════════════════════════════════════════════════════════

def compute_risk_analysis(
    period_statements: list[dict],
    ratios_by_period:  dict[str, dict],
) -> dict:
    """
    Risk metrics: volatility, stability, cost structure, earnings consistency.

    Margin Volatility:   std dev of gross_margin_pct over all periods
    Revenue Volatility:  coefficient of variation (std/mean) of revenue
    Revenue Stability:   composite score 0-100 based on trend + volatility
    Cost Structure:      COGS% vs OpEx% — shows business model
    Earnings Consistency: % of periods with positive and growing net profit
    """
    if not period_statements:
        return {}

    IS = "income_statement"
    n  = len(period_statements)

    rev_series  = [float(_get(s, IS, "revenue",   "total")    or 0) for s in period_statements]
    np_series   = [float(_get(s, IS, "net_profit")            or 0) for s in period_statements]
    gm_series   = [float(_get(s, IS, "gross_margin_pct")      or 0) for s in period_statements]
    nm_series   = [float(_get(s, IS, "net_margin_pct")        or 0) for s in period_statements]
    cogs_series = [float(_get(s, IS, "cogs",      "total")    or 0) for s in period_statements]
    opex_series = [float(_get(s, IS, "expenses",  "total")    or 0) for s in period_statements]

    # ── Margin Volatility ─────────────────────────────────────────────────────
    gm_std    = _r2(_sd(gm_series))
    nm_std    = _r2(_sd(nm_series))
    gm_mean   = _mean(gm_series)
    nm_mean   = _mean(nm_series)
    gm_cv     = _r4(_div(gm_std, gm_mean)) if (gm_std and gm_mean) else None   # coefficient of variation
    margin_volatility_rating = (
        "low"    if (gm_cv is not None and gm_cv < 0.05) else
        "medium" if (gm_cv is not None and gm_cv < 0.15) else
        "high"   if gm_cv is not None else "unknown"
    )

    # ── Revenue Stability ─────────────────────────────────────────────────────
    rev_std  = _sd(rev_series)
    rev_mean = _mean(rev_series)
    rev_cv   = _r4(_div(rev_std, rev_mean)) if (rev_std and rev_mean) else None

    # Trend component: positive slope = more stable
    rev_slope = _slope(rev_series, window=min(6, n))
    trend_positive = rev_slope is not None and rev_slope > 0

    # Revenue stability score 0-100
    # Lower CV = more stable. Positive trend = bonus.
    stability_score: Optional[int] = None
    if rev_cv is not None:
        base  = max(0, 100 - int(rev_cv * 200))   # CV of 0.5 → score 0
        bonus = 10 if trend_positive else 0
        stability_score = min(100, base + bonus)

    rev_stability_rating = (
        "stable"   if (stability_score is not None and stability_score >= 70) else
        "moderate" if (stability_score is not None and stability_score >= 40) else
        "volatile" if stability_score is not None else "unknown"
    )

    # ── Cost Structure ────────────────────────────────────────────────────────
    # Average COGS% and OpEx% over all periods
    cogs_pct_series = [_pct(c, r) for c, r in zip(cogs_series, rev_series) if r]
    opex_pct_series = [_pct(o, r) for o, r in zip(opex_series, rev_series) if r]

    avg_cogs_pct = _r2(_mean(cogs_pct_series))
    avg_opex_pct = _r2(_mean(opex_pct_series))

    # Latest values
    latest_rev  = rev_series[-1]  if rev_series  else 0
    latest_cogs = cogs_series[-1] if cogs_series else 0
    latest_opex = opex_series[-1] if opex_series else 0
    latest_cogs_pct = _pct(latest_cogs, latest_rev)
    latest_opex_pct = _pct(latest_opex, latest_rev)

    # Cost structure ratio: COGS / OpEx (> 1 = product cost dominates)
    cogs_to_opex_ratio = _r2(_div(latest_cogs, latest_opex))
    cost_structure_type = (
        "product-cost-heavy"  if (cogs_to_opex_ratio and cogs_to_opex_ratio > 2.5) else
        "opex-heavy"          if (cogs_to_opex_ratio and cogs_to_opex_ratio < 1.5) else
        "balanced"            if cogs_to_opex_ratio is not None else "unknown"
    )

    # ── Earnings Consistency Score ────────────────────────────────────────────
    # % of periods with positive NP
    positive_np_count  = sum(1 for v in np_series if v > 0)
    positive_np_pct    = round(positive_np_count / n * 100, 1) if n else 0

    # % of periods where NP grew vs prior period
    growing_np_count = sum(
        1 for i in range(1, len(np_series))
        if np_series[i] > np_series[i - 1]
    )
    growing_np_pct = round(growing_np_count / max(n - 1, 1) * 100, 1)

    # Composite earnings consistency score 0-100
    earnings_consistency = round((positive_np_pct * 0.6) + (growing_np_pct * 0.4), 1)
    earnings_rating = (
        "consistent"   if earnings_consistency >= 70 else
        "moderate"     if earnings_consistency >= 45 else
        "inconsistent"
    )

    # ── Overall Risk Rating ───────────────────────────────────────────────────
    risk_factors = 0
    if gm_cv is not None and gm_cv > 0.10:           risk_factors += 2
    elif gm_cv is not None and gm_cv > 0.05:         risk_factors += 1
    if rev_cv is not None and rev_cv > 0.20:          risk_factors += 2
    elif rev_cv is not None and rev_cv > 0.10:        risk_factors += 1
    if earnings_consistency < 50:                     risk_factors += 2
    elif earnings_consistency < 70:                   risk_factors += 1
    if avg_cogs_pct is not None and avg_cogs_pct > 65: risk_factors += 1

    risk_rating = (
        "low"      if risk_factors <= 1 else
        "medium"   if risk_factors <= 3 else
        "high"     if risk_factors <= 5 else
        "critical"
    )

    return {
        "margin_volatility": {
            "gross_margin_std_dev":       gm_std,
            "gross_margin_cv":            gm_cv,
            "net_margin_std_dev":         nm_std,
            "gross_margin_mean_pct":      _r2(gm_mean),
            "volatility_rating":          margin_volatility_rating,
        },
        "revenue_stability": {
            "revenue_std_dev":            _r2(rev_std),
            "revenue_cv":                 rev_cv,
            "revenue_trend_slope":        rev_slope,
            "trend_direction":            "up" if trend_positive else "down",
            "stability_score":            stability_score,
            "stability_rating":           rev_stability_rating,
        },
        "cost_structure": {
            "avg_cogs_pct":               avg_cogs_pct,
            "avg_opex_pct":               avg_opex_pct,
            "latest_cogs_pct":            latest_cogs_pct,
            "latest_opex_pct":            latest_opex_pct,
            "cogs_to_opex_ratio":         cogs_to_opex_ratio,
            "cost_structure_type":        cost_structure_type,
        },
        "earnings_consistency": {
            "positive_np_pct":            positive_np_pct,
            "growing_np_pct":             growing_np_pct,
            "consistency_score":          earnings_consistency,
            "consistency_rating":         earnings_rating,
            "periods_analyzed":           n,
        },
        "risk_rating":                    risk_rating,
        "risk_factor_count":             risk_factors,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Main entry point — called from analysis API
# ══════════════════════════════════════════════════════════════════════════════

def compute_advanced_metrics(
    period_statements: list[dict],
    ratios_by_period:  dict[str, dict],
) -> dict:
    """
    Compute all advanced CFO-level metrics.
    Appended to analysis response as "advanced_metrics".

    Input:
      period_statements — list of statement dicts (from _build_period_statements)
      ratios_by_period  — {period: ratios} from run_analysis()

    Output:
      {
        "profitability": {...},
        "liquidity":     {...},
        "efficiency":    {...},
        "risk":          {...},
        "period_count":  int,
        "latest_period": str,
      }
    """
    if not period_statements:
        return {"error": "no data"}

    return {
        "period_count":  len(period_statements),
        "latest_period": period_statements[-1].get("period", ""),
        "profitability": compute_advanced_profitability(period_statements, ratios_by_period),
        "liquidity":     compute_advanced_liquidity(period_statements, ratios_by_period),
        "efficiency":    compute_advanced_efficiency(period_statements, ratios_by_period),
        "risk":          compute_risk_analysis(period_statements, ratios_by_period),
    }
