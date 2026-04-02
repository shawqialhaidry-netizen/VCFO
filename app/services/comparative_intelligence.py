"""
comparative_intelligence.py — Phase: Comparative Intelligence (company + branches)

Builds a deterministic comparison layer across branches within the same company.

Constraints:
  - Reuse existing expense outputs (expense_intelligence_engine bundle outputs).
  - No duplicate financial calculations (all amounts come from statement_engine-derived bundles).
  - Deterministic outputs only (stable sorting, explicit tie-breakers).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


def _r2(x: Any) -> Optional[float]:
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


def _pct(n: Optional[float], d: Optional[float]) -> Optional[float]:
    try:
        nn = float(n or 0)
        dd = float(d or 0)
        if dd <= 0:
            return None
        return round(nn / dd * 100, 2)
    except (TypeError, ValueError):
        return None


def _safe_float(x: Any) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _period_index(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("period") or ""): r for r in (rows or []) if r.get("period")}


def _latest_row(bundle: dict) -> Optional[dict]:
    rows = ((bundle or {}).get("expense_analysis") or {}).get("by_period") or []
    return rows[-1] if rows else None


def _prev_row(bundle: dict) -> Optional[dict]:
    rows = ((bundle or {}).get("expense_analysis") or {}).get("by_period") or []
    return rows[-2] if len(rows) >= 2 else None


def _yoy_row(bundle: dict, period: str) -> Optional[dict]:
    """
    Find the row for same month prior year.
    Period format: YYYY-MM. If parsing fails, returns None.
    """
    try:
        y, m = period.split("-", 1)
        y_i = int(y)
        if len(m) != 2:
            return None
        target = f"{y_i - 1}-{m}"
    except Exception:
        return None
    rows = ((bundle or {}).get("expense_analysis") or {}).get("by_period") or []
    idx = _period_index(rows)
    return idx.get(target)


@dataclass(frozen=True)
class _BranchPoint:
    branch_id: str
    branch_name: str
    period: str
    revenue: Optional[float]
    total_expense: Optional[float]
    expense_pct_of_revenue: Optional[float]
    categories: dict[str, float]


def _branch_point(branch_id: str, branch_name: str, bundle: dict) -> Optional[_BranchPoint]:
    r = _latest_row(bundle)
    if not r:
        return None
    cats = r.get("categories") or {}
    return _BranchPoint(
        branch_id=branch_id,
        branch_name=branch_name,
        period=str(r.get("period") or ""),
        revenue=_r2(r.get("revenue")),
        total_expense=_r2(r.get("total_expense")),
        expense_pct_of_revenue=_r2(r.get("expense_pct_of_revenue")),
        categories={str(k): _safe_float(v) for k, v in cats.items()},
    )


def _top_category(point: _BranchPoint) -> Optional[dict]:
    if not point.categories:
        return None
    cat, amt = sorted(point.categories.items(), key=lambda kv: (-_safe_float(kv[1]), kv[0]))[0]
    pct = _pct(amt, point.revenue)
    return {"category": cat, "amount": _r2(amt), "pct_of_revenue": pct}


def _category_share_map(categories: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, _safe_float(v)) for v in (categories or {}).values())
    if total <= 0:
        return {}
    return {k: max(0.0, _safe_float(v)) / total for k, v in categories.items()}


def _l1_distance(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a.keys()) | set(b.keys())
    return float(sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys))


def build_comparative_intelligence(
    *,
    company_expense_bundle: dict,
    branch_bundles: list[dict],
) -> dict[str, Any]:
    """
    branch_bundles: [{branch_id, branch_name, expense_bundle}]
    """
    # Company latest (for contributions / ratio context)
    comp_latest = _latest_row(company_expense_bundle) or {}
    comp_period = str(comp_latest.get("period") or "")
    comp_rev = _r2(comp_latest.get("revenue"))
    comp_exp = _r2(comp_latest.get("total_expense"))
    comp_ratio = _r2(comp_latest.get("expense_pct_of_revenue"))
    comp_cats = {str(k): _safe_float(v) for k, v in (comp_latest.get("categories") or {}).items()}

    # Points
    points: list[_BranchPoint] = []
    for b in (branch_bundles or []):
        bid = str(b.get("branch_id") or "")
        bname = str(b.get("branch_name") or "")
        bun = b.get("expense_bundle") or {}
        pt = _branch_point(bid, bname, bun)
        if pt and pt.period:
            points.append(pt)

    # Rankings (stable)
    def _tie(p: _BranchPoint):
        return (p.branch_name.lower(), p.branch_id)

    by_total_desc = sorted(points, key=lambda p: (-_safe_float(p.total_expense), *_tie(p)))
    by_total_asc = sorted(points, key=lambda p: (_safe_float(p.total_expense), *_tie(p)))
    by_ratio_desc = sorted(points, key=lambda p: (-(p.expense_pct_of_revenue or -1e9), *_tie(p)))
    by_ratio_asc = sorted(points, key=lambda p: ((p.expense_pct_of_revenue if p.expense_pct_of_revenue is not None else 1e9), *_tie(p)))

    def _rank_entry(p: _BranchPoint) -> dict:
        return {
            "branch_id": p.branch_id,
            "branch_name": p.branch_name,
            "period": p.period,
            "revenue": p.revenue,
            "total_expense": p.total_expense,
            "expense_pct_of_revenue": p.expense_pct_of_revenue,
        }

    branch_rankings = {
        "highest_total_expense": _rank_entry(by_total_desc[0]) if by_total_desc else None,
        "lowest_total_expense": _rank_entry(by_total_asc[0]) if by_total_asc else None,
        "highest_expense_pct_of_revenue": _rank_entry(by_ratio_desc[0]) if by_ratio_desc else None,
        "lowest_expense_pct_of_revenue": _rank_entry(by_ratio_asc[0]) if by_ratio_asc else None,
    }

    # Branch vs company contributions (latest-by-branch, compared against company latest)
    contrib_rows: list[dict] = []
    for p in sorted(points, key=lambda p: (*_tie(p), p.period)):
        contrib_rows.append(
            {
                "branch_id": p.branch_id,
                "branch_name": p.branch_name,
                "period": p.period,
                "branch_total_expense": p.total_expense,
                "company_period": comp_period or None,
                "company_total_expense": comp_exp,
                "branch_contribution_pct_of_company_expense": _pct(p.total_expense, comp_exp),
                "branch_revenue": p.revenue,
                "company_revenue": comp_rev,
                "branch_contribution_pct_of_company_revenue": _pct(p.revenue, comp_rev) if comp_rev else None,
                # Simple deterministic impact signal: branch ratio delta vs company ratio (not a recomputation)
                "branch_vs_company_expense_ratio_pp": (
                    round((p.expense_pct_of_revenue - comp_ratio), 2)
                    if (p.expense_pct_of_revenue is not None and comp_ratio is not None)
                    else None
                ),
            }
        )

    # Cost pressure (MoM / YoY deltas on total_expense, no extra math beyond deltas)
    pressure: list[dict] = []
    for b in (branch_bundles or []):
        bid = str(b.get("branch_id") or "")
        bname = str(b.get("branch_name") or "")
        bun = b.get("expense_bundle") or {}
        latest = _latest_row(bun)
        prev = _prev_row(bun)
        if not latest:
            continue
        period = str(latest.get("period") or "")
        te = _safe_float(latest.get("total_expense"))
        te_prev = _safe_float(prev.get("total_expense")) if prev else None
        mom_delta = (te - te_prev) if te_prev is not None else None
        yoy = _yoy_row(bun, period)
        te_yoy = _safe_float(yoy.get("total_expense")) if yoy else None
        yoy_delta = (te - te_yoy) if te_yoy is not None else None
        ratio = _r2(latest.get("expense_pct_of_revenue"))
        pressure.append(
            {
                "branch_id": bid,
                "branch_name": bname,
                "period": period,
                "total_expense": _r2(te),
                "mom_delta_total_expense": _r2(mom_delta),
                "yoy_delta_total_expense": _r2(yoy_delta),
                "expense_pct_of_revenue": ratio,
            }
        )

    driving_mom = None
    driving_yoy = None
    if pressure:
        driving_mom = sorted(
            [p for p in pressure if p.get("mom_delta_total_expense") is not None],
            key=lambda x: (-_safe_float(x.get("mom_delta_total_expense")), str(x.get("branch_name") or "").lower(), str(x.get("branch_id") or "")),
        )
        driving_mom = driving_mom[0] if driving_mom else None
        driving_yoy = sorted(
            [p for p in pressure if p.get("yoy_delta_total_expense") is not None],
            key=lambda x: (-_safe_float(x.get("yoy_delta_total_expense")), str(x.get("branch_name") or "").lower(), str(x.get("branch_id") or "")),
        )
        driving_yoy = driving_yoy[0] if driving_yoy else None

    most_inefficient = branch_rankings.get("highest_expense_pct_of_revenue")
    most_efficient = branch_rankings.get("lowest_expense_pct_of_revenue")

    # "Improving": biggest negative MoM delta in expense ratio (pp) if available; fallback to total_expense MoM
    improving = None
    improving_candidates: list[dict] = []
    for b in (branch_bundles or []):
        bun = b.get("expense_bundle") or {}
        latest = _latest_row(bun)
        prev = _prev_row(bun)
        if not latest or not prev:
            continue
        lr = latest.get("expense_pct_of_revenue")
        pr = prev.get("expense_pct_of_revenue")
        if lr is None or pr is None:
            continue
        improving_candidates.append(
            {
                "branch_id": str(b.get("branch_id") or ""),
                "branch_name": str(b.get("branch_name") or ""),
                "period": str(latest.get("period") or ""),
                "expense_ratio_delta_pp": _r2(_safe_float(lr) - _safe_float(pr)),
                "expense_pct_of_revenue": _r2(lr),
            }
        )
    if improving_candidates:
        improving = sorted(
            improving_candidates,
            key=lambda x: (_safe_float(x.get("expense_ratio_delta_pp")), str(x.get("branch_name") or "").lower(), str(x.get("branch_id") or "")),
        )[0]

    cost_pressure = {
        "driving_expense_increase_mom": driving_mom,
        "driving_expense_increase_yoy": driving_yoy,
        "most_inefficient_branch": most_inefficient,
        "most_efficient_branch": most_efficient,
        "most_improving_branch": improving,
        "all_branches": sorted(pressure, key=lambda x: (str(x.get("branch_name") or "").lower(), str(x.get("branch_id") or ""))),
    }

    # Efficiency ranking (full list)
    efficiency_ranking = {
        "by_expense_pct_of_revenue_desc": [_rank_entry(p) for p in by_ratio_desc],
        "by_expense_pct_of_revenue_asc": [_rank_entry(p) for p in by_ratio_asc],
    }

    # Category comparison
    comp_share = _category_share_map(comp_cats)
    branch_cats: list[dict] = []
    abnormal: list[dict] = []
    for p in points:
        top = _top_category(p)
        branch_cats.append(
            {
                "branch_id": p.branch_id,
                "branch_name": p.branch_name,
                "period": p.period,
                "top_category": top,
            }
        )
        shares = _category_share_map(p.categories)
        dist = _l1_distance(shares, comp_share) if comp_share else None
        if dist is not None:
            abnormal.append(
                {
                    "branch_id": p.branch_id,
                    "branch_name": p.branch_name,
                    "period": p.period,
                    "distribution_distance_l1": _r2(dist),
                }
            )

    most_abnormal = None
    if abnormal:
        most_abnormal = sorted(
            abnormal,
            key=lambda x: (-_safe_float(x.get("distribution_distance_l1")), str(x.get("branch_name") or "").lower(), str(x.get("branch_id") or "")),
        )[0]

    category_comparison = {
        "top_category_per_branch": sorted(branch_cats, key=lambda x: (str(x.get("branch_name") or "").lower(), str(x.get("branch_id") or ""))),
        "most_abnormal_category_distribution": most_abnormal,
        "all_distribution_distances": sorted(abnormal, key=lambda x: (str(x.get("branch_name") or "").lower(), str(x.get("branch_id") or ""))),
    }

    return {
        "branch_rankings": branch_rankings,
        "branch_vs_company": {
            "company_latest_period": comp_period or None,
            "company_total_expense": comp_exp,
            "company_revenue": comp_rev,
            "company_expense_pct_of_revenue": comp_ratio,
            "branch_contributions": contrib_rows,
        },
        "cost_pressure": cost_pressure,
        "efficiency_ranking": efficiency_ranking,
        "category_comparison": category_comparison,
    }

