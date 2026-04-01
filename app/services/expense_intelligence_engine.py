"""
expense_intelligence_engine.py — Phase 1 Expense Intelligence Engine

Produces structured JSON for downstream APIs (no UI):
  expense_analysis, expense_anomalies, expense_decisions, expense_explanation

Rules:
  - Reads ONLY financial_statements-style dicts (same contract as expense_engine).
  - Reuses expense_engine categorization; does not recompute revenue/COGS/OpEx totals
    (totals taken from income_statement sections).
  - No database access.
"""
from __future__ import annotations

import re
import statistics
import uuid
from collections import defaultdict
from typing import Any, Optional

from app.services.expense_engine import (
    THRESHOLD_SOURCE,
    THRESHOLDS,
    _build_groups,
    _mom,
    _pct,
)

_PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")


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


def _total_expense(is_: dict) -> tuple[float, float, float, float]:
    """Returns (cogs, opex, unclassified, total_expense)."""
    cogs = float((is_.get("cogs") or {}).get("total") or 0)
    opex = float((is_.get("expenses") or {}).get("total") or 0)
    uncl = float((is_.get("unclassified_pnl_debits") or {}).get("total") or 0)
    return cogs, opex, uncl, cogs + opex + uncl


def _revenue(is_: dict) -> float:
    return float((is_.get("revenue") or {}).get("total") or 0)


def _sorted_statements(stmts: list[dict]) -> list[dict]:
    return sorted(stmts, key=lambda s: (s.get("period") or ""))


def _category_amounts_from_groups(groups: dict[str, dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for ck, g in groups.items():
        out[ck] = float(g.get("current") or 0)
    return out


def _median(xs: list[float]) -> Optional[float]:
    vals = [float(x) for x in xs if x is not None and x == x]
    if not vals:
        return None
    return float(statistics.median(vals))


def _build_by_period_rows(stmts: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for stmt in stmts:
        p = stmt.get("period") or ""
        parsed = _parse_period(p)
        year, month = (parsed[0], parsed[1]) if parsed else (None, None)
        is_ = stmt.get("income_statement") or {}
        rev = _revenue(is_)
        cogs, opex, uncl, tot = _total_expense(is_)
        groups = _build_groups(stmt, rev if rev else None)
        cats = _category_amounts_from_groups(groups)
        rows.append(
            {
                "period": p,
                "year": year,
                "month": month,
                "revenue": _r2(rev),
                "cogs": _r2(cogs),
                "operating_expenses": _r2(opex),
                "unclassified_pnl_debits": _r2(uncl),
                "total_expense": _r2(tot),
                "expense_pct_of_revenue": _pct(tot, rev) if rev else None,
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
    out = []
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
        sorted_b = _sorted_statements(bstmts)
        latest = sorted_b[-1]
        p = latest.get("period") or ""
        is_ = latest.get("income_statement") or {}
        rev = _revenue(is_)
        cogs, opex, uncl, tot = _total_expense(is_)
        groups = _build_groups(latest, rev if rev else None)
        cats = _category_amounts_from_groups(groups)
        out.append(
            {
                "branch_id": bid,
                "branch_name": (branch_labels or {}).get(bid) or bid,
                "latest_period": p,
                "revenue": _r2(rev),
                "total_expense": _r2(tot),
                "cogs": _r2(cogs),
                "operating_expenses": _r2(opex),
                "unclassified_pnl_debits": _r2(uncl),
                "expense_pct_of_revenue": _pct(tot, rev) if rev else None,
                "categories": {k: _r2(v) for k, v in sorted(cats.items())},
            }
        )
    out.sort(key=lambda x: x.get("total_expense") or 0, reverse=True)
    return out


def _compute_trends(rows: list[dict], stmts: list[dict]) -> dict[str, Any]:
    if len(rows) < 1:
        return {
            "mom": None,
            "yoy": None,
            "expense_pct_of_revenue_series": [],
        }
    last = rows[-1]
    prev_row = rows[-2] if len(rows) >= 2 else None

    mom: dict[str, Any] = {}
    if prev_row:
        tr = float(last.get("total_expense") or 0)
        pr = float(prev_row.get("total_expense") or 0)
        rev_l = float(last.get("revenue") or 0)
        rev_p = float(prev_row.get("revenue") or 0)
        mom = {
            "total_expense_pct": _mom(tr, pr),
            "revenue_pct": _mom(rev_l, rev_p),
            "expense_pct_of_revenue_pp": None,
            "from_period": prev_row.get("period"),
            "to_period": last.get("period"),
        }
        epr_l = last.get("expense_pct_of_revenue")
        epr_p = prev_row.get("expense_pct_of_revenue")
        if epr_l is not None and epr_p is not None:
            mom["expense_pct_of_revenue_pp"] = _r2(float(epr_l) - float(epr_p))

    yoy: dict[str, Any] | None = None
    parsed = _parse_period(last.get("period") or "")
    if parsed:
        y, m = parsed
        want = _yoy_period(y, m)
        match = next((r for r in rows if r.get("period") == want), None)
        if match:
            tr = float(last.get("total_expense") or 0)
            yr = float(match.get("total_expense") or 0)
            rev_l = float(last.get("revenue") or 0)
            rev_y = float(match.get("revenue") or 0)
            yoy = {
                "total_expense_pct": _mom(tr, yr),
                "revenue_pct": _mom(rev_l, rev_y),
                "expense_pct_of_revenue_pp": None,
                "from_period": match.get("period"),
                "to_period": last.get("period"),
            }
            el = last.get("expense_pct_of_revenue")
            ey = match.get("expense_pct_of_revenue")
            if el is not None and ey is not None:
                yoy["expense_pct_of_revenue_pp"] = _r2(float(el) - float(ey))

    series = [
        {"period": r.get("period"), "expense_pct_of_revenue": r.get("expense_pct_of_revenue")}
        for r in rows
    ]
    return {"mom": mom or None, "yoy": yoy, "expense_pct_of_revenue_series": series}


def _detect_anomalies(rows: list[dict], lang: str) -> list[dict]:
    ar = lang == "ar"
    tr = lang == "tr"
    anomalies: list[dict] = []

    if len(rows) < 1:
        return anomalies

    last = rows[-1]
    prior_rows = rows[:-1]

    # --- Category vs median baseline (prior periods) ---
    all_cats: set[str] = set()
    for r in rows:
        all_cats.update((r.get("categories") or {}).keys())

    for cat in sorted(all_cats):
        hist = [
            float((r.get("categories") or {}).get(cat) or 0)
            for r in prior_rows
            if (r.get("categories") or {}).get(cat) is not None
        ]
        if len(hist) < 2:
            continue
        base = _median(hist)
        if base is None or base < 1e-6:
            continue
        obs = float((last.get("categories") or {}).get(cat) or 0)
        dev_pct = _mom(obs, base)
        if dev_pct is None or dev_pct < 18.0:
            continue
        sev = "high" if dev_pct >= 35 else "medium"
        if ar:
            narr = f"فئة المصروف «{cat}» في {last.get('period')} أعلى بكثير من وسيط الفترات السابقة ({dev_pct:+.1f}٪)."
        elif tr:
            narr = f"«{cat}» gideri {last.get('period')} döneminde önceki dönemlerin medyanına göre belirgin yükseldi (%{dev_pct:+.1f})."
        else:
            narr = (
                f"Expense category '{cat}' in {last.get('period')} is materially above the "
                f"median of prior periods ({dev_pct:+.1f}% vs baseline)."
            )
        anomalies.append(
            {
                "anomaly_id": f"exp_cat_{cat}_{last.get('period')}".replace(" ", "_"),
                "severity": sev,
                "scope": "company",
                "category": cat,
                "period": last.get("period"),
                "signal": "unusual_increase_vs_baseline",
                "observed": _r2(obs),
                "baseline_value": _r2(base),
                "baseline_method": "median_prior_periods",
                "deviation_pct": dev_pct,
                "expense_pct_of_revenue": _pct(
                    float((last.get("categories") or {}).get(cat) or 0),
                    float(last.get("revenue") or 0),
                )
                if float(last.get("revenue") or 0) > 0
                else None,
                "revenue_in_period": last.get("revenue"),
                "narrative": narr,
            }
        )

    # --- Total expense spike vs prior month with modest revenue growth ---
    if len(rows) >= 2:
        tr = float(last.get("total_expense") or 0)
        pr = float(rows[-2].get("total_expense") or 0)
        rev_l = float(last.get("revenue") or 0)
        rev_p = float(rows[-2].get("revenue") or 0)
        te_mom = _mom(tr, pr)
        rev_mom = _mom(rev_l, rev_p) if rev_p else None
        if (
            te_mom is not None
            and te_mom >= 12.0
            and (rev_mom is None or te_mom > rev_mom + 5.0)
        ):
            if ar:
                narr = f"إجمالي المصروفات ارتفع {te_mom:.1f}٪ عن الشهر السابق، أسرع من ديناميكيات الإيرادات."
            elif tr:
                narr = f"Toplam giderler bir önceki aya göre %{te_mom:.1f} arttı; gelir hareketini belirgin şekilde aştı."
            else:
                narr = (
                    f"Total expense rose {te_mom:.1f}% vs prior month, outpacing revenue momentum."
                )
            anomalies.append(
                {
                    "anomaly_id": f"exp_total_mom_{last.get('period')}",
                    "severity": "high" if te_mom >= 22 else "medium",
                    "scope": "company",
                    "category": None,
                    "period": last.get("period"),
                    "signal": "total_expense_outpaced_revenue",
                    "observed": _r2(tr),
                    "baseline_value": _r2(pr),
                    "baseline_method": "prior_period",
                    "deviation_pct": te_mom,
                    "expense_pct_of_revenue": last.get("expense_pct_of_revenue"),
                    "revenue_in_period": last.get("revenue"),
                    "revenue_mom_pct": rev_mom,
                    "narrative": narr,
                }
            )

    # --- Opex ratio threshold (from internal thresholds) ---
    epr = last.get("expense_pct_of_revenue")
    thr = THRESHOLDS.get("expense_ratio_pct", {})
    if epr is not None and thr:
        crit = thr.get("critical", 80)
        warn = thr.get("warning", 65)
        if float(epr) >= warn:
            sev = "high" if float(epr) >= crit else "medium"
            if ar:
                narr = f"نسبة المصروف إلى الإيرادات {float(epr):.1f}٪ تتجاوز عتبة المراقبة."
            elif tr:
                narr = f"Gelire oranla gider oranı %{float(epr):.1f} — eşik üzerinde."
            else:
                narr = f"Expense-to-revenue ratio {float(epr):.1f}% exceeds monitoring threshold."
            anomalies.append(
                {
                    "anomaly_id": f"exp_ratio_{last.get('period')}",
                    "severity": sev,
                    "scope": "company",
                    "category": None,
                    "period": last.get("period"),
                    "signal": "elevated_expense_to_revenue_ratio",
                    "observed": float(epr),
                    "baseline_value": warn,
                    "baseline_method": "internal_threshold",
                    "deviation_pct": None,
                    "expense_pct_of_revenue": epr,
                    "revenue_in_period": last.get("revenue"),
                    "threshold_source": THRESHOLD_SOURCE,
                    "narrative": narr,
                }
            )

    anomalies.sort(
        key=lambda a: {"high": 0, "medium": 1, "low": 2}.get(a.get("severity", ""), 3)
    )
    return anomalies


def _build_explanation(
    rows: list[dict],
    trends: dict[str, Any],
    anomalies: list[dict],
    latest_groups: dict[str, dict],
    lang: str,
) -> dict[str, Any]:
    ar = lang == "ar"
    tr = lang == "tr"
    drivers: list[dict] = []

    if not rows:
        return {
            "headline": "",
            "narrative": "",
            "drivers": [],
            "comparison_basis": "none",
        }

    last = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else None

    # Top category deltas MoM
    if prev:
        cats_l = last.get("categories") or {}
        cats_p = prev.get("categories") or {}
        deltas: list[tuple[str, float]] = []
        for ck in set(cats_l) | set(cats_p):
            a = float(cats_l.get(ck) or 0) - float(cats_p.get(ck) or 0)
            if abs(a) > 1e-6:
                deltas.append((ck, a))
        deltas.sort(key=lambda x: -abs(x[1]))
        for ck, d in deltas[:4]:
            direction = "up" if d > 0 else "down"
            drivers.append(
                {
                    "driver": f"category_{ck}",
                    "direction": direction,
                    "magnitude_amount": _r2(d),
                    "categories": [ck],
                    "contribution_summary": f"{ck} {_r2(d):+}",
                }
            )

    mom = trends.get("mom") or {}
    yoy = trends.get("yoy") or {}

    if ar:
        headline = f"ملخص مصروفات {last.get('period')}"
        parts = [
            f"إجمالي المصروفات: {last.get('total_expense')} مقابل إيرادات {last.get('revenue')}.",
        ]
        if mom.get("total_expense_pct") is not None:
            parts.append(f"تغير شهري لإجمالي المصروفات: {mom.get('total_expense_pct'):+.1f}٪.")
        if yoy.get("total_expense_pct") is not None:
            parts.append(f"تغير سنوي لإجمالي المصروفات: {yoy.get('total_expense_pct'):+.1f}٪.")
    elif tr:
        headline = f"{last.get('period')} dönemi gider özeti"
        parts = [
            f"Toplam gider: {last.get('total_expense')}, gelir: {last.get('revenue')}.",
        ]
        if mom.get("total_expense_pct") is not None:
            parts.append(f"Aylık toplam gider değişimi: %{mom.get('total_expense_pct'):+.1f}.")
        if yoy.get("total_expense_pct") is not None:
            parts.append(f"Yıllık toplam gider değişimi: %{yoy.get('total_expense_pct'):+.1f}.")
    else:
        headline = f"Expense summary for {last.get('period')}"
        parts = [
            f"Total expense {last.get('total_expense')} vs revenue {last.get('revenue')}.",
        ]
        if mom.get("total_expense_pct") is not None:
            parts.append(f"MoM total expense change: {mom.get('total_expense_pct'):+.1f}%.")
        if yoy.get("total_expense_pct") is not None:
            parts.append(f"YoY total expense change: {yoy.get('total_expense_pct'):+.1f}%.")

    if anomalies:
        parts.append(f"{len(anomalies)} anomaly signal(s) flagged for review.")

    basis = []
    if prev:
        basis.append("vs_prior_month")
    if yoy:
        basis.append("vs_yoy_same_month")
    if any(a.get("baseline_method") == "median_prior_periods" for a in anomalies):
        basis.append("vs_median_baseline")

    return {
        "headline": headline,
        "narrative": " ".join(parts),
        "drivers": drivers,
        "comparison_basis": "+".join(basis) if basis else "latest_period_only",
        "top_movers": sorted(
            [
                {
                    "category": ck,
                    "variance_pct": g.get("variance_pct"),
                    "variance_amount": g.get("variance"),
                    "direction": g.get("direction"),
                }
                for ck, g in latest_groups.items()
                if g.get("variance_pct") is not None
            ],
            key=lambda x: abs(x.get("variance_pct") or 0),
            reverse=True,
        )[:5],
    }


def _estimate_savings_impact(
    revenue: float,
    category_amount: float,
    reduction_pct: float,
) -> dict[str, Any]:
    """Rough margin impact: savings as bps of revenue if revenue > 0."""
    if revenue <= 0:
        return {
            "estimated_monthly_savings": None,
            "estimated_operating_margin_bps": None,
            "confidence": "low",
        }
    save = category_amount * (reduction_pct / 100.0)
    bps = (save / revenue) * 10000.0
    return {
        "estimated_monthly_savings": _r2(save),
        "estimated_operating_margin_bps": _r2(bps),
        "confidence": "low",
    }


def _build_decisions(
    anomalies: list[dict],
    last_row: dict,
    lang: str,
) -> list[dict]:
    ar = lang == "ar"
    tr = lang == "tr"
    decisions: list[dict] = []
    rev = float(last_row.get("revenue") or 0)

    for an in anomalies[:8]:
        sig = an.get("signal")
        cat = an.get("category")
        linked = [an.get("anomaly_id")]
        if sig == "unusual_increase_vs_baseline" and cat:
            amt = float(an.get("observed") or 0)
            impact = _estimate_savings_impact(rev, amt, 5.0)
            if ar:
                title = f"مراجعة وضبط مصروفات {cat}"
                rationale = an.get("narrative", "")
                actions = [
                    f"تحليل بنود {cat} مقابل الميزانية والعقود",
                    "تحديد ارتفاعات لمرة واحدة مقابل تكاليف متكررة",
                ]
                enarr = "افتراض خفض 5٪ لهذه الفئة — تقدير أولي فقط."
            elif tr:
                title = f"{cat} giderlerini gözden geçir ve sıkılaştır"
                rationale = an.get("narrative", "")
                actions = [
                    f"{cat} kalemlerini bütçe ve sözleşmelere göre analiz et",
                    "Tek seferlik artışları tekrarlayan maliyetlerden ayır",
                ]
                enarr = "%5 varsayımsal kısıntı — yalnızca kabaca tahmin."
            else:
                title = f"Review and tighten '{cat}' spending"
                rationale = an.get("narrative", "")
                actions = [
                    f"Line-item review of {cat} vs budget and contracts",
                    "Separate one-time spikes from recurring run-rate increases",
                ]
                enarr = "Assumes 5% reduction in this category — illustrative only."
            decisions.append(
                {
                    "decision_id": f"dc_{uuid.uuid4().hex[:10]}",
                    "title": title,
                    "rationale": rationale,
                    "actions": actions,
                    "expected_financial_impact": {
                        "narrative": enarr,
                        **impact,
                    },
                    "linked_anomaly_ids": linked,
                    "priority": "high" if an.get("severity") == "high" else "medium",
                }
            )
        elif sig == "total_expense_outpaced_revenue":
            if ar:
                title = "تجميد أو خفض الإنفاق التشغيلي غير الضروري"
                rationale = an.get("narrative", "")
                actions = ["تدقيق سريع لأكبر 5 بنود مصروف", "مواءمة الإنفاق مع توقعات الإيرادات"]
            elif tr:
                title = "Gereksiz opex'i dondur veya kıs"
                rationale = an.get("narrative", "")
                actions = [
                    "En büyük 5 gider kalemini hızlı denetle",
                    "Harcamayı gelir öngörüsüyle hizala",
                ]
            else:
                title = "Freeze or cut non-essential operating spend"
                rationale = an.get("narrative", "")
                actions = [
                    "Rapid audit of top 5 expense lines",
                    "Align spending with revenue outlook",
                ]
            te = float(last_row.get("total_expense") or 0)
            impact = _estimate_savings_impact(rev, te, 3.0)
            decisions.append(
                {
                    "decision_id": f"dc_{uuid.uuid4().hex[:10]}",
                    "title": title,
                    "rationale": rationale,
                    "actions": actions,
                    "expected_financial_impact": {
                        "narrative": "Assumes 3% reduction in total expense — illustrative.",
                        **impact,
                    },
                    "linked_anomaly_ids": linked,
                    "priority": "high",
                }
            )
        elif sig == "elevated_expense_to_revenue_ratio":
            if ar:
                title = "إعادة هيكلة تكلفة الإيراد لتحسين الهامش"
                rationale = an.get("narrative", "")
                actions = ["إعادة تسعير/مزيج المنتج", "خفض تكلفة مباشرة أو تشغيلية حسب التشخيص"]
            elif tr:
                title = "Marj için gelir başına maliyet yapısını yeniden düzenle"
                rationale = an.get("narrative", "")
                actions = ["Fiyatlandırma/ürün karmasını gözden geçir", "Doğrudan veya operasyonel maliyeti hedefle"]
            else:
                title = "Restructure cost-to-revenue to recover margin"
                rationale = an.get("narrative", "")
                actions = [
                    "Revisit pricing / mix",
                    "Target direct or operating cost levers per diagnosis",
                ]
            impact = _estimate_savings_impact(rev, float(last_row.get("total_expense") or 0), 4.0)
            decisions.append(
                {
                    "decision_id": f"dc_{uuid.uuid4().hex[:10]}",
                    "title": title,
                    "rationale": rationale,
                    "actions": actions,
                    "expected_financial_impact": {
                        "narrative": "Assumes 4% structural expense reduction — illustrative.",
                        **impact,
                    },
                    "linked_anomaly_ids": linked,
                    "priority": "high",
                }
            )

    # De-dupe by title
    seen: set[str] = set()
    uniq: list[dict] = []
    for d in decisions:
        t = d.get("title") or ""
        if t in seen:
            continue
        seen.add(t)
        uniq.append(d)
    return uniq[:12]


def build_expense_intelligence_bundle(
    period_statements: list[dict],
    *,
    branch_period_statements: dict[str, list[dict]] | None = None,
    branch_labels: dict[str, str] | None = None,
    lang: str = "en",
) -> dict[str, Any]:
    """
    Build the Phase 1 expense intelligence JSON bundle.

    Args:
        period_statements: company-level statement dicts (financial_statements / statement pipeline shape).
        branch_period_statements: optional map branch_id -> list of statement dicts (same shape), sorted arbitrarily (will be re-sorted by period).
        branch_labels: optional branch_id -> display name
        lang: en | ar | tr (controls narrative strings)

    Returns:
        dict with keys: expense_analysis, expense_anomalies, expense_decisions, expense_explanation
    """
    lang = lang if lang in ("en", "ar", "tr") else "en"

    if not period_statements:
        empty = {
            "meta": {"error": "no_statements", "periods_covered": [], "latest_period": None},
        }
        return {
            "expense_analysis": empty,
            "expense_anomalies": [],
            "expense_decisions": [],
            "expense_explanation": {
                "headline": "",
                "narrative": "",
                "drivers": [],
                "comparison_basis": "none",
            },
        }

    stmts = _sorted_statements(period_statements)
    rows = _build_by_period_rows(stmts)
    by_year = _rollup_by_year(rows)
    cat_ts = _category_timeseries(rows)
    trends = _compute_trends(rows, stmts)

    latest = stmts[-1]
    prev = stmts[-2] if len(stmts) >= 2 else None
    rev_l = _revenue(latest.get("income_statement") or {})
    groups_prev = _build_groups(prev, _revenue(prev.get("income_statement") or {})) if prev else {}
    groups_now = _build_groups(latest, rev_l if rev_l else None)

    # Enrich latest groups with MoM variance like expense_engine
    enriched: dict[str, dict] = {}
    all_keys = sorted(
        set(groups_now) | set(groups_prev),
        key=lambda k: groups_now.get(k, {}).get("current", 0),
        reverse=True,
    )
    for ck in all_keys:
        g = dict(groups_now.get(ck, {}) or {})
        curr = float(g.get("current") or 0)
        prev_v = float((groups_prev.get(ck) or {}).get("current") or 0) if groups_prev.get(ck) else None
        if prev_v is not None:
            g["previous"] = _r2(prev_v)
            g["variance"] = _r2(curr - prev_v)
            g["variance_pct"] = _mom(curr, prev_v)
            d = g["variance_pct"]
            if d is None:
                g["direction"] = "stable"
            elif d > 3.0:
                g["direction"] = "increasing"
            elif d < -3.0:
                g["direction"] = "declining"
            else:
                g["direction"] = "stable"
        enriched[ck] = g

    branches = (
        _branch_breakdown(branch_period_statements, branch_labels)
        if branch_period_statements
        else []
    )

    anomalies = _detect_anomalies(rows, lang)
    explanation = _build_explanation(rows, trends, anomalies, enriched, lang)
    decisions = _build_decisions(anomalies, rows[-1], lang)

    expense_analysis = {
        "meta": {
            "engine": "expense_intelligence_phase1",
            "lang": lang,
            "periods_covered": [r.get("period") for r in rows],
            "latest_period": rows[-1].get("period") if rows else None,
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
