"""
period_aggregation.py — Phase 14 (Hardened)
Aggregation layer that builds annual/YTD views from monthly statements.

Source of truth: monthly period_statements from _build_period_statements().
This module NEVER touches files, DB, or the financial engine.

KPI rules:
  Summed:  revenue, cogs, expenses, tax, gross_profit, operating_profit, net_profit
  Derived: gross_margin_pct, operating_margin_pct, net_margin_pct
           — always recalculated from aggregated sums, never averaged or summed directly

Balance-sheet ratios (current_ratio, DSO, etc.) are NOT aggregated here —
they are point-in-time metrics and must be read from individual period statements.

Hardening:
  - Partial/incomplete years are never labeled as full-year comparisons
    unless both sides are complete OR explicitly flagged as partial
  - YTD comparison uses STRICTLY same calendar months from prior year
  - Gap detection: flags years with missing months
  - 1-month YTD handled safely (no division errors, no false comparisons)
  - Sparse/gapped periods: months are matched by name, not by count/index
"""
from __future__ import annotations

from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _safe_div(num: float, den: float) -> Optional[float]:
    if den and abs(den) > 0.001:
        return round(num / den * 100, 2)
    return None


def _pct_change(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    if curr is None or prev is None or prev == 0:
        return None
    return round((curr - prev) / abs(prev) * 100, 2)


def _extract_scalars(stmt: dict) -> dict:
    """Extract only flow (additive) IS values. Never extracts ratios."""
    is_ = stmt.get("income_statement", {})
    return {
        "revenue":          float(is_.get("revenue",   {}).get("total", 0) or 0),
        "cogs":             float(is_.get("cogs",      {}).get("total", 0) or 0),
        "expenses":         float(is_.get("expenses",  {}).get("total", 0) or 0),
        "tax":              float(is_.get("tax",       {}).get("total", 0) or 0),
        "gross_profit":     float(is_.get("gross_profit",     0) or 0),
        "operating_profit": float(is_.get("operating_profit", 0) or 0),
        "net_profit":       float(is_.get("net_profit",       0) or 0),
        # Note: margin percentages deliberately excluded — derived after aggregation
    }


def _aggregate_scalars(stmts: list[dict]) -> dict:
    """
    Sum flow IS values over multiple monthly statements.
    Margins are recalculated from sums — NEVER summed or averaged directly.
    """
    totals = {k: 0.0 for k in (
        "revenue", "cogs", "expenses", "tax",
        "gross_profit", "operating_profit", "net_profit"
    )}
    for s in stmts:
        row = _extract_scalars(s)
        for k in totals:
            totals[k] += row[k]
    # Recalculate margin percentages from aggregated totals
    rev = totals["revenue"]
    totals["gross_margin_pct"]     = _safe_div(totals["gross_profit"],     rev)
    totals["operating_margin_pct"] = _safe_div(totals["operating_profit"], rev)
    totals["net_margin_pct"]       = _safe_div(totals["net_profit"],       rev)
    return totals


def _detect_gaps(months_present: list[str], year: str) -> dict:
    """
    Detect missing months within a year.
    Returns: { has_gaps, missing_months, months_present }
    """
    expected = {f"{year}-{m:02d}" for m in range(1, 13)}
    present  = set(months_present)
    missing  = sorted(expected - present)
    return {
        "has_gaps":       len(missing) > 0,
        "missing_months": missing,
        "months_present": sorted(months_present),
    }


def _group_by_year(monthly: list[dict]) -> dict[str, list[dict]]:
    """Group YYYY-MM statements by year. Ignores non-YYYY-MM periods."""
    groups: dict[str, list[dict]] = {}
    for s in monthly:
        p = s.get("period", "")
        if len(p) == 7 and p[4] == "-":
            year = p[:4]
            groups.setdefault(year, []).append(s)
    for year in groups:
        groups[year].sort(key=lambda s: s.get("period", ""))
    return groups


def _changes(curr: dict, prior: dict) -> dict:
    """Percentage change for each flow metric and margin."""
    keys = (
        "revenue", "gross_profit", "operating_profit", "net_profit",
        "gross_margin_pct", "operating_margin_pct", "net_margin_pct",
    )
    return {k: _pct_change(curr.get(k), prior.get(k)) for k in keys}


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_annual_layer(all_stmts: list[dict]) -> dict:
    """
    Build the complete annual/YTD analysis layer from monthly statements.

    Hardening guarantees:
    1. full_year_current_vs_prior is None when current year is incomplete
       AND prior year is also incomplete (ambiguous basis)
    2. ytd_prior uses STRICTLY same calendar months (by name) as current YTD
    3. Gap detection per year (has_gaps, missing_months)
    4. 1-month YTD: valid, no false MoM/YoY forced
    5. Sparse periods: month matching by period string, never by index
    6. Balance-sheet ratios excluded from all aggregation
    """
    if not all_stmts:
        return {}

    monthly = [
        s for s in all_stmts
        if len(s.get("period", "")) == 7 and s["period"][4] == "-"
    ]
    if not monthly:
        return {}

    monthly.sort(key=lambda s: s["period"])
    by_year = _group_by_year(monthly)
    years   = sorted(by_year.keys())

    latest_period = monthly[-1]["period"]
    latest_year   = latest_period[:4]
    latest_month  = latest_period[5:7]   # "MM"
    prior_years   = [y for y in years if y < latest_year]

    # ── latest_month ─────────────────────────────────────────────────────────
    latest_scalars = _extract_scalars(monthly[-1])
    rev = latest_scalars["revenue"]
    latest_month_block = {
        "period": latest_period,
        **latest_scalars,
        "gross_margin_pct":     _safe_div(latest_scalars["gross_profit"],     rev),
        "operating_margin_pct": _safe_div(latest_scalars["operating_profit"], rev),
        "net_margin_pct":       _safe_div(latest_scalars["net_profit"],       rev),
    }

    # ── YTD current ───────────────────────────────────────────────────────────
    ytd_stmts     = by_year.get(latest_year, [])
    ytd_months    = [s["period"] for s in ytd_stmts]
    ytd_agg       = _aggregate_scalars(ytd_stmts) if ytd_stmts else {}
    ytd_gap_info  = _detect_gaps(ytd_months, latest_year)

    # Check for gaps within YTD window (months between Jan and latest_month)
    ytd_expected_count = int(latest_month)  # e.g. "03" → 3
    ytd_has_internal_gap = len(ytd_stmts) < ytd_expected_count

    ytd_block = {
        "year":                latest_year,
        "months":              ytd_months,
        "month_count":         len(ytd_stmts),
        "months_available":    ytd_months,
        "has_gaps":            ytd_has_internal_gap,
        "missing_count":       max(0, ytd_expected_count - len(ytd_stmts)),
        "latest_period":       latest_period,
        "is_single_month":     len(ytd_stmts) == 1,
        **ytd_agg,
    }

    # ── YTD prior — strictly same calendar months only ────────────────────────
    ytd_prior_block = None
    if prior_years:
        prior_year      = prior_years[-1]
        prior_all       = by_year.get(prior_year, [])
        # Match ONLY the exact same month codes that exist in current YTD
        current_month_codes = {p[5:7] for p in ytd_months}    # {"01","02","03"}
        prior_ytd_stmts = [
            s for s in prior_all
            if s["period"][5:7] in current_month_codes
        ]
        if prior_ytd_stmts:
            prior_ytd_months = [s["period"] for s in prior_ytd_stmts]
            prior_ytd_agg    = _aggregate_scalars(prior_ytd_stmts)
            ytd_prior_block  = {
                "year":             prior_year,
                "months":           prior_ytd_months,
                "month_count":      len(prior_ytd_stmts),
                "months_available": prior_ytd_months,
                "basis_months":     sorted(current_month_codes),
                "has_gaps":         len(prior_ytd_stmts) < len(ytd_stmts),
                **prior_ytd_agg,
            }

    # ── Full years ────────────────────────────────────────────────────────────
    full_years = []
    for year in sorted(years, reverse=True):
        yr_stmts      = by_year[year]
        yr_months     = [s["period"] for s in yr_stmts]
        yr_agg        = _aggregate_scalars(yr_stmts)
        complete      = len(yr_stmts) == 12
        gap_info      = _detect_gaps(yr_months, year)
        full_years.append({
            "year":             year,
            "months":           yr_months,
            "month_count":      len(yr_stmts),
            "complete":         complete,
            "has_gaps":         gap_info["has_gaps"],
            "missing_months":   gap_info["missing_months"],
            **yr_agg,
        })

    # ── Comparisons ──────────────────────────────────────────────────────────

    # 1. YTD vs prior YTD — only when both have same months
    ytd_vs_prior = None
    if ytd_prior_block:
        # Comparison is valid when prior has all same months as current
        basis_complete = (ytd_prior_block["month_count"] == ytd_block["month_count"])
        ytd_vs_prior = {
            "current_year":     latest_year,
            "prior_year":       ytd_prior_block["year"],
            "current_months":   ytd_block["month_count"],
            "prior_months":     ytd_prior_block["month_count"],
            "basis_complete":   basis_complete,
            "comparable":       basis_complete,
            "changes":          _changes(ytd_block, ytd_prior_block) if basis_complete else None,
            "changes_partial":  _changes(ytd_block, ytd_prior_block) if not basis_complete else None,
        }

    # 2. Latest month vs prior month
    mom_prior = monthly[-2] if len(monthly) >= 2 else None
    mom_block = {
        "current_period": latest_period,
        "prior_period":   mom_prior["period"] if mom_prior else None,
        "available":      mom_prior is not None,
        "changes": _changes(
            latest_month_block,
            {**_extract_scalars(mom_prior), **{
                "gross_margin_pct":     _safe_div(_extract_scalars(mom_prior)["gross_profit"], _extract_scalars(mom_prior)["revenue"]),
                "operating_margin_pct": _safe_div(_extract_scalars(mom_prior)["operating_profit"], _extract_scalars(mom_prior)["revenue"]),
                "net_margin_pct":       _safe_div(_extract_scalars(mom_prior)["net_profit"], _extract_scalars(mom_prior)["revenue"]),
            }}
        ) if mom_prior else {},
    }

    # 3. Latest month vs same month last year (strict: exact period match)
    same_month_ly_block = None
    if prior_years:
        same_month_ly_period = f"{prior_years[-1]}-{latest_month}"
        same_month_ly = next(
            (s for s in monthly if s["period"] == same_month_ly_period), None
        )
        if same_month_ly:
            ly_sc = _extract_scalars(same_month_ly)
            ly_rev = ly_sc["revenue"]
            ly_with_margins = {
                **ly_sc,
                "gross_margin_pct":     _safe_div(ly_sc["gross_profit"],     ly_rev),
                "operating_margin_pct": _safe_div(ly_sc["operating_profit"], ly_rev),
                "net_margin_pct":       _safe_div(ly_sc["net_profit"],       ly_rev),
            }
            same_month_ly_block = {
                "current_period": latest_period,
                "prior_period":   same_month_ly_period,
                "changes":        _changes(latest_month_block, ly_with_margins),
            }

    # 4. Full year current vs prior
    # Rule: only emit when prior year is complete (12 months)
    # If current is partial, flag it but still emit with explicit warning
    fy_vs_prior = None
    fy_years = full_years   # sorted desc
    if len(fy_years) >= 2:
        fy_curr  = fy_years[0]
        fy_prior = fy_years[1]
        prior_complete = fy_prior["complete"]
        curr_complete  = fy_curr["complete"]
        # Only emit if prior year is complete (reliable baseline)
        if prior_complete:
            fy_vs_prior = {
                "current_year":       fy_curr["year"],
                "prior_year":         fy_prior["year"],
                "current_complete":   curr_complete,
                "prior_complete":     prior_complete,
                "annualized_current": not curr_complete,   # flag partial current
                "comparable":         curr_complete,       # True only when both complete
                "changes":            _changes(fy_curr, fy_prior),
                "warning": (
                    None if curr_complete
                    else f"Current year {fy_curr['year']} has only {fy_curr['month_count']} months — "
                         f"comparison is partial, not annualized"
                ),
            }

    return {
        "latest_month": latest_month_block,
        "ytd":          ytd_block,
        "ytd_prior":    ytd_prior_block,
        "full_years":   full_years,
        "comparisons": {
            "ytd_vs_prior_ytd":              ytd_vs_prior,
            "latest_month_vs_prior_month":   mom_block,
            "latest_month_vs_same_month_ly": same_month_ly_block,
            "full_year_current_vs_prior":    fy_vs_prior,
        },
        "meta": {
            "years_available":       years,
            "latest_period":         latest_period,
            "latest_year":           latest_year,
            "ytd_months":            ytd_months,
            "ytd_has_gaps":          ytd_has_internal_gap,
            "total_monthly":         len(monthly),
            "current_year_complete": len(by_year.get(latest_year, [])) == 12,
        },
    }
