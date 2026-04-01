"""
time_scope.py — Phase 22
Universal time-scope engine for VCFO.

Responsibilities:
  - Parse and validate scope parameters
  - Resolve a sorted list of matching YYYY-MM periods
  - Filter a list of statement dicts to the resolved scope
  - No DB access, no HTTP — pure function

Scope types:
  month   → single YYYY-MM period
  year    → all 12 months of YYYY
  ytd     → Jan through latest available month of YYYY
  custom  → from_period to to_period inclusive
  all     → pass-through (backward-compat with legacy "ALL")
"""
from __future__ import annotations
import re
from typing import Optional


# ── Validation ────────────────────────────────────────────────────────────────

_PERIOD_RE = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")
_YEAR_RE   = re.compile(r"^\d{4}$")


def _valid_period(p: str) -> bool:
    return bool(_PERIOD_RE.match(str(p or "")))


def _valid_year(y: str) -> bool:
    return bool(_YEAR_RE.match(str(y or "")))


def _months_in_year(year: str) -> list[str]:
    return [f"{year}-{m:02d}" for m in range(1, 13)]


def _period_cmp(p: str) -> str:
    """Make period safely comparable (returns canonical YYYY-MM or '')."""
    return p if _valid_period(p) else ""


# ── Scope builder ─────────────────────────────────────────────────────────────

def resolve_scope(
    basis_type:  str = "all",
    period:      Optional[str] = None,   # YYYY-MM for basis_type=month
    year:        Optional[str] = None,   # YYYY    for basis_type=year or ytd
    from_period: Optional[str] = None,   # YYYY-MM for basis_type=custom
    to_period:   Optional[str] = None,   # YYYY-MM for basis_type=custom
    available_periods: Optional[list[str]] = None,  # from actual data
) -> dict:
    """
    Build a normalized scope object.

    Returns:
    {
      "basis_type": str,          # normalised type
      "label":      str,          # human-readable label
      "months":     [YYYY-MM],    # sorted list of target months
      "year":       str | None,
      "from_period":str | None,
      "to_period":  str | None,
      "error":      str | None,   # set if inputs are invalid
    }
    """
    bt = (basis_type or "all").strip().lower()
    avail = sorted(set(available_periods or []))

    # ── month ─────────────────────────────────────────────────────────────────
    if bt == "month":
        if not period or not _valid_period(period):
            return _err(bt, f"Invalid period '{period}'. Use YYYY-MM format.")
        return {
            "basis_type":  "month",
            "label":       period,
            "months":      [period],
            "year":        period[:4],
            "from_period": period,
            "to_period":   period,
            "error":       None,
        }

    # ── year ──────────────────────────────────────────────────────────────────
    if bt == "year":
        yr = (year or "").strip()
        if not _valid_year(yr):
            return _err(bt, f"Invalid year '{yr}'. Use YYYY format.")
        months = _months_in_year(yr)
        return {
            "basis_type":  "year",
            "label":       f"FY {yr}",
            "months":      months,
            "year":        yr,
            "from_period": f"{yr}-01",
            "to_period":   f"{yr}-12",
            "error":       None,
        }

    # ── ytd ───────────────────────────────────────────────────────────────────
    if bt == "ytd":
        # Determine target year
        if year and _valid_year(year):
            yr = year
        elif avail:
            yr = avail[-1][:4]  # latest year in available data
        else:
            return _err(bt, "No year specified and no available periods.")

        # Find latest available month within that year
        yr_months = [p for p in avail if p.startswith(yr)]
        if yr_months:
            end = max(yr_months)
        else:
            # No data for that year yet — default to Jan (scope label remains explicit).
            end = f"{yr}-01"

        months = [m for m in _months_in_year(yr) if m <= end]
        return {
            "basis_type":  "ytd",
            "label":       f"YTD {yr}",
            "months":      months,
            "year":        yr,
            "from_period": f"{yr}-01",
            "to_period":   end,
            "error":       None,
        }

    # ── custom ────────────────────────────────────────────────────────────────
    if bt == "custom":
        fp = (from_period or "").strip()
        tp = (to_period   or "").strip()
        if not _valid_period(fp):
            return _err(bt, f"Invalid from_period '{fp}'. Use YYYY-MM format.")
        if not _valid_period(tp):
            return _err(bt, f"Invalid to_period '{tp}'. Use YYYY-MM format.")
        if fp > tp:
            return _err(bt, f"from_period ({fp}) must not be after to_period ({tp}).")

        # Generate all YYYY-MM between fp and tp
        def _next_month(p: str) -> str:
            y, m = int(p[:4]), int(p[5:7])
            m += 1
            if m > 12:
                m, y = 1, y + 1
            return f"{y:04d}-{m:02d}"

        months: list[str] = []
        cur = fp
        while cur <= tp:
            months.append(cur)
            if len(months) > 120:   # hard cap 10 years
                break
            cur = _next_month(cur)

        label = fp if fp == tp else f"{fp} → {tp}"
        return {
            "basis_type":  "custom",
            "label":       label,
            "months":      months,
            "year":        None,
            "from_period": fp,
            "to_period":   tp,
            "error":       None,
        }

    # ── all (default / backward-compat) ──────────────────────────────────────
    months = avail if avail else []
    label  = "All Periods"
    if avail:
        label = f"{avail[0]} → {avail[-1]}" if avail[0] != avail[-1] else avail[0]
    return {
        "basis_type":  "all",
        "label":       label,
        "months":      months,
        "year":        None,
        "from_period": avail[0]  if avail else None,
        "to_period":   avail[-1] if avail else None,
        "error":       None,
    }


def _err(bt: str, msg: str) -> dict:
    return {
        "basis_type": bt, "label": "Error",
        "months": [], "year": None,
        "from_period": None, "to_period": None,
        "error": msg,
    }


# ── Statement filter ──────────────────────────────────────────────────────────

def filter_by_scope(
    all_stmts: list[dict],
    scope:     dict,
) -> list[dict]:
    """
    Filter a sorted list of statement dicts to only those whose 'period'
    is in scope['months']. Preserves chronological order.

    Falls back to all_stmts if scope has error or empty months.
    """
    if scope.get("error") or not scope.get("months"):
        return all_stmts

    target = set(scope["months"])
    filtered = [s for s in all_stmts if s.get("period") in target]
    return filtered if filtered else all_stmts


# ── Query param helper (for FastAPI endpoints) ───────────────────────────────

def scope_from_params(
    basis_type:  str,
    period:      Optional[str],
    year:        Optional[str],
    from_period: Optional[str],
    to_period:   Optional[str],
    all_stmts:   list[dict],
) -> dict:
    """
    Convenience wrapper — builds scope and validates against available data.
    Returns scope dict with 'months' filtered to periods that actually exist.
    """
    available = sorted(s.get("period", "") for s in all_stmts if s.get("period"))
    scope = resolve_scope(
        basis_type  = basis_type,
        period      = period,
        year        = year,
        from_period = from_period,
        to_period   = to_period,
        available_periods = available,
    )
    return scope
