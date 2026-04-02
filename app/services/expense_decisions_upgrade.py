"""
expense_decisions_upgrade.py — Phase 5 Expense Decisions Upgrade

Produces additive, more actionable expense decisions for:
  - company level
  - branch level

Constraints:
  - Reuse statement-derived expense bundle outputs (expense_intelligence_engine).
  - Do NOT break or change existing `expense_decisions` output; this emits `expense_decisions_v2`.
  - Deterministic outputs only (stable IDs, stable sorting).
  - Conservative, explainable financial impact estimates.
  - Operational, specific action steps (category-aware).
"""

from __future__ import annotations

import hashlib
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


def _stable_id(*parts: str) -> str:
    s = "|".join(str(p or "") for p in parts)
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]
    return f"expd_{h}"


def _latest_row(bundle: dict) -> Optional[dict]:
    rows = ((bundle or {}).get("expense_analysis") or {}).get("by_period") or []
    return rows[-1] if rows else None


def _prev_row(bundle: dict) -> Optional[dict]:
    rows = ((bundle or {}).get("expense_analysis") or {}).get("by_period") or []
    return rows[-2] if len(rows) >= 2 else None


def _baseline_total_expense(bundle: dict) -> Optional[float]:
    """
    Conservative baseline: previous period total_expense if present, else None.
    """
    prev = _prev_row(bundle)
    if not prev:
        return None
    return _r2(prev.get("total_expense"))


def _top_category(latest: dict) -> Optional[tuple[str, float]]:
    cats = (latest or {}).get("categories") or {}
    if not isinstance(cats, dict) or not cats:
        return None
    k, v = sorted(((str(k), _safe_float(v)) for k, v in cats.items()), key=lambda kv: (-kv[1], kv[0]))[0]
    return k, float(v)


_CAPTURE_RATE: dict[str, float] = {
    # Conservative capture assumptions (monthly), explainable and stable
    "marketing": 0.18,
    "utilities": 0.12,
    "logistics": 0.10,
    "other": 0.10,
    "rent": 0.06,
    "payroll": 0.05,
}


def _capture_rate_for(category: Optional[str]) -> float:
    if not category:
        return 0.08
    return float(_CAPTURE_RATE.get(category, 0.08))


def _operational_steps_for(category: Optional[str], where_name: str) -> list[str]:
    """
    Specific, operational steps. Kept deterministic and category-aware.
    """
    c = (category or "").lower()
    if c == "payroll":
        return [
            f"Run a 14-day rota audit for {where_name}: overtime, idle time, and peak-hour coverage.",
            "Freeze non-critical hiring for 30 days; backfill only revenue-critical roles.",
            "Shift to demand-based scheduling (align staffing hours to sales peaks).",
            "Renegotiate temporary labor / contractor rates with a target reduction band (3–5%).",
        ]
    if c == "rent":
        return [
            f"Review {where_name} lease terms and service charges; request a rent review or concessions at renewal.",
            "Audit facilities invoices (cleaning, security, maintenance) for duplicates and non-contracted items.",
            "Implement energy and space-usage controls (closing hours, equipment shutdown checklist).",
        ]
    if c == "logistics":
        return [
            f"Re-price top 10 lanes/vendors for {where_name} and request a 3-quote benchmark within 7 days.",
            "Introduce route batching and minimum-load rules to reduce partial shipments.",
            "Enforce purchase order controls: no expedited shipping without approval.",
        ]
    if c == "utilities":
        return [
            f"Validate {where_name} utility meters and tariffs; correct any wrong tariff class.",
            "Implement an immediate consumption checklist (AC setpoints, lighting schedules, equipment shutdown).",
            "Negotiate telecom/internet bundles; remove unused lines and services.",
        ]
    if c == "marketing":
        return [
            f"Pause low-ROI campaigns for {where_name} for 14 days; keep only campaigns with tracked conversion.",
            "Set weekly spend caps per channel and require CPA/ROAS reporting before increases.",
            "Renegotiate agency/production retainers; switch to performance-based components where possible.",
        ]
    # other / unknown
    return [
        f"Freeze discretionary spend in {where_name} for 14 days; require approval for non-essential purchases.",
        "Audit the top 15 expense accounts by value; tag each as contractual vs discretionary.",
        "Renegotiate top 5 vendor contracts; target 5–10% reduction where spend is non-core.",
        "Implement PO controls: 2-step approval for new vendors and above-threshold invoices.",
    ]


def _impact_block(
    *,
    currency: str,
    latest_total_expense: float,
    baseline_total_expense: Optional[float],
    category: Optional[str],
    reason: str,
) -> dict[str, Any]:
    """
    Conservative, explainable impact estimate:
      savings = max(0, latest - baseline) * capture_rate
    If no baseline, estimate is zero (explicitly explain why).
    """
    capture = _capture_rate_for(category)
    if baseline_total_expense is None:
        return {
            "currency": currency,
            "estimated_monthly_savings": 0.0,
            "estimated_annual_savings": 0.0,
            "assumptions": [
                "Baseline period not available; impact estimate withheld (set to 0).",
                f"Capture rate (conservative) would be {round(capture*100,1)}% if baseline exists.",
                reason,
            ],
        }
    excess = max(0.0, float(latest_total_expense) - float(baseline_total_expense))
    savings = excess * capture
    return {
        "currency": currency,
        "estimated_monthly_savings": _r2(savings) or 0.0,
        "estimated_annual_savings": _r2(savings * 12) or 0.0,
        "assumptions": [
            f"Baseline = previous period total expense ({_r2(baseline_total_expense)}).",
            f"Excess spend = max(0, latest - baseline) = {_r2(excess)}.",
            f"Capture rate (conservative) = {round(capture*100,1)}% (category={category or 'mixed'}).",
            reason,
        ],
    }


def _priority_from(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def build_company_expense_decisions_v2(
    *,
    company_id: str,
    company_name: str,
    currency: str,
    company_bundle: dict,
    comparative_intelligence: dict | None,
    lang: str = "en",
) -> list[dict[str, Any]]:
    """
    Company-level decisions can be emitted even when anomalies are empty, as long as
    comparative pressure is strong (deterministic).
    """
    _ = lang  # reserved for future localization; keep deterministic EN outputs for now

    latest = _latest_row(company_bundle)
    if not latest:
        return []

    anomalies = (company_bundle or {}).get("expense_anomalies") or []
    comp = comparative_intelligence or {}
    cp = (comp.get("cost_pressure") or {}) if isinstance(comp, dict) else {}
    driver = cp.get("driving_expense_increase_mom") or cp.get("most_inefficient_branch")

    decisions: list[dict[str, Any]] = []

    # Decision 1: address the branch driving cost pressure (MoM) or inefficiency
    if driver:
        bname = str(driver.get("branch_name") or "")
        bid = str(driver.get("branch_id") or "")
        branch_contrib = None
        try:
            contribs = (comp.get("branch_vs_company") or {}).get("branch_contributions") or []
            for c in contribs:
                if str(c.get("branch_id")) == bid:
                    branch_contrib = c.get("branch_contribution_pct_of_company_expense")
                    break
        except Exception:
            branch_contrib = None

        # abnormal category driver for that branch (if available)
        abnormal_branch = None
        try:
            ab = (comp.get("category_comparison") or {}).get("most_abnormal_category_distribution")
            if ab and str(ab.get("branch_id")) == bid:
                abnormal_branch = ab
        except Exception:
            abnormal_branch = None

        title = f"Contain cost pressure in {bname} (branch-level expense control)"
        rationale = (
            f"{bname} is a primary cost-pressure signal for the company. "
            f"Contribution to company expense: {branch_contrib}%." if branch_contrib is not None else
            f"{bname} is a primary cost-pressure signal for the company."
        )
        if abnormal_branch and abnormal_branch.get("distribution_distance_l1") is not None:
            rationale += f" Category mix is atypical (distribution distance {abnormal_branch.get('distribution_distance_l1')})."

        action_steps = [
            f"Run a 7-day spend triage in {bname}: stop/approve all non-essential invoices above threshold.",
            "Audit top 20 expense accounts driving the increase; assign owner + target reduction per account.",
            "Renegotiate the top 5 vendors by spend; request revised quotes within 10 business days.",
            "Implement a weekly cost-control cadence (branch GM + ops + finance): variance review and approvals.",
        ]

        score = 60.0
        if branch_contrib is not None:
            score += min(25.0, float(branch_contrib) * 0.4)
        if driver.get("expense_pct_of_revenue") is not None and float(driver.get("expense_pct_of_revenue") or 0) >= 85:
            score += 15.0

        decisions.append(
            {
                "decision_id": _stable_id("company", company_id, str(latest.get("period") or ""), "contain_branch_pressure", bid),
                "scope": {"type": "company", "id": company_id, "name": company_name},
                "where": {"branch_id": bid, "branch_name": bname},
                "title": title,
                "rationale": rationale,
                "action": {"steps": action_steps, "owner": "operations", "time_horizon": "immediate"},
                "priority": _priority_from(score),
                "expected_financial_impact": {
                    "currency": currency,
                    "estimated_monthly_savings": 0.0,
                    "estimated_annual_savings": 0.0,
                    "assumptions": [
                        "Company-level decision is branch-targeting; savings is estimated at branch scope (see branch decisions)."
                    ],
                },
                "linked_drivers": {
                    "anomaly_ids": [a.get("anomaly_id") for a in anomalies if isinstance(a, dict) and a.get("anomaly_id")][:5],
                    "categories": [],
                    "metrics": ["total_expense", "expense_pct_of_revenue", "mom_delta_total_expense", "branch_contribution_pct_of_company_expense"],
                },
            }
        )

    # Decision 2: if company expense ratio is high, enforce cost governance even without anomalies
    ratio = latest.get("expense_pct_of_revenue")
    if ratio is not None and float(ratio or 0) >= 75:
        te = _safe_float(latest.get("total_expense"))
        baseline = _baseline_total_expense(company_bundle)
        title = "Enforce company-wide discretionary spend controls (30-day)"
        rationale = f"Expense ratio is elevated at {round(float(ratio),2)}% in {latest.get('period')}."
        steps = [
            "Set approval thresholds for discretionary spend (marketing, admin, non-critical services).",
            "Introduce a purchase order (PO) requirement for new vendors and above-threshold invoices.",
            "Run a vendor consolidation exercise (top 20 vendors) and renegotiate pricing bands.",
            "Weekly variance review: compare actual spend vs baseline and publish accountability owners.",
        ]
        decisions.append(
            {
                "decision_id": _stable_id("company", company_id, str(latest.get("period") or ""), "company_governance"),
                "scope": {"type": "company", "id": company_id, "name": company_name},
                "where": {"branch_id": None, "branch_name": None},
                "title": title,
                "rationale": rationale,
                "action": {"steps": steps, "owner": "cfo", "time_horizon": "short"},
                "priority": "high" if float(ratio or 0) >= 85 else "medium",
                "expected_financial_impact": _impact_block(
                    currency=currency,
                    latest_total_expense=te,
                    baseline_total_expense=baseline,
                    category=None,
                    reason="Company-level capture assumes governance reduces excess spend vs prior period.",
                ),
                "linked_drivers": {
                    "anomaly_ids": [a.get("anomaly_id") for a in anomalies if isinstance(a, dict) and a.get("anomaly_id")][:5],
                    "categories": [],
                    "metrics": ["expense_pct_of_revenue", "total_expense"],
                },
            }
        )

    # Deterministic ordering
    decisions_sorted = sorted(
        decisions,
        key=lambda d: (
            {"high": 0, "medium": 1, "low": 2}.get(d.get("priority", "medium"), 1),
            -(float(d.get("expected_financial_impact", {}).get("estimated_monthly_savings") or 0.0)),
            str(d.get("title") or ""),
            str(d.get("decision_id") or ""),
        ),
    )
    return decisions_sorted[:8]


def build_branch_expense_decisions_v2(
    *,
    branch_id: str,
    branch_name: str,
    company_id: str,
    company_name: str,
    currency: str,
    branch_bundle: dict,
    comparative_intelligence: dict | None,
    lang: str = "en",
) -> list[dict[str, Any]]:
    """
    Branch-level decisions must consider:
      - inefficiency
      - contribution to company expense
      - abnormal category driver
    If anomalies are empty, still emit decisions when comparative pressure is strong.
    """
    _ = lang
    latest = _latest_row(branch_bundle)
    if not latest:
        return []

    period = str(latest.get("period") or "")
    ratio = _r2(latest.get("expense_pct_of_revenue"))
    te = _safe_float(latest.get("total_expense"))
    baseline = _baseline_total_expense(branch_bundle)
    top_cat = _top_category(latest)
    top_cat_key = top_cat[0] if top_cat else None

    anomalies = (branch_bundle or {}).get("expense_anomalies") or []

    # comparative signals for this branch
    comp = comparative_intelligence or {}
    contrib_pct = None
    ineff_rank = None
    abnormal_dist = None
    try:
        for c in ((comp.get("branch_vs_company") or {}).get("branch_contributions") or []):
            if str(c.get("branch_id") or "") == branch_id:
                contrib_pct = c.get("branch_contribution_pct_of_company_expense")
                break
        desc = ((comp.get("efficiency_ranking") or {}).get("by_expense_pct_of_revenue_desc") or [])
        for i, row in enumerate(desc):
            if str(row.get("branch_id") or "") == branch_id:
                ineff_rank = i + 1
                break
        for row in ((comp.get("category_comparison") or {}).get("all_distribution_distances") or []):
            if str(row.get("branch_id") or "") == branch_id:
                abnormal_dist = row.get("distribution_distance_l1")
                break
    except Exception:
        pass

    decisions: list[dict[str, Any]] = []

    # Decision A: fix inefficiency (high expense ratio)
    ineff_pressure = (ratio is not None and float(ratio) >= 80) or (ineff_rank == 1)
    if ineff_pressure:
        title = f"Reduce expense ratio in {branch_name} (targeted cost actions)"
        rationale = []
        if ratio is not None:
            rationale.append(f"Expense ratio is {ratio}% in {period}.")
        if contrib_pct is not None:
            rationale.append(f"Branch contributes {contrib_pct}% of company total expense.")
        if abnormal_dist is not None:
            rationale.append(f"Category mix deviation is {abnormal_dist} (vs company).")
        rationale_s = " ".join(rationale) if rationale else "Branch shows structural cost pressure vs company."

        steps = _operational_steps_for(top_cat_key, branch_name)
        score = 55.0
        if ratio is not None:
            score += min(25.0, max(0.0, float(ratio) - 70.0))
        if contrib_pct is not None:
            score += min(20.0, float(contrib_pct) * 0.3)
        if abnormal_dist is not None:
            score += min(10.0, float(abnormal_dist) * 20.0)

        decisions.append(
            {
                "decision_id": _stable_id("branch", branch_id, period, "reduce_ratio", top_cat_key or "mixed"),
                "scope": {"type": "branch", "id": branch_id, "name": branch_name},
                "where": {"branch_id": branch_id, "branch_name": branch_name},
                "title": title,
                "rationale": rationale_s,
                "action": {"steps": steps, "owner": "branch_manager", "time_horizon": "immediate"},
                "priority": _priority_from(score),
                "expected_financial_impact": _impact_block(
                    currency=currency,
                    latest_total_expense=te,
                    baseline_total_expense=baseline,
                    category=top_cat_key,
                    reason="Estimate targets a small capture of excess spend driven by the dominant cost category.",
                ),
                "linked_drivers": {
                    "anomaly_ids": [a.get("anomaly_id") for a in anomalies if isinstance(a, dict) and a.get("anomaly_id")][:5],
                    "categories": [top_cat_key] if top_cat_key else [],
                    "metrics": ["expense_pct_of_revenue", "total_expense", "branch_contribution_pct_of_company_expense"],
                },
            }
        )

    # Decision B: contain MoM total expense increase even if anomalies list is empty
    prev = _prev_row(branch_bundle)
    mom_delta = None
    if prev:
        mom_delta = _r2(te - _safe_float(prev.get("total_expense")))
    if mom_delta is not None and mom_delta > 0:
        score = 40.0 + min(30.0, float(mom_delta) / 10000.0)  # scale conservatively
        if contrib_pct is not None:
            score += min(15.0, float(contrib_pct) * 0.2)
        title = f"Stop month-over-month expense creep in {branch_name}"
        rationale = f"Total expense increased by {mom_delta} vs previous period ({period})."
        steps = [
            f"Identify the top 10 accounts driving the increase in {branch_name} and assign an owner per account.",
            "Set a 30-day spend cap per cost category; require approvals for exceptions.",
            "Renegotiate any variable-rate vendor items that increased this month (quotes within 10 days).",
        ]
        decisions.append(
            {
                "decision_id": _stable_id("branch", branch_id, period, "stop_mom_creep"),
                "scope": {"type": "branch", "id": branch_id, "name": branch_name},
                "where": {"branch_id": branch_id, "branch_name": branch_name},
                "title": title,
                "rationale": rationale,
                "action": {"steps": steps, "owner": "operations", "time_horizon": "short"},
                "priority": _priority_from(score),
                "expected_financial_impact": _impact_block(
                    currency=currency,
                    latest_total_expense=te,
                    baseline_total_expense=_r2(te - float(mom_delta)),
                    category=top_cat_key,
                    reason="Estimate assumes a conservative capture of the MoM increase through immediate controls.",
                ),
                "linked_drivers": {
                    "anomaly_ids": [a.get("anomaly_id") for a in anomalies if isinstance(a, dict) and a.get("anomaly_id")][:5],
                    "categories": [top_cat_key] if top_cat_key else [],
                    "metrics": ["mom_delta_total_expense", "total_expense"],
                },
            }
        )

    # Deterministic ordering
    decisions_sorted = sorted(
        decisions,
        key=lambda d: (
            {"high": 0, "medium": 1, "low": 2}.get(d.get("priority", "medium"), 1),
            -(float(d.get("expected_financial_impact", {}).get("estimated_monthly_savings") or 0.0)),
            str(d.get("title") or ""),
            str(d.get("decision_id") or ""),
        ),
    )
    return decisions_sorted[:8]

