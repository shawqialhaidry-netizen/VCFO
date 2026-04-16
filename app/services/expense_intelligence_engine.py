"""
expense_intelligence_engine.py — Phase 1 Expense Intelligence Engine

Analyst-grade expense intelligence (backend only).

Input: statement dicts in the same shape as `financial_statements.statements_to_dict()`.
Output keys:
  - expense_analysis
  - expense_anomalies
  - expense_decisions
  - expense_explanation

Constraints:
  - No DB access, no UI/API changes.
  - No recalculation from raw debit/credit; use statement totals only.
  - Reuse `expense_engine` grouping logic for categorization (no duplicate classifier).
"""

from __future__ import annotations

import re
import statistics
import uuid
from collections import defaultdict
from typing import Any, Optional

from app.services.expense_engine import THRESHOLD_SOURCE, THRESHOLDS, _build_groups, _mom, _pct

_PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")

# Phase 1 normalized buckets (stable, small vocabulary)
_NORM_CATS: tuple[str, ...] = ("payroll", "rent", "logistics", "utilities", "marketing", "other")

_MARKETING_KWS = (
    "marketing",
    "advert",
    "advertising",
    "promotion",
    "promotions",
    "advertisement",
    "brand",
    "sponsorship",
    "lead generation",
)
_UTIL_KWS = (
    "electricity",
    "water",
    "internet",
    "utilities",
    "utility",
    "communication",
)


def _r2(x: Any) -> Optional[float]:
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


def _parse_period(p: str) -> Optional[tuple[int, int]]:
    if not p or not isinstance(p, str):
        return None
    m = _PERIOD_RE.match(p.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _yoy_period(y: int, mo: int) -> str:
    return f"{y - 1}-{mo:02d}"


def _sorted_statements(stmts: list[dict]) -> list[dict]:
    return sorted(stmts, key=lambda s: (s.get("period") or ""))


def _revenue(is_: dict) -> float:
    return float((is_.get("revenue") or {}).get("total") or 0)


def _totals_from_is(is_: dict) -> tuple[float, float, float, float, float]:
    """
    Returns:
      (cogs, opex_expenses_total, tax_total, unclassified_total, total_expense)

    `total_expense` matches the existing cost-load definition:
      total_expense = cogs.total + expenses.total + unclassified_pnl_debits.total
    Tax is excluded by design.
    """
    cogs = float((is_.get("cogs") or {}).get("total") or 0)
    opex = float((is_.get("expenses") or {}).get("total") or 0)
    tax = float((is_.get("tax") or {}).get("total") or 0)
    uncl = float((is_.get("unclassified_pnl_debits") or {}).get("total") or 0)
    total = cogs + opex + uncl
    return cogs, opex, tax, uncl, total


def _median(xs: list[float]) -> Optional[float]:
    vals = [float(x) for x in xs if x is not None and x == x]
    if not vals:
        return None
    return float(statistics.median(vals))


def _infer_norm_cat(raw_cat: str, group_obj: dict) -> str:
    """
    Map `expense_engine` categories into Phase 1 normalized buckets.

    We do not reclassify raw rows; we only remap group keys and use `top_items`
    for lightweight splitting (rent vs utilities, admin vs marketing).
    """
    if raw_cat == "payroll":
        return "payroll"
    if raw_cat == "logistics":
        return "logistics"
    if raw_cat == "rent_facilities":
        top_items = group_obj.get("top_items") or []
        text = " ".join(str(i.get("account_name", "") or "").lower() for i in top_items)
        return "utilities" if any(kw in text for kw in _UTIL_KWS) else "rent"
    if raw_cat == "admin_other":
        top_items = group_obj.get("top_items") or []
        text = " ".join(str(i.get("account_name", "") or "").lower() for i in top_items)
        return "marketing" if any(kw in text for kw in _MARKETING_KWS) else "other"

    # Everything else (cogs, fuel, maintenance, depreciation, etc.) -> other for Phase 1.
    return "other"


def _normalize_categories_for_stmt(stmt: dict) -> dict[str, float]:
    """
    Normalized category totals that reconcile to `total_expense`.

    Reconciliation steps (no financial recomputation):
      1) start from `_build_groups` totals (which may include tax in admin_other)
      2) subtract `tax_total` from admin_other
      3) add `unclassified_pnl_debits` into admin_other (treated as other)
      4) backfill missing cogs/opex sections if item arrays are absent
      5) reconcile any residual diff into admin_other
      6) map to Phase 1 normalized buckets
    """
    is_ = stmt.get("income_statement") or {}
    rev = _revenue(is_)
    cogs_total, opex_total, tax_total, uncl_total, total_exp = _totals_from_is(is_)

    groups = _build_groups(stmt, rev if rev else None) or {}
    raw_amounts: dict[str, float] = {ck: float(g.get("current") or 0) for ck, g in groups.items()}

    # Align admin_other with total_expense (exclude tax, include unclassified)
    admin_raw = float(raw_amounts.get("admin_other") or 0)
    raw_amounts["admin_other"] = max(0.0, admin_raw - tax_total) + uncl_total

    # Ensure cogs appears if cogs.total exists but items were absent
    if cogs_total > 0 and float(raw_amounts.get("cogs") or 0) <= 1e-6:
        raw_amounts["cogs"] = cogs_total

    # If expenses.total exists but no expense categories were produced, backfill to admin_other
    non_cogs_sum = sum(float(v or 0) for k, v in raw_amounts.items() if k != "cogs")
    if opex_total > 0 and non_cogs_sum <= 1e-6:
        raw_amounts["admin_other"] = float(raw_amounts.get("admin_other") or 0) + opex_total

    # Reconcile sums to total_expense
    raw_total = sum(float(v or 0) for v in raw_amounts.values())
    diff = total_exp - raw_total
    if abs(diff) > 1e-3:
        raw_amounts["admin_other"] = float(raw_amounts.get("admin_other") or 0) + diff

    normalized: defaultdict[str, float] = defaultdict(float)
    for raw_cat, amt in raw_amounts.items():
        if amt is None:
            continue
        norm = _infer_norm_cat(raw_cat, groups.get(raw_cat, {}) or {})
        normalized[norm] += float(amt)

    cleaned = {
        k: float(v)
        for k, v in normalized.items()
        if k in _NORM_CATS and abs(float(v)) > 1e-6
    }
    return cleaned


def _build_by_period_rows(stmts: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for stmt in stmts:
        p = stmt.get("period") or ""
        parsed = _parse_period(p)
        year, month = (parsed[0], parsed[1]) if parsed else (None, None)

        is_ = stmt.get("income_statement") or {}
        rev = _revenue(is_)
        cogs_total, opex_total, _tax_total, uncl_total, total_exp = _totals_from_is(is_)
        cats = _normalize_categories_for_stmt(stmt)

        rows.append(
            {
                "period": p,
                "year": year,
                "month": month,
                "revenue": _r2(rev),
                "cogs": _r2(cogs_total),
                "operating_expenses": _r2(opex_total),
                "unclassified_pnl_debits": _r2(uncl_total),
                "total_expense": _r2(total_exp),
                "expense_pct_of_revenue": _pct(total_exp, rev) if rev else None,
                "categories": {k: _r2(v) for k, v in sorted(cats.items())},
            }
        )
    return rows


def _rollup_by_year(rows: list[dict]) -> list[dict]:
    by_y: dict[int, dict[str, Any]] = {}
    for r in rows:
        y = r.get("year")
        if y is None:
            continue
        slot = by_y.setdefault(
            y,
            {
                "year": y,
                "revenue": 0.0,
                "total_expense": 0.0,
                "cogs": 0.0,
                "operating_expenses": 0.0,
                "unclassified_pnl_debits": 0.0,
                "categories": defaultdict(float),
            },
        )
        slot["revenue"] += float(r.get("revenue") or 0)
        slot["total_expense"] += float(r.get("total_expense") or 0)
        slot["cogs"] += float(r.get("cogs") or 0)
        slot["operating_expenses"] += float(r.get("operating_expenses") or 0)
        slot["unclassified_pnl_debits"] += float(r.get("unclassified_pnl_debits") or 0)
        for ck, amt in (r.get("categories") or {}).items():
            slot["categories"][ck] += float(amt or 0)

    out: list[dict] = []
    for y in sorted(by_y.keys()):
        s = by_y[y]
        rev = s["revenue"]
        te = s["total_expense"]
        out.append(
            {
                "year": y,
                "revenue": _r2(rev),
                "total_expense": _r2(te),
                "cogs": _r2(s["cogs"]),
                "operating_expenses": _r2(s["operating_expenses"]),
                "unclassified_pnl_debits": _r2(s["unclassified_pnl_debits"]),
                "expense_pct_of_revenue": _pct(te, rev) if rev else None,
                "categories": {k: _r2(v) for k, v in sorted(s["categories"].items())},
            }
        )
    return out


def _category_timeseries(rows: list[dict]) -> dict[str, list[dict]]:
    ts: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        p = r.get("period") or ""
        rev = float(r.get("revenue") or 0)
        for ck, amt in (r.get("categories") or {}).items():
            amt_f = float(amt or 0)
            ts[ck].append(
                {
                    "period": p,
                    "amount": _r2(amt_f),
                    "pct_of_revenue": _pct(amt_f, rev) if rev else None,
                }
            )
    return dict(ts)


def _branch_breakdown(
    branch_period_statements: dict[str, list[dict]],
    branch_labels: dict[str, str] | None,
) -> list[dict]:
    out: list[dict] = []
    for bid, bstmts in branch_period_statements.items():
        if not bstmts:
            continue
        latest = _sorted_statements(bstmts)[-1]
        p = latest.get("period") or ""

        is_ = latest.get("income_statement") or {}
        rev = _revenue(is_)
        cogs_total, opex_total, _tax_total, uncl_total, total_exp = _totals_from_is(is_)
        cats = _normalize_categories_for_stmt(latest)

        out.append(
            {
                "branch_id": bid,
                "branch_name": (branch_labels or {}).get(bid) or bid,
                "latest_period": p,
                "revenue": _r2(rev),
                "total_expense": _r2(total_exp),
                "cogs": _r2(cogs_total),
                "operating_expenses": _r2(opex_total),
                "unclassified_pnl_debits": _r2(uncl_total),
                "expense_pct_of_revenue": _pct(total_exp, rev) if rev else None,
                "categories": {k: _r2(v) for k, v in sorted(cats.items())},
            }
        )
    out.sort(key=lambda x: x.get("total_expense") or 0, reverse=True)
    return out


def _compute_trends(rows: list[dict]) -> dict[str, Any]:
    if not rows:
        return {"mom": None, "yoy": None, "expense_pct_of_revenue_series": []}

    last = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else None

    mom = None
    if prev:
        te_l = float(last.get("total_expense") or 0)
        te_p = float(prev.get("total_expense") or 0)
        rev_l = float(last.get("revenue") or 0)
        rev_p = float(prev.get("revenue") or 0)
        epr_l = last.get("expense_pct_of_revenue")
        epr_p = prev.get("expense_pct_of_revenue")
        mom = {
            "from_period": prev.get("period"),
            "to_period": last.get("period"),
            "total_expense_pct": _mom(te_l, te_p),
            "revenue_pct": _mom(rev_l, rev_p),
            "expense_pct_of_revenue_pp": _r2(float(epr_l) - float(epr_p))
            if epr_l is not None and epr_p is not None
            else None,
        }

    yoy = None
    parsed = _parse_period(last.get("period") or "")
    if parsed:
        y, m = parsed
        want = _yoy_period(y, m)
        match = next((r for r in rows if r.get("period") == want), None)
        if match:
            te_l = float(last.get("total_expense") or 0)
            te_y = float(match.get("total_expense") or 0)
            rev_l = float(last.get("revenue") or 0)
            rev_y = float(match.get("revenue") or 0)
            epr_l = last.get("expense_pct_of_revenue")
            epr_y = match.get("expense_pct_of_revenue")
            yoy = {
                "from_period": match.get("period"),
                "to_period": last.get("period"),
                "total_expense_pct": _mom(te_l, te_y),
                "revenue_pct": _mom(rev_l, rev_y),
                "expense_pct_of_revenue_pp": _r2(float(epr_l) - float(epr_y))
                if epr_l is not None and epr_y is not None
                else None,
            }

    series = [
        {"period": r.get("period"), "expense_pct_of_revenue": r.get("expense_pct_of_revenue")}
        for r in rows
    ]
    return {"mom": mom, "yoy": yoy, "expense_pct_of_revenue_series": series}


def _severity_for_score(score: float) -> str:
    if score >= 40.0:
        return "high"
    if score >= 20.0:
        return "medium"
    return "low"


def _detect_anomalies(rows: list[dict], lang: str) -> list[dict]:
    if not rows:
        return []

    last = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else None
    prior_rows = rows[:-1]

    eps = 1e-6
    anomalies: list[dict] = []

    last_cats = {k: float(v or 0) for k, v in (last.get("categories") or {}).items()}
    all_cats: set[str] = set(last_cats.keys())
    for r in prior_rows:
        all_cats |= set((r.get("categories") or {}).keys())
    if prev:
        all_cats |= set((prev.get("categories") or {}).keys())

    # 1) Category spike vs median baseline (>=15%) and 2) new category appearance
    for cat in sorted(all_cats):
        obs = float(last_cats.get(cat) or 0)
        hist = [float((r.get("categories") or {}).get(cat) or 0) for r in prior_rows]
        if len(hist) < 2:
            continue
        base = _median(hist)
        prior_max = max(hist) if hist else 0.0
        if base is None:
            continue

        if obs > eps and prior_max <= eps:
            sev = "high" if obs / max(float(last.get("total_expense") or 0), eps) >= 0.15 else "medium"
            anomalies.append(
                {
                    "anomaly_id": f"exp_newcat_{cat}_{last.get('period')}",
                    "signal": "new_category_appeared",
                    "severity": sev,
                    "baseline_method": "zero_prior_periods",
                    "baseline_value": 0.0,
                    "observed": _r2(obs),
                    "deviation_pct": 100.0,
                    "short_explanation": f"New category '{cat}' appeared with material spend in {last.get('period')}.",
                }
            )
            continue

        if base < eps:
            continue
        dev_pct = _mom(obs, base)
        if dev_pct is None or dev_pct < 15.0:
            continue
        sev = _severity_for_score(abs(dev_pct))
        anomalies.append(
            {
                "anomaly_id": f"exp_cat_spike_{cat}_{last.get('period')}",
                "signal": "category_spike_vs_median",
                "severity": sev,
                "baseline_method": "median_prior_periods",
                "baseline_value": _r2(base),
                "observed": _r2(obs),
                "deviation_pct": _r2(dev_pct),
                "short_explanation": f"'{cat}' is {dev_pct:+.1f}% above the prior median in {last.get('period')}.",
            }
        )

    # 3) Total expense growing faster than revenue (MoM)
    if prev:
        te_l = float(last.get("total_expense") or 0)
        te_p = float(prev.get("total_expense") or 0)
        rev_l = float(last.get("revenue") or 0)
        rev_p = float(prev.get("revenue") or 0)
        te_mom = _mom(te_l, te_p)
        rev_mom = _mom(rev_l, rev_p) if rev_p else None
        if te_mom is not None and te_mom >= 10.0 and (rev_mom is None or te_mom > rev_mom + 3.0):
            baseline_total = te_p * (1.0 + (rev_mom or 0) / 100.0) if rev_mom is not None else te_p
            deviation_amount = te_l - baseline_total
            deviation_pct = (deviation_amount / baseline_total) * 100.0 if abs(baseline_total) > eps else None
            anomalies.append(
                {
                    "anomaly_id": f"exp_total_outpaced_{last.get('period')}",
                    "signal": "total_expense_outpaced_revenue",
                    "severity": "high" if te_mom >= 22.0 else "medium",
                    "baseline_method": "revenue_momentum_implied_total_expense",
                    "baseline_value": _r2(baseline_total),
                    "observed": _r2(te_l),
                    "deviation_pct": _r2(deviation_pct),
                    "short_explanation": "Total expense growth outpaced revenue momentum.",
                }
            )

        # 4) Expense-to-revenue ratio deterioration (pp)
        epr_l = last.get("expense_pct_of_revenue")
        epr_p = prev.get("expense_pct_of_revenue")
        if epr_l is not None and epr_p is not None:
            delta_pp = float(epr_l) - float(epr_p)
            if delta_pp >= 5.0:
                anomalies.append(
                    {
                        "anomaly_id": f"exp_ratio_deterioration_{last.get('period')}",
                        "signal": "expense_ratio_deterioration",
                        "severity": "high" if delta_pp >= 10.0 else "medium",
                        "baseline_method": "prior_period_expense_ratio",
                        "baseline_value": _r2(epr_p),
                        "observed": _r2(epr_l),
                        "deviation_pct": _r2(delta_pp),  # pp
                        "short_explanation": f"Expense-to-revenue worsened by +{delta_pp:.1f}pp.",
                    }
                )

    # 5) Elevated ratio vs internal thresholds
    epr = last.get("expense_pct_of_revenue")
    thr = THRESHOLDS.get("expense_ratio_pct", {})
    if epr is not None and thr:
        warn = float(thr.get("warning", 65))
        crit = float(thr.get("critical", 80))
        if float(epr) >= warn:
            anomalies.append(
                {
                    "anomaly_id": f"exp_ratio_threshold_{last.get('period')}",
                    "signal": "expense_ratio_above_threshold",
                    "severity": "high" if float(epr) >= crit else "medium",
                    "baseline_method": "internal_threshold",
                    "baseline_value": warn,
                    "observed": _r2(epr),
                    "deviation_pct": None,
                    "short_explanation": f"Expense-to-revenue {float(epr):.1f}% exceeds threshold {warn:.1f}%.",
                    "threshold_source": THRESHOLD_SOURCE,
                }
            )

    anomalies.sort(key=lambda a: {"high": 0, "medium": 1, "low": 2}.get(a.get("severity"), 3))
    return anomalies


def _compute_top_movers(last_row: dict, prev_row: dict | None) -> dict[str, list[dict]]:
    if not prev_row:
        return {"increasing": [], "decreasing": []}

    total_l = float(last_row.get("total_expense") or 0)
    total_p = float(prev_row.get("total_expense") or 0)
    net_delta = total_l - total_p

    last_cats = {k: float(v or 0) for k, v in (last_row.get("categories") or {}).items()}
    prev_cats = {k: float(v or 0) for k, v in (prev_row.get("categories") or {}).items()}
    all_cats = set(last_cats.keys()) | set(prev_cats.keys())

    movers: list[dict] = []
    for cat in all_cats:
        c = last_cats.get(cat, 0.0)
        p = prev_cats.get(cat, 0.0)
        abs_change = c - p
        if abs(abs_change) < 1e-6:
            continue
        pct_change = _mom(c, p) if abs(p) > 1e-6 else (100.0 if abs(c) > 1e-6 else None)
        contrib = (abs_change / net_delta) * 100.0 if abs(net_delta) > 1e-6 else None
        movers.append(
            {
                "category": cat,
                "absolute_change": _r2(abs_change),
                "pct_change": _r2(pct_change),
                "contribution_to_total_change_pct": _r2(contrib),
            }
        )

    inc = [m | {"direction": "increasing"} for m in movers if float(m.get("absolute_change") or 0) > 0]
    dec = [m | {"direction": "decreasing"} for m in movers if float(m.get("absolute_change") or 0) < 0]
    inc.sort(key=lambda x: abs(float(x.get("absolute_change") or 0)), reverse=True)
    dec.sort(key=lambda x: abs(float(x.get("absolute_change") or 0)), reverse=True)
    return {"increasing": inc[:3], "decreasing": dec[:3]}


def _build_explanation(rows: list[dict], trends: dict[str, Any], anomalies: list[dict], lang: str) -> dict[str, Any]:
    if not rows:
        return {
            "headline": "",
            "narrative": "",
            "drivers": [],
            "comparison_basis": "none",
            "top_movers": {"increasing": [], "decreasing": []},
        }

    last = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else None
    mom = (trends or {}).get("mom") or {}
    yoy = (trends or {}).get("yoy") or {}

    top_movers = _compute_top_movers(last, prev)

    te_l = last.get("total_expense")
    rev_l = last.get("revenue")
    te_mom = mom.get("total_expense_pct")
    rev_mom = mom.get("revenue_pct")
    ratio_pp = mom.get("expense_pct_of_revenue_pp")

    headline = f"Expense intelligence for {last.get('period')}"
    narrative = [f"In {last.get('period')}, total expense was {te_l} against revenue of {rev_l}."]
    if te_mom is not None:
        narrative.append(f"Expense changed {te_mom:+.1f}% versus the prior period.")
    if rev_mom is not None:
        narrative.append(f"Revenue changed {rev_mom:+.1f}% over the same comparison.")
    if ratio_pp is not None:
        narrative.append(f"The expense-to-revenue ratio moved {ratio_pp:+.1f}pp.")

    if top_movers["increasing"]:
        m = top_movers["increasing"][0]
        narrative.append(f"The main cost increase came from {m['category']} ({m['absolute_change']:+.2f}).")
    if top_movers["decreasing"]:
        m = top_movers["decreasing"][0]
        narrative.append(f"The largest offset came from {m['category']} ({m['absolute_change']:+.2f}).")
    if anomalies:
        narrative.append(f"{len(anomalies)} anomaly signal(s) were flagged and should be validated before the next operating review.")

    if not prev:
        narrative.append("Prior-period comparison is limited because only one period is available in the current window.")

    basis = []
    if prev:
        basis.append("MoM")
    if yoy:
        basis.append("YoY")

    return {
        "headline": headline,
        "narrative": " ".join(narrative),
        "drivers": top_movers["increasing"] + top_movers["decreasing"],
        "comparison_basis": "+".join(basis) if basis else "latest_period_only",
        "top_movers": top_movers,
    }


def _capture_rate_from_severity(sev: str) -> float:
    return {"high": 0.5, "medium": 0.35, "low": 0.25}.get(sev, 0.35)


def _estimate_impact(revenue: float, savings_amount: float | None) -> dict[str, Any]:
    if savings_amount is None:
        return {
            "estimated_monthly_savings": None,
            "estimated_margin_impact_bps": None,
            "estimated_margin_impact_pct": None,
        }
    if revenue <= 0:
        return {
            "estimated_monthly_savings": _r2(savings_amount),
            "estimated_margin_impact_bps": None,
            "estimated_margin_impact_pct": None,
        }
    bps = (float(savings_amount) / float(revenue)) * 10000.0
    pct = (float(savings_amount) / float(revenue)) * 100.0
    return {
        "estimated_monthly_savings": _r2(savings_amount),
        "estimated_margin_impact_bps": _r2(bps),
        "estimated_margin_impact_pct": _r2(pct),
    }


def _build_decisions(anomalies: list[dict], last_row: dict) -> list[dict]:
    if not anomalies:
        return []

    rev = float(last_row.get("revenue") or 0)
    decisions: list[dict] = []

    for an in anomalies[:8]:
        sev = an.get("severity") or "medium"
        capture = _capture_rate_from_severity(sev)
        period = last_row.get("period")
        signal = an.get("signal")
        linked = [an.get("anomaly_id")]

        if signal in ("category_spike_vs_median", "new_category_appeared") and an.get("category"):
            cat = an["category"]
            obs = float(an.get("observed") or 0)
            base = float(an.get("baseline_value") or 0)
            excess = max(0.0, obs - base)
            savings = excess * capture if signal == "category_spike_vs_median" else obs * (capture * 0.8)
            impact = _estimate_impact(rev, savings)
            decisions.append(
                {
                    "decision_id": f"dc_{uuid.uuid4().hex[:10]}",
                    "title": f"Reduce {cat} run-rate in {period}",
                    "rationale": f"{signal}: observed={_r2(obs)} baseline={_r2(base)} deviation={an.get('deviation_pct')}.",
                    "action": f"Cap {cat} spend to remove {_r2(savings)} from monthly run-rate (estimate).",
                    "expected_financial_impact": impact,
                    "priority": sev,
                    "linked_anomaly_ids": linked,
                }
            )

        if signal == "total_expense_outpaced_revenue":
            obs_total = float(an.get("observed") or 0)
            base_total = float(an.get("baseline_value") or 0)
            excess = max(0.0, obs_total - base_total)
            savings = excess * capture
            impact = _estimate_impact(rev, savings)
            decisions.append(
                {
                    "decision_id": f"dc_{uuid.uuid4().hex[:10]}",
                    "title": f"Bring total expense back in line with revenue momentum ({period})",
                    "rationale": f"Observed={_r2(obs_total)} baseline={_r2(base_total)} excess={_r2(excess)}.",
                    "action": f"Freeze discretionary spend and target {_r2(savings)} in reductions (estimate).",
                    "expected_financial_impact": impact,
                    "priority": sev,
                    "linked_anomaly_ids": linked,
                }
            )

    # Deduplicate by title
    seen: set[str] = set()
    out: list[dict] = []
    for d in decisions:
        t = d.get("title") or ""
        if t in seen:
            continue
        seen.add(t)
        out.append(d)
    return out[:12]


def build_expense_intelligence_executive_view(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    Compact, UI-oriented slice of ``build_expense_intelligence_bundle`` output
    for GET /analysis/{id}/executive (deterministic, no new calculations).
    """
    ea = (bundle or {}).get("expense_analysis") or {}
    meta = ea.get("meta") or {}
    rows = ea.get("by_period") or []
    if meta.get("error") == "no_statements" or not rows:
        reason = meta.get("error") or "no_periods"
        return {
            "available": False,
            "reason": reason,
            "period": None,
            "categories": {},
            "totals": None,
            "top_category": None,
            "mom_change": None,
            "expense_ratio": None,
            "expense_ratio_prior": None,
            "anomalies": [],
            "decisions": [],
            "largest_increasing_category": None,
            "narrative_headline": "",
            "narrative_excerpt": "",
        }

    latest = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else None
    trends = ea.get("trends") or {}
    mom = trends.get("mom")
    cats = latest.get("categories") or {}
    if not isinstance(cats, dict):
        cats = {}

    sorted_cats = sorted(
        ((str(k), float(v or 0)) for k, v in cats.items()),
        key=lambda kv: (-abs(kv[1]), kv[0]),
    )
    top_cat: dict[str, Any] | None = None
    for name, amt in sorted_cats:
        if name.lower() == "other" and len(sorted_cats) > 1:
            continue
        top_cat = {"name": name, "amount": _r2(amt)}
        break
    if top_cat is None and sorted_cats:
        top_cat = {"name": sorted_cats[0][0], "amount": _r2(sorted_cats[0][1])}

    cat_ts = ea.get("by_category_timeseries") or {}
    if isinstance(top_cat, dict) and top_cat.get("name"):
        te = float(latest.get("total_expense") or 0)
        amt = float(top_cat.get("amount") or 0)
        if te > 1e-6:
            top_cat["share_of_cost_pct"] = _r2(amt / te * 100)
        sname = str(top_cat.get("name") or "")
        if isinstance(cat_ts, dict):
            series = cat_ts.get(sname)
            if isinstance(series, list) and len(series) >= 2:
                a0 = float(series[-2].get("amount") or 0)
                a1 = float(series[-1].get("amount") or 0)
                if abs(a0) > 1e-6:
                    top_cat["amount_mom_pct"] = _r2((a1 - a0) / abs(a0) * 100)

    expl = (bundle or {}).get("expense_explanation") or {}
    tm = expl.get("top_movers") or {}
    inc = tm.get("increasing") or []
    first_inc = inc[0] if isinstance(inc, list) and inc else None
    largest_inc: dict[str, Any] | None = None
    if isinstance(first_inc, dict) and first_inc.get("category"):
        largest_inc = {
            "name": str(first_inc.get("category")),
            "absolute_change": _r2(first_inc.get("absolute_change")),
            "pct_change": _r2(first_inc.get("pct_change")),
            "direction": "up",
        }

    anomalies_out: list[dict[str, Any]] = []
    for a in (bundle or {}).get("expense_anomalies") or []:
        if not isinstance(a, dict):
            continue
        anomalies_out.append(
            {
                "anomaly_id": a.get("anomaly_id"),
                "signal": a.get("signal"),
                "severity": a.get("severity"),
                "short_explanation": a.get("short_explanation"),
                "observed": _r2(a.get("observed")),
                "deviation_pct": _r2(a.get("deviation_pct")),
            }
        )
        if len(anomalies_out) >= 8:
            break

    decisions_out: list[dict[str, Any]] = []
    for d in (bundle or {}).get("expense_decisions") or []:
        if not isinstance(d, dict):
            continue
        decisions_out.append(
            {
                "decision_id": d.get("decision_id"),
                "title": d.get("title"),
                "priority": d.get("priority"),
                "rationale": d.get("rationale"),
                "action": d.get("action"),
                "expected_financial_impact": d.get("expected_financial_impact"),
                "linked_anomaly_ids": d.get("linked_anomaly_ids"),
            }
        )
        if len(decisions_out) >= 12:
            break

    narr = expl.get("narrative") or ""
    if isinstance(narr, str) and len(narr) > 320:
        narr = narr[:317] + "..."

    return {
        "available": True,
        "reason": None,
        "period": latest.get("period"),
        "categories": {str(k): _r2(v) for k, v in sorted(cats.items(), key=lambda kv: kv[0])},
        "totals": {
            "revenue": latest.get("revenue"),
            "total_expense": latest.get("total_expense"),
            "cogs": latest.get("cogs"),
            "operating_expenses": latest.get("operating_expenses"),
            "unclassified_pnl_debits": latest.get("unclassified_pnl_debits"),
        },
        "top_category": top_cat,
        "mom_change": mom,
        "expense_ratio": latest.get("expense_pct_of_revenue"),
        "expense_ratio_prior": prev.get("expense_pct_of_revenue") if prev else None,
        "anomalies": anomalies_out,
        "decisions": decisions_out,
        "largest_increasing_category": largest_inc,
        "narrative_headline": expl.get("headline") or "",
        "narrative_excerpt": narr if isinstance(narr, str) else "",
    }


def build_expense_intelligence_bundle(
    period_statements: list[dict],
    *,
    branch_period_statements: dict[str, list[dict]] | None = None,
    branch_labels: dict[str, str] | None = None,
    lang: str = "en",
) -> dict[str, Any]:
    """Public entry point (signature preserved)."""
    lang = lang if lang in ("en", "ar", "tr") else "en"

    if not period_statements:
        return {
            "expense_analysis": {"meta": {"error": "no_statements", "periods_covered": [], "latest_period": None}},
            "expense_anomalies": [],
            "expense_decisions": [],
            "expense_explanation": {
                "headline": "",
                "narrative": "",
                "drivers": [],
                "comparison_basis": "none",
                "top_movers": {"increasing": [], "decreasing": []},
            },
        }

    stmts = _sorted_statements(period_statements)
    rows = _build_by_period_rows(stmts)
    by_year = _rollup_by_year(rows)
    cat_ts = _category_timeseries(rows)
    trends = _compute_trends(rows)

    branches = _branch_breakdown(branch_period_statements, branch_labels) if branch_period_statements else []

    anomalies = _detect_anomalies(rows, lang)
    explanation = _build_explanation(rows, trends, anomalies, lang)
    decisions = _build_decisions(anomalies, rows[-1])

    expense_analysis = {
        "meta": {
            "engine": "expense_intelligence_phase1",
            "lang": lang,
            "periods_covered": [r.get("period") for r in rows],
            "latest_period": rows[-1].get("period"),
            "statement_count": len(rows),
            "threshold_source": THRESHOLD_SOURCE,
        },
        "by_period": rows,
        "by_year": by_year,
        "by_category_timeseries": cat_ts,
        "by_branch": branches,
        "trends": trends,
    }

    return {
        "expense_analysis": expense_analysis,
        "expense_anomalies": anomalies,
        "expense_decisions": decisions,
        "expense_explanation": explanation,
    }
