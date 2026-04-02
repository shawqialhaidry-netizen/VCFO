"""
financial_brain.py — Phase 6 Core Financial Brain

Deterministic, explainable reasoning layer (no black-box AI).

Builds a causal narrative that links:
  - what changed (MoM / YoY deltas)
  - why it changed (revenue linkage, category drivers, branch contribution, efficiency shifts)
  - root cause classification (cost-driven / revenue-driven / mix effect / structural inefficiency)
  - driver linking (anomalies + comparative signals + decisions)

Constraints:
  - No raw TB recalculation; use statement-derived bundles and existing engines.
  - Deterministic outputs (stable ordering, explicit tie-breakers).
"""

from __future__ import annotations

from typing import Any, Optional


def _r2(x: Any) -> Optional[float]:
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


def _safe_float(x: Any) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _pct(n: Optional[float], d: Optional[float]) -> Optional[float]:
    try:
        nn = float(n or 0)
        dd = float(d or 0)
        if dd <= 0:
            return None
        return round(nn / dd * 100, 2)
    except (TypeError, ValueError):
        return None


def _latest_row(bundle: dict) -> Optional[dict]:
    rows = ((bundle or {}).get("expense_analysis") or {}).get("by_period") or []
    return rows[-1] if rows else None


def _prev_row(bundle: dict) -> Optional[dict]:
    rows = ((bundle or {}).get("expense_analysis") or {}).get("by_period") or []
    return rows[-2] if len(rows) >= 2 else None


def _yoy_row(bundle: dict, period: str) -> Optional[dict]:
    try:
        y, m = period.split("-", 1)
        y_i = int(y)
        if len(m) != 2:
            return None
        target = f"{y_i - 1}-{m}"
    except Exception:
        return None
    rows = ((bundle or {}).get("expense_analysis") or {}).get("by_period") or []
    for r in rows:
        if str(r.get("period") or "") == target:
            return r
    return None


def _top_category_delta(latest: dict, previous: dict) -> Optional[dict]:
    lc = (latest or {}).get("categories") or {}
    pc = (previous or {}).get("categories") or {}
    keys = set(lc.keys()) | set(pc.keys())
    deltas = []
    for k in keys:
        d = _safe_float(lc.get(k)) - _safe_float(pc.get(k))
        deltas.append((str(k), d))
    if not deltas:
        return None
    k, d = sorted(deltas, key=lambda x: (-abs(x[1]), x[0]))[0]
    return {"category": k, "delta": _r2(d)}


def _classify_root_cause(
    *,
    expense_delta: float,
    revenue_delta: float,
    expense_ratio_delta_pp: Optional[float],
    driver_branch_expense_ratio: Optional[float],
) -> str:
    """
    Deterministic root cause classification rules.
    """
    # Structural inefficiency: expense ratio is very high (branch driver).
    if driver_branch_expense_ratio is not None and float(driver_branch_expense_ratio) >= 90:
        return "structural_inefficiency"

    # Revenue-driven: revenue down, expenses flat/up → ratio deterioration driven by denominator.
    if revenue_delta < 0 and expense_delta >= 0:
        return "revenue_driven"

    # Cost-driven: expenses up materially while revenue flat/down.
    if expense_delta > 0 and revenue_delta <= 0:
        return "cost_driven"

    # Structural inefficiency: ratio worsened significantly while revenue is not the driver.
    if expense_ratio_delta_pp is not None and float(expense_ratio_delta_pp) >= 5:
        return "structural_inefficiency"

    # Mix effect: both moving same direction but ratio changes.
    if expense_ratio_delta_pp is not None and abs(float(expense_ratio_delta_pp)) >= 1:
        return "mix_effect"

    # Default (stable / ambiguous)
    return "mix_effect"


def build_financial_brain_company(
    *,
    company_id: str,
    company_name: str,
    currency: str,
    expense_bundle: dict,
    comparative_intelligence: dict,
    expense_decisions_v2: list[dict],
    anomalies: list[dict],
    lang: str = "en",
) -> dict[str, Any]:
    _ = lang
    latest = _latest_row(expense_bundle) or {}
    prev = _prev_row(expense_bundle) or {}
    period = str(latest.get("period") or "")
    if not period:
        return {"available": False, "reason": "no_periods"}

    yoy = _yoy_row(expense_bundle, period) or {}

    # Core deltas (statement-derived)
    te = _safe_float(latest.get("total_expense"))
    rev = _safe_float(latest.get("revenue"))
    ratio = latest.get("expense_pct_of_revenue")

    te_prev = _safe_float(prev.get("total_expense")) if prev else 0.0
    rev_prev = _safe_float(prev.get("revenue")) if prev else 0.0
    ratio_prev = prev.get("expense_pct_of_revenue")

    te_yoy = _safe_float(yoy.get("total_expense")) if yoy else 0.0
    rev_yoy = _safe_float(yoy.get("revenue")) if yoy else 0.0
    ratio_yoy = yoy.get("expense_pct_of_revenue")

    mom = {
        "period": period,
        "expense_delta": _r2(te - te_prev),
        "revenue_delta": _r2(rev - rev_prev),
        "expense_ratio_delta_pp": _r2((_safe_float(ratio) - _safe_float(ratio_prev)) if (ratio is not None and ratio_prev is not None) else None),
    }
    yoy_d = {
        "period": period,
        "expense_delta": _r2(te - te_yoy) if yoy else None,
        "revenue_delta": _r2(rev - rev_yoy) if yoy else None,
        "expense_ratio_delta_pp": _r2((_safe_float(ratio) - _safe_float(ratio_yoy)) if (ratio is not None and ratio_yoy is not None) else None),
    }

    # Comparative driver branch + contributions
    cp = (comparative_intelligence or {}).get("cost_pressure") or {}
    driver = cp.get("driving_expense_increase_mom") or cp.get("most_inefficient_branch") or {}
    driver_branch = {
        "branch_id": driver.get("branch_id"),
        "branch_name": driver.get("branch_name"),
        "expense_pct_of_revenue": driver.get("expense_pct_of_revenue"),
        "mom_delta_total_expense": driver.get("mom_delta_total_expense"),
    } if driver else None

    contrib_pct = None
    try:
        bid = str((driver or {}).get("branch_id") or "")
        for c in ((comparative_intelligence or {}).get("branch_vs_company") or {}).get("branch_contributions") or []:
            if str(c.get("branch_id") or "") == bid:
                contrib_pct = c.get("branch_contribution_pct_of_company_expense")
                break
    except Exception:
        contrib_pct = None

    # Category driver (company level) — largest absolute category delta MoM
    cat_driver = _top_category_delta(latest, prev) if prev else None

    # Root cause classification
    rc_type = _classify_root_cause(
        expense_delta=float(mom["expense_delta"] or 0),
        revenue_delta=float(mom["revenue_delta"] or 0),
        expense_ratio_delta_pp=mom.get("expense_ratio_delta_pp"),
        driver_branch_expense_ratio=(driver or {}).get("expense_pct_of_revenue"),
    )

    # Link decisions (top 3) + anomalies ids
    top_decisions = sorted(
        expense_decisions_v2 or [],
        key=lambda d: (
            {"high": 0, "medium": 1, "low": 2}.get(str(d.get("priority") or "medium"), 1),
            -_safe_float((d.get("expected_financial_impact") or {}).get("estimated_monthly_savings")),
            str(d.get("decision_id") or ""),
        ),
    )[:3]

    anomaly_ids = sorted(
        [str(a.get("anomaly_id")) for a in (anomalies or []) if isinstance(a, dict) and a.get("anomaly_id")]
    )[:8]

    # Compose deterministic narrative chain (structured)
    chain = []
    chain.append(
        f"Expenses changed by {mom['expense_delta']} MoM while revenue changed by {mom['revenue_delta']}."
    )
    if driver_branch and driver_branch.get("branch_name"):
        chain.append(
            f"Main pressure signal is {driver_branch['branch_name']} (contribution {contrib_pct}%)."
            if contrib_pct is not None
            else f"Main pressure signal is {driver_branch['branch_name']}."
        )
    if cat_driver and cat_driver.get("category"):
        chain.append(f"Primary category driver (MoM) is {cat_driver['category']} (delta {cat_driver['delta']}).")
    if top_decisions:
        chain.append(f"Recommended action: {top_decisions[0].get('title')}.")

    return {
        "available": True,
        "scope": {"type": "company", "id": company_id, "name": company_name},
        "currency": currency,
        "what_changed": {
            "period": period,
            "latest": {
                "revenue": _r2(rev),
                "total_expense": _r2(te),
                "expense_pct_of_revenue": _r2(ratio),
            },
            "mom": mom,
            "yoy": yoy_d,
        },
        "why": {
            "links": {
                "expense_vs_revenue": {
                    "mom_expense_delta": mom["expense_delta"],
                    "mom_revenue_delta": mom["revenue_delta"],
                    "expense_ratio_delta_pp": mom.get("expense_ratio_delta_pp"),
                },
                "category_driver_mom": cat_driver,
                "branch_driver": {
                    **(driver_branch or {}),
                    "contribution_pct_of_company_expense": contrib_pct,
                }
                if driver_branch
                else None,
            }
        },
        "root_causes": {
            "classification": rc_type,
            "explainable_rules": {
                "structural_inefficiency_if_branch_ratio_ge_90": True,
                "revenue_driven_if_revenue_down_and_expenses_not_down": True,
                "cost_driven_if_expenses_up_and_revenue_flat_or_down": True,
                "mix_effect_default": True,
            },
        },
        "linked_drivers": {
            "anomaly_ids": anomaly_ids,
            "comparative_signals": {
                "driver_branch_id": (driver_branch or {}).get("branch_id") if driver_branch else None,
                "most_inefficient_branch_id": ((cp.get("most_inefficient_branch") or {}).get("branch_id") if isinstance(cp, dict) else None),
            },
            "decision_ids": [str(d.get("decision_id")) for d in top_decisions if d.get("decision_id")],
        },
        "causal_chain": chain,
    }

