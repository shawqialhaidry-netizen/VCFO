"""
api/analysis.py — Phase 9 Stabilized

CANONICAL PRODUCT PATH (Phase 1 — single truth):
  • Primary UI data: GET /{company_id}/executive
  • Forecast: forecast_engine.build_forecast (in executive ``data.forecast`` and GET /{company_id}/forecast)
  • Structured financial overlays: statement_engine.build_statement_bundle → root data (structured_*, statement_hierarchy) + nested statements (stripped)
  • CFO decisions: cfo_decision_engine.build_cfo_decisions
  • Surfaces on canonical path: Command Center (/), Statements, CfoPanel (executive only)

PHASE 3 — Intelligence / decisions lock:
  • Product intelligence ratios/health: ``fin_intelligence.build_intelligence`` only (same scoped ``windowed`` as executive).
  • Product decisions: ``build_cfo_decisions`` fed with ``alerts_engine.build_alerts`` outputs — never ad-hoc alert builders.
  • ``intelligence_engine.run_intelligence`` — legacy GET /{company_id} aggregate only; does not define product truth.
  • Deep / profitability / trend blocks on executive are ``interpretation_secondary`` (see ``meta.product_intelligence``).

LEGACY (non-canonical — do not extend for product):
  • GET /{company_id} (this file, get_analysis): run_intelligence + flat ``statements`` map; see response ``pipeline_profile``

Legacy GET /analysis execution order (strict, historical):
  1. analysis          = run_analysis(windowed)
  2. kpi_block         = build_kpi_block(all_stmts, window)
  3. advanced_metrics  = compute_advanced_metrics(windowed, ratios)
  4. cashflow          = build_cashflow(windowed)          ← MUST be before decision
  5. decision          = run_intelligence(analysis, advanced_metrics, cashflow)  # signals only — no health_score
  6. fe_debug          = _build_debug_block(windowed)
"""
import logging
from typing import Optional, Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_company_access
from app.core.security import get_current_user
from app.models.company import Company
from app.models.trial_balance import TrialBalanceUpload
from app.services.financial_statements import build_statements, statements_to_dict
from app.services.canonical_period_statements import (
    build_branch_period_statements,
    build_period_statements_from_uploads,
    load_normalized_tb_dataframe,
)
from app.services.structured_income_statement import attach_structured_income_statement
from app.services.analysis_engine import run_analysis
from app.services.time_intelligence import build_kpi_block, filter_periods
from app.services.intelligence_engine import run_intelligence
from app.services.advanced_metrics import compute_advanced_metrics
from app.services.cashflow_engine import build_cashflow
from app.services.root_cause_engine import build_root_cause, build_root_causes
from app.services.anomaly_engine    import detect_anomalies
from app.services.narrative_builder import build_narratives
from app.services.executive_engine import build_executive_summary
from app.services.expense_engine import build_expense_intelligence as build_expense_breakdown
from app.services.cfo_decision_engine import build_cfo_decisions
from app.services.period_aggregation import build_annual_layer
from app.services.time_scope import scope_from_params, filter_by_scope
from app.services.fin_intelligence import build_intelligence  # FIX-1.1: single health_score source
from app.services.metric_definitions import cogs_ratio_pct, opex_ratio_pct, total_cost_ratio_pct
from app.services.metric_resolver import MetricResolver
from app.services.confidence_engine import score_confidence
from app.services.attribution_engine import profit_bridge_attribution
from app.services.narrative_engine import (
    build_narrative,
    collect_default_narrative_warning_items,
    collect_period_block_warning_items,
    enrich_trend_object,
    format_narrative_warning_item,
    format_narrative_warning_items,
    format_prev_comparison_label,
    format_simple_narrative,
    normalize_narrative_lang,
    reconciliation_warning_payload,
)

# ── Phase 22 scope helper ─────────────────────────────────────────────────────

def _apply_scope(all_stmts: list, scope_basis_type: str = "", scope_period: str = "",
                 scope_year: str = "", scope_from_period: str = "",
                 scope_to_period: str = "") -> tuple:
    """
    Resolve and apply time-scope to all_stmts.
    Returns (scoped_stmts, scope_dict).
    Falls back to all_stmts if scope_basis_type is empty/all.
    """
    if not scope_basis_type or scope_basis_type.strip().lower() in ("", "all"):
        return all_stmts, None
    scope = scope_from_params(
        basis_type  = scope_basis_type,
        period      = scope_period      or None,
        year        = scope_year        or None,
        from_period = scope_from_period or None,
        to_period   = scope_to_period   or None,
        all_stmts   = all_stmts,
    )
    if scope.get("error"):
        from fastapi import HTTPException
        raise HTTPException(400, scope["error"])
    scoped = filter_by_scope(all_stmts, scope)
    return scoped, scope


logger = logging.getLogger("vcfo.analysis")

# ── Metric Resolver — Phase 2 diagnostic-only (see metric_resolver module doc) ─
_METRIC_SHADOW_KEYS = (
    "revenue",
    "net_profit",
    "net_margin_pct",
    "gross_margin_pct",
    "operating_expenses",
    "total_cost_ratio_pct",
    "current_ratio",
    "working_capital",
    "operating_cashflow",
)


def _shadow_compare_metrics(
    *,
    resolver: MetricResolver,
    current: dict,
    label: str,
) -> None:
    """
    Diagnostic-only parity checks vs MetricResolver (never authoritative for product).
    Logs mismatches only; never raises and never changes responses.
    """
    try:
        for k in _METRIC_SHADOW_KEYS:
            rv = resolver.get(k)
            cv = current.get(k)
            if rv is None and cv is None:
                continue
            # Tolerance by unit family (pct/ratio tighter than currency)
            tol = 0.05
            if k in ("revenue", "net_profit", "operating_expenses", "working_capital", "operating_cashflow"):
                tol = 0.5
            if k in ("current_ratio",):
                tol = 0.005
            try:
                if rv is None or cv is None:
                    if (rv is None) != (cv is None):
                        logger.warning("metric-shadow %s %s mismatch: resolver=%s current=%s meta=%s", label, k, rv, cv, resolver.meta())
                    continue
                diff = abs(float(rv) - float(cv))
                if diff > tol:
                    logger.warning("metric-shadow %s %s mismatch: resolver=%s current=%s diff=%.4f meta=%s", label, k, rv, cv, diff, resolver.meta())
            except Exception:
                # Non-numeric mismatch
                if rv != cv:
                    logger.warning("metric-shadow %s %s mismatch (non-numeric): resolver=%s current=%s meta=%s", label, k, rv, cv, resolver.meta())
    except Exception as exc:
        logger.warning("metric-shadow %s failed: %s", label, exc)

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(get_current_user), Depends(require_company_access)],
)

VALID_WINDOWS = {"3M", "6M", "12M", "YTD", "ALL"}


def _dedupe_causal_items_by_id(items: list | None) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        uid = str(it.get("id") or "").strip() or f"_idx:{len(out)}"
        if uid in seen:
            continue
        seen.add(uid)
        out.append(it)
    return out


def _merge_causal_sources_for_realize(
    dec_pack: dict | None,
    deep_intel: dict | None,
    profit_intel: dict | None,
) -> list[dict]:
    """Merge CFO + expense-pressure + profitability causal rows; dedupe by id."""
    flat: list[dict] = []
    if dec_pack:
        flat.extend(dec_pack.get("causal_items") or [])
    di = deep_intel or {}
    ei = di.get("expense_intelligence") or {}
    pa = ei.get("pressure_assessment") or {}
    flat.extend(pa.get("causal_items") or [])
    pi = profit_intel or {}
    interp = pi.get("interpretation") or {}
    ci_pi = interp.get("causal_items") or []
    if ci_pi:
        flat.extend(ci_pi)
    else:
        dpi = di.get("profitability_intelligence") or {}
        interp2 = dpi.get("interpretation") or {}
        flat.extend(interp2.get("causal_items") or [])
    return _dedupe_causal_items_by_id(flat)


def _augment_cfo_decision_pack_for_api(
    dec_pack: dict | None,
    safe_lang: str,
    *,
    deep_intel: dict | None = None,
    profit_intel: dict | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Align GET /decisions and board-report CFO payloads with GET /executive:
    - decisions[] gain causal_realized (CFO causal row only, same index as executive)
    - realized_causal_items = realize(merged CFO + optional deep/profit templates)
    - causal_items = merged template rows (deduped)
    """
    from app.services.causal_realize import realize_causal_items

    merged_templates = _merge_causal_sources_for_realize(dec_pack, deep_intel, profit_intel)
    realized_causal_items = realize_causal_items(merged_templates, safe_lang)
    raw_cfo = (dec_pack or {}).get("causal_items") or []
    realized_per_dec = realize_causal_items(raw_cfo, safe_lang)
    decisions_for_api: list[dict] = []
    for i, dec in enumerate((dec_pack or {}).get("decisions") or []):
        row = dict(dec)
        if i < len(realized_per_dec):
            r = realized_per_dec[i]
            row["causal_realized"] = {
                "id": r.get("id"),
                "change_text": r.get("change_text") or "",
                "cause_text": r.get("cause_text") or "",
                "action_text": r.get("action_text") or "",
            }
        decisions_for_api.append(row)
    return decisions_for_api, realized_causal_items, merged_templates


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_df(record: TrialBalanceUpload):
    """Branch / legacy CSV readers — same disk rules as canonical TB path (no mapped_type required)."""
    return load_normalized_tb_dataframe(record)


def _branch_context_for_cfo_decisions(db: Session, company_id: str) -> Optional[dict]:
    """
    Latest-period branch snapshots for portfolio-level recommendations (2+ branches with data).
    Uses canonical branch TB statements (Phase 5).
    """
    try:
        from app.api import branches as _branches_api
        from app.models.branch import Branch

        branches = (
            db.query(Branch)
            .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa: E712
            .all()
        )
        if len(branches) < 2:
            return None
        snapshots: list[dict] = []
        for b in branches:
            stmts_b = _branches_api._branch_statements_from_uploads(db, company_id, b.id)
            if not stmts_b:
                continue
            last = stmts_b[-1]
            is_ = last.get("income_statement") or {}
            rev = float((is_.get("revenue") or {}).get("total") or 0)
            if rev <= 0:
                continue
            npv = float(is_.get("net_profit") or 0)
            nm = is_.get("net_margin_pct")
            if nm is None:
                nm = round(npv / rev * 100, 2) if rev else None
            snapshots.append({
                "branch_id": b.id,
                "name": b.name or str(b.id),
                "revenue": rev,
                "net_margin_pct": nm,
            })
        if len(snapshots) < 2:
            return None
        total_rev = sum(s["revenue"] for s in snapshots) or 1.0
        for s in snapshots:
            s["revenue_share_pct"] = round(s["revenue"] / total_rev * 100.0, 2)
        leader = max(snapshots, key=lambda x: x["revenue"])
        weakest = min(
            snapshots,
            key=lambda x: (x["net_margin_pct"] if x["net_margin_pct"] is not None else 0.0),
        )
        return {
            "revenue_leader": {
                "branch_id": leader["branch_id"],
                "name": leader["name"],
                "revenue": leader["revenue"],
                "revenue_share_pct": leader.get("revenue_share_pct"),
            },
            "weakest": {
                "branch_id": weakest["branch_id"],
                "name": weakest["name"],
                "net_margin_pct": float(weakest["net_margin_pct"] or 0),
                "revenue_share_pct": weakest.get("revenue_share_pct"),
            },
        }
    except Exception:
        return None


def _query_branch_tb_uploads(db: Session, company_id: str) -> list:
    """All successful branch-scoped TB uploads for consolidation (Phase 5)."""
    return (
        db.query(TrialBalanceUpload)
        .filter(
            TrialBalanceUpload.company_id == company_id,
            TrialBalanceUpload.status == "ok",
            TrialBalanceUpload.branch_id.isnot(None),
        )
        .order_by(TrialBalanceUpload.uploaded_at.asc())
        .all()
    )


def _apply_statement_scope_meta(
    stmts: list[dict],
    *,
    company_id: str,
    data_source: str,
    branch_id: Optional[str] = None,
    is_consolidated: bool = False,
) -> None:
    for d in stmts:
        d["company_id"] = company_id
        d["data_source"] = data_source
        d["is_consolidated"] = is_consolidated
        if branch_id:
            d["branch_id"] = branch_id


def _attach_consolidation_branch_coverage(
    db: Session,
    company_id: str,
    stmts: list[dict],
    uploads: list[Any],
) -> None:
    """
    Mark periods where not every active branch contributed a TB for that period.
    Does not alter numbers — visibility only.
    """
    from app.models.branch import Branch

    active = {
        b.id
        for b in db.query(Branch)
        .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa: E712
        .all()
    }
    for d in stmts:
        p = d.get("period")
        if not p or not active:
            d["incomplete_accounting_data"] = False
            d.pop("missing_active_branch_ids", None)
            continue
        present: set[str] = set()
        for u in uploads:
            if not u.branch_id:
                continue
            df = load_normalized_tb_dataframe(u)
            if df is not None and not df.empty and "period" in df.columns:
                if str(p) in df["period"].astype(str).unique():
                    present.add(u.branch_id)
            elif getattr(u, "period", None) == p:
                present.add(u.branch_id)
        missing = active - present
        d["incomplete_accounting_data"] = bool(missing)
        if missing:
            d["missing_active_branch_ids"] = sorted(missing)
        else:
            d.pop("missing_active_branch_ids", None)


def _build_consolidated_statements(company_id: str, db) -> list[dict]:
    """
    Phase 5 — TB-level consolidation: merge branch normalized TB rows per period,
    then canonical classify → financial_statements (same path as company uploads).
    """
    uploads = _query_branch_tb_uploads(db, company_id)
    if not uploads:
        return []
    stmts = build_period_statements_from_uploads(company_id, uploads)
    _apply_statement_scope_meta(
        stmts,
        company_id=company_id,
        data_source="branch_consolidation",
        is_consolidated=True,
    )
    _attach_consolidation_branch_coverage(db, company_id, stmts, uploads)
    return stmts


def _build_single_branch_statements(branch_id: str, company_id: str, db) -> list[dict]:
    """Phase 5 — single branch: canonical TB → statements (identical pipeline to company)."""
    uploads = (
        db.query(TrialBalanceUpload)
        .filter(
            TrialBalanceUpload.company_id == company_id,
            TrialBalanceUpload.status == "ok",
            TrialBalanceUpload.branch_id == branch_id,
        )
        .order_by(TrialBalanceUpload.uploaded_at.asc())
        .all()
    )
    if not uploads:
        return []
    return build_branch_period_statements(company_id, branch_id, uploads)


def _build_period_statements(company_id: str, uploads: list) -> list[dict]:
    """Phase 2: delegate to canonical TB → statements builder (single truth)."""
    return build_period_statements_from_uploads(company_id, uploads)


def _product_windowed_statements(
    db: Session,
    company_id: str,
    *,
    consolidate: bool,
    branch_id: Optional[str] = None,
    window: str,
    basis_type: str,
    period: str,
    year_scope: str,
    from_period: str,
    to_period: str,
) -> tuple[Company, list[dict], list[dict], dict, Optional[dict]]:
    """
    Phase 3 + Phase 5 — one statement + scope path for executive-aligned product endpoints.

    ``branch_id``: optional single-branch TB scope (mutually exclusive with ``consolidate``).
    ``consolidate``: merge all branch TB uploads per period, then canonical pipeline.

    Returns (company, all_stmts, windowed, resolved_scope, scope22_or_none).
    """
    from app.models.branch import Branch

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    bid = (branch_id or "").strip() or None
    if bid and consolidate:
        raise HTTPException(
            400,
            "Invalid scope: use branch_id for a single branch, or consolidate=true for merged branches — not both.",
        )

    if bid:
        br = db.query(Branch).filter(Branch.id == bid, Branch.company_id == company_id).first()
        if not br:
            raise HTTPException(404, "Branch not found for this company.")
        all_stmts = _build_single_branch_statements(bid, company_id, db)
        if not all_stmts:
            raise HTTPException(
                422,
                "No Trial Balance data for this branch. Upload a branch-scoped TB with normalized output.",
            )
    elif consolidate:
        all_stmts = _build_consolidated_statements(company_id, db)
        if not all_stmts:
            raise HTTPException(
                422,
                "No branch Trial Balance uploads to consolidate. Upload TBs with a branch selected.",
            )
    else:
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None),
            )
            .order_by(TrialBalanceUpload.uploaded_at.asc())
            .all()
        )
        if not uploads:
            raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")
        all_stmts = _build_period_statements(company_id, uploads)
        if not all_stmts:
            raise HTTPException(422, "Could not build statements.")

    scope22: Optional[dict] = None
    if (basis_type or "").lower() not in ("all", ""):
        scope22 = scope_from_params(
            basis_type,
            period or None,
            year_scope or None,
            from_period or None,
            to_period or None,
            all_stmts,
        )
        if scope22.get("error"):
            raise HTTPException(400, scope22["error"])
        windowed = filter_by_scope(all_stmts, scope22)
    else:
        windowed = filter_periods(
            all_stmts,
            window.upper() if window.upper() in VALID_WINDOWS else "ALL",
        )

    available = sorted(s.get("period", "") for s in windowed if s.get("period"))
    resolved_scope = scope22 if scope22 else {
        "basis_type": "all",
        "label": f"{available[0]} → {available[-1]}" if len(available) > 1
        else (available[0] if available else "all"),
        "months": available,
        "year": None,
        "from_period": available[0] if available else None,
        "to_period": available[-1] if available else None,
        "error": None,
    }
    if bid:
        resolved_scope = {**resolved_scope, "branch_id": bid}
    if consolidate:
        resolved_scope = {**resolved_scope, "consolidated": True}
    return company, all_stmts, windowed, resolved_scope, scope22


# ── Validation Layer ─────────────────────────────────────────────────────────

def _validate_pipeline(
    windowed:  list[dict],
    analysis:  dict,
    cashflow:  dict,
) -> dict:
    """
    FIX-4.1+4.2: Upgraded validation layer — standardized codes, 6 checks.
    NEVER raises. Always returns consistent shape.

    Warning codes (FIX-4.4):
      net_profit_mismatch     — NP differs between statement_engine and analysis_engine
      wc_mismatch             — WC differs between BS and analysis liquidity
      wc_formula_error        — current_assets - current_liabilities != working_capital
      balance_unbalanced      — BS assets != liabilities + equity
      cashflow_np_mismatch    — cashflow engine used different NP
      cashflow_estimated      — single-period, WC deltas = 0 (informational)
      tb_type_unknown         — tb_type not set on upload (informational)
    """
    import logging as _log
    _vlog = _log.getLogger("vcfo.validation")

    warnings_out = []
    ok = True

    if not windowed:
        return {"consistent": True, "warnings": [], "checked": 0, "period": None}

    latest = windowed[-1]
    period = latest.get("period", "?")
    is_    = latest.get("income_statement", {})
    bs_    = latest.get("balance_sheet",    {})

    stmt_np  = float(is_.get("net_profit", 0) or 0)
    stmt_wc  = float(bs_.get("working_capital", 0) or 0)
    stmt_ca  = float(bs_.get("current_assets", 0) or 0)
    stmt_cl  = float(bs_.get("current_liabilities", 0) or 0)

    def _warn(code: str, severity: str = "error", **kw):
        entry = {"code": code, "severity": severity, "period": period, **kw}
        warnings_out.append(entry)
        if severity == "error":
            _vlog.warning("[PIPELINE:%s] %s", code, kw.get("detail", code))
        else:
            _vlog.info("[PIPELINE:%s] %s", code, kw.get("detail", code))

    # ── CHECK 1: Net Profit consistency ──────────────────────────────────────
    analysis_np = float(
        (analysis.get("latest") or {}).get("profitability", {}).get("net_profit", 0) or 0
    )
    if abs(stmt_np - analysis_np) > 0.05:
        ok = False
        _warn("net_profit_mismatch", "error",
              stmt=round(stmt_np, 2), analysis=round(analysis_np, 2),
              diff=round(abs(stmt_np - analysis_np), 2),
              detail=f"NP stmt={stmt_np} analysis={analysis_np}")

    # ── CHECK 2: Working Capital consistency ──────────────────────────────────
    analysis_wc = float(
        (analysis.get("latest") or {}).get("liquidity", {}).get("working_capital", 0) or 0
    )
    if abs(stmt_wc - analysis_wc) > 0.05:
        ok = False
        _warn("wc_mismatch", "error",
              stmt=round(stmt_wc, 2), analysis=round(analysis_wc, 2),
              diff=round(abs(stmt_wc - analysis_wc), 2),
              detail=f"WC stmt={stmt_wc} analysis={analysis_wc}")

    # ── CHECK 3: WC formula integrity ─────────────────────────────────────────
    if stmt_ca > 0 or stmt_cl > 0:
        expected_wc = round(stmt_ca - stmt_cl, 2)
        if abs(stmt_wc - expected_wc) > 0.10:
            ok = False
            _warn("wc_formula_error", "error",
                  wc_stored=round(stmt_wc, 2),
                  ca_minus_cl=expected_wc,
                  ca=round(stmt_ca, 2), cl=round(stmt_cl, 2),
                  detail=f"WC={stmt_wc} but ca({stmt_ca})-cl({stmt_cl})={expected_wc}")

    # ── CHECK 4: Balance sheet balanced ──────────────────────────────────────
    if not bs_.get("is_balanced", True):
        ok = False
        _warn("balance_unbalanced", "error",
              balance_diff=bs_.get("balance_diff", 0),
              detail=f"BS diff={bs_.get('balance_diff', 0)}")

    # ── CHECK 5: Cashflow NP consistency ─────────────────────────────────────
    cf_np = float((cashflow.get("debug") or {}).get("net_profit", 0) or 0)
    if cashflow and not cashflow.get("error") and abs(stmt_np - cf_np) > 0.05:
        ok = False
        _warn("cashflow_np_mismatch", "error",
              stmt_np=round(stmt_np, 2), cf_np=round(cf_np, 2),
              diff=round(abs(stmt_np - cf_np), 2),
              detail=f"CF uses NP={cf_np}, stmt NP={stmt_np}")

    # ── CHECK 6: Cashflow single-period (informational) ───────────────────────
    if cashflow and cashflow.get("reliability") == "estimated":
        _warn("cashflow_estimated", "info",
              period_count=len(windowed),
              detail="Single period — WC deltas set to zero")

    # ── CHECK 7: TB type unknown (informational) ──────────────────────────────
    bs_warning = bs_.get("balance_warning")
    if bs_warning and "tb_type_unknown" in str(bs_warning):
        _warn("tb_type_unknown", "info",
              detail="tb_type not set on upload — NP not injected into equity")

    return {
        "consistent": ok,
        "warnings":   warnings_out,
        "checked":    7,
        "period":     period,
        # Convenience booleans for frontend
        "has_errors": any(w["severity"] == "error" for w in warnings_out),
        "has_info":   any(w["severity"] == "info"  for w in warnings_out),
        "error_codes": [w["code"] for w in warnings_out if w["severity"] == "error"],
        "info_codes":  [w["code"] for w in warnings_out if w["severity"] == "info"],
    }


def _assess_financial_integrity(pipeline_validation: dict) -> dict:
    """
    Phase 2 — map pipeline_validation to a deterministic product integrity tier.

    Blocking (suppresses governance outputs on GET /executive): any severity=error
    warning from _validate_pipeline (NP/WC/BS/CF consistency failures).

    Non-blocking: info-only codes (e.g. cashflow_estimated, tb_type_unknown).
    """
    if not isinstance(pipeline_validation, dict):
        return {
            "status": "unknown",
            "blocking": False,
            "suppress_governance_outputs": False,
        }
    if pipeline_validation.get("error"):
        return {
            "status": "unknown",
            "blocking": False,
            "suppress_governance_outputs": False,
            "validation_error": str(pipeline_validation.get("error")),
        }
    consistent = pipeline_validation.get("consistent")
    has_errors = bool(pipeline_validation.get("has_errors"))
    blocking = (consistent is False) or has_errors
    info_only = bool(pipeline_validation.get("has_info")) and not blocking
    status = "blocking" if blocking else ("warning" if info_only else "ok")
    return {
        "status": status,
        "blocking": blocking,
        "suppress_governance_outputs": blocking,
        "error_codes": list(pipeline_validation.get("error_codes") or []),
        "info_codes": list(pipeline_validation.get("info_codes") or []),
    }


def _build_debug_block(windowed: list[dict]) -> dict:
    result = {}
    try:
        for stmt in windowed:
            p    = stmt.get("period", "")
            is_  = stmt.get("income_statement", {})
            rev  = float(is_.get("revenue",   {}).get("total", 0) or 0)
            cogs = float(is_.get("cogs",      {}).get("total", 0) or 0)
            opex = float(is_.get("expenses",  {}).get("total", 0) or 0)
            tax  = float(is_.get("tax",       {}).get("total", 0) or 0)
            np_  = float(is_.get("net_profit", 0) or 0)
            result[p] = {
                "period":             p,
                "revenue":            rev,
                "cogs":               cogs,
                "opex":               opex,
                "gross_profit":       float(is_.get("gross_profit", 0) or 0),
                "operating_profit":   float(is_.get("operating_profit", 0) or 0),
                "tax":                tax,
                "net_profit":         np_,
                "expenses_for_chart": cogs + opex,
                "check":              abs(rev - cogs - opex - tax - np_) < 0.02,
                "_formula":           "net_profit = revenue - cogs - opex - tax",
            }
    except Exception as exc:
        logger.warning("Debug block error: %s", exc)
        result = {"error": "Internal processing error"}
    return result


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("/{company_id}")
def get_analysis(
    company_id:  str,
    window:      str = Query(default="ALL", description="Legacy: 3M | 6M | 12M | YTD | ALL"),
    branch_id:   str = Query(default="",    description="Optional: run full pipeline on single branch"),

    # Phase 22 — Universal time-scope params (override window when provided)
    basis_type:  str = Query(default="all",  description="month | year | ytd | custom | all"),
    period:      str = Query(default="",     description="YYYY-MM — for basis_type=month"),
    year:        str = Query(default="",     description="YYYY   — for basis_type=year or ytd"),
    from_period: str = Query(default="",     description="YYYY-MM — for basis_type=custom"),
    to_period:   str = Query(default="",     description="YYYY-MM — for basis_type=custom"),
    consolidate: bool = Query(default=False, description="true = derive company financials from branch uploads"),
    db: Session = Depends(get_db),
):
    """
    **LEGACY aggregate — not the canonical product path** (Phase 1.1).

    Returns the historical full pipeline: flat ``statements`` map, ``decision`` from
    ``run_intelligence`` (including its ``forecast`` block), ``intelligence_v2`` from
    ``fin_intelligence``, etc. This is **not** interchangeable with
    ``GET /{company_id}/executive`` (structured bundle, canonical forecast, CFO decisions).

    Product surfaces must use ``GET /{company_id}/executive``. The response includes
    ``pipeline_profile`` so clients can detect non-canonical payloads.
    """
    if window not in VALID_WINDOWS:
        raise HTTPException(400, f"Invalid window '{window}'. Use: {sorted(VALID_WINDOWS)}")

    # ── 1. Company ────────────────────────────────────────────────────────────
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    # ── 2+3. Statements — direct uploads OR branch consolidation ─────────────
    if branch_id:
        all_stmts = _build_single_branch_statements(branch_id, company_id, db)
        if not all_stmts:
            raise HTTPException(404, f"No financial data for branch {branch_id}.")
        data_source = "branch_direct"
    elif consolidate:
        all_stmts = _build_consolidated_statements(company_id, db)
        if not all_stmts:
            raise HTTPException(
                422,
                "No financial data uploaded yet (branch consolidation). Upload Trial Balances with a branch selected first.",
            )
        data_source = "branch_consolidation"
    else:
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None),  # company-level only
            )
            .order_by(TrialBalanceUpload.uploaded_at.asc())
            .all()
        )
        if not uploads:
            # Company exists, but no financial data uploaded yet.
            raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")

        all_stmts = _build_period_statements(company_id, uploads)
        if not all_stmts:
            raise HTTPException(422, "Could not build statements. Ensure normalized files exist.")
        data_source = "direct_uploads"

    # ── Phase 22: resolve scope (overrides legacy window when basis_type is set)
    use_scope = (basis_type or "").lower() not in ("all", "")
    if use_scope:
        scope = scope_from_params(
            basis_type  = basis_type,
            period      = period or None,
            year        = year   or None,
            from_period = from_period or None,
            to_period   = to_period   or None,
            all_stmts   = all_stmts,
        )
        if scope.get("error"):
            raise HTTPException(400, scope["error"])
        windowed = filter_by_scope(all_stmts, scope)
        scope_label = scope["label"]
    else:
        windowed    = filter_periods(all_stmts, window)
        scope       = None
        scope_label = window

    # ── 4. Analysis engine (Phase 5) ──────────────────────────────────────────
    analysis: dict = run_analysis(windowed)

    # ── 5. KPI block (Phase 7.6) ──────────────────────────────────────────────
    # FIX: build_kpi_block now uses windowed (not all_stmts) for KPI .value fields.
    # When basis_type scope is active (use_scope=True):
    #   pass windowed + window="ALL" so internal filter_periods is a no-op.
    # When legacy rolling window is used (use_scope=False):
    #   pass all_stmts + window so internal filter_periods applies the window.
    # Either way, enrich_kpi() now reads w_* (windowed series) correctly.
    if use_scope:
        kpi_block: dict = build_kpi_block(windowed, "ALL")
    else:
        kpi_block: dict = build_kpi_block(all_stmts, window)

    # ── 6. Advanced metrics (Phase 8) ─────────────────────────────────────────
    advanced_metrics: dict = {}
    try:
        advanced_metrics = compute_advanced_metrics(windowed, analysis.get("ratios", {}))
    except Exception as exc:
        logger.warning("advanced_metrics failed: %s", exc)
        advanced_metrics = {"error": "Internal processing error"}

    # ── 7. Cash flow engine (Phase 9) ─────────────────────────────────────────
    # MUST be computed before run_intelligence
    cashflow: dict = {}
    try:
        cashflow = build_cashflow(windowed)
    except Exception as exc:
        logger.warning("cashflow failed: %s", exc)
        cashflow = {"error": "Internal processing error"}

    # ── 8. Root Cause Engine (Phase 10) ──────────────────────────────────────
    root_cause: dict = {}
    try:
        root_cause = build_root_cause(analysis, cashflow)
    except Exception as exc:
        logger.warning("root_cause failed: %s", exc)
        root_cause = {"error": "Internal processing error"}

    # ── 9. Executive Interpretation Engine (Phase 11) ───────────────────────
    executive: dict = {}
    try:
        executive = build_executive_summary(analysis, advanced_metrics, cashflow, root_cause)
    except Exception as exc:
        logger.warning("executive_summary failed: %s", exc)
        executive = {"error": "Internal processing error"}

    # ── 10. Expense Intelligence Engine (Phase 12.5) ─────────────────────────
    expense_analysis: dict = {}
    try:
        expense_analysis = build_expense_breakdown(windowed)
    except Exception as exc:
        logger.warning("expense_breakdown failed: %s", exc)
        expense_analysis = {"error": "Internal processing error"}

    # ── 11. Annual / YTD Aggregation Layer (Phase 14) ─────────────────────────
    annual_layer: dict = {}
    try:
        annual_layer = build_annual_layer(all_stmts)
    except Exception as exc:
        logger.warning("annual_layer failed: %s", exc)
        annual_layer = {"error": "Internal processing error"}

    # ── FIX-1.1: health_score_v2 sourced exclusively from build_intelligence() ──
    # fin_intelligence.build_intelligence() is the SINGLE source of truth.
    # No parallel computation here — we call it once and read the result.
    health_v2: int = 0
    intelligence_block: dict = {}
    try:
        intelligence_block = build_intelligence(
            analysis     = analysis,
            annual_layer = annual_layer,
            currency     = company.currency or "",
        )
        health_v2 = intelligence_block.get("health_score_v2", 0)
    except Exception as exc:
        logger.warning("build_intelligence failed: %s", exc)
        health_v2 = 0
        intelligence_block = {}

    # advanced_metrics and cashflow are always defined before this call
    decision: dict = {}
    try:
        decision = run_intelligence(
            analysis,
            advanced_metrics=advanced_metrics,
            cashflow=cashflow,
            root_cause=root_cause,
        )
    except Exception as exc:
        logger.warning("run_intelligence failed: %s", exc)
        # Fallback: compute basic health score from raw metrics
        # so health_score is never 0 for a functioning company
        # FIX-2.3: health_score intentionally omitted from fallback.
        # health_score_v2 comes exclusively from build_intelligence() (already computed above).
        decision = {
            "insights": [], "warnings": [], "recommendations": [],
            "forecast": {"available": False, "reason": "Internal processing error"},
            "summary": {
                "total_insights": 0, "total_warnings": 0,
                "total_recommendations": 0,
                "health_score": None,  # FIX-2.3: use health_score_v2 only
                "top_risk": "Signal engine error",
                "top_opportunity": None,
            },
        }

    # ── 9. Debug block ────────────────────────────────────────────────────────
    fe_debug: dict = _build_debug_block(windowed)

    # ── 10. Validation Layer ──────────────────────────────────────────────────
    # Detects mismatches between pipeline stages. Never crashes.
    pipeline_validation: dict = {}
    try:
        pipeline_validation = _validate_pipeline(windowed, analysis, cashflow)
    except Exception as exc:
        logger.warning("pipeline_validation failed: %s", exc)
        pipeline_validation = {"consistent": None, "warnings": [], "error": "Internal processing error"}

    # ── 11. Debug full ────────────────────────────────────────────────────────
    debug_full = {
        "analysis_present":    bool(analysis),
        "cashflow_present":    bool(cashflow and not cashflow.get("error")),
        "adv_metrics_present": bool(advanced_metrics and not advanced_metrics.get("error")),
        "decision_insights":   len(decision.get("insights", [])),
        "decision_warnings":   len(decision.get("warnings", [])),
        "health_score":        health_v2,  # always from fin_intelligence
        "cashflow_ocf":        cashflow.get("operating_cashflow"),
        "root_cause_present":  bool(root_cause and not root_cause.get("error")),
        "executive_present":   bool(executive and not executive.get("error")),
        "expense_present":     bool(expense_analysis and not expense_analysis.get("error")),
        "forecast_available":  decision.get("forecast", {}).get("available"),
        "periods_in_window":   len(windowed),
        "pipeline_consistent": pipeline_validation.get("consistent"),
        "pipeline_warnings":   len(pipeline_validation.get("warnings", [])),
        "execution_order":     [
            "statement_engine", "analysis_engine", "cashflow_engine",
            "decision_engine", "executive_engine", "validation",
        ],
    }

    # ── Response ──────────────────────────────────────────────────────────────
    return {
        "pipeline_profile": {
            "is_canonical_product_path": False,
            "route": "GET /{company_id}",
            "notes": (
                "Legacy aggregate: run_intelligence + flat statements map. "
                "Canonical product data: GET /{company_id}/executive."
            ),
        },
        "company_id":        company_id,
        "company_name":      company.name,
        "data_source":       data_source,        # "direct_uploads" | "branch_consolidation"
        "window":            window,
        "scope":             scope,
        "scope_label":       scope_label,
        "health_score_v2":   health_v2,      # Phase 23 — unified health score
        "period_count":      len(windowed),
        "total_periods":     len(all_stmts),
        "periods":           [s["period"] for s in windowed],
        "all_periods":       [s["period"] for s in all_stmts],
        "available_windows": sorted(VALID_WINDOWS),
        "analysis":          analysis,
        "decision":          decision,
        "statements":        {s["period"]: s for s in windowed},
        "kpi_block":         kpi_block,
        "advanced_metrics":  advanced_metrics,
        "cashflow":          cashflow,
        "root_cause":        root_cause,
        "executive":         executive,
        "expense_analysis":  expense_analysis,
        "annual_layer":      annual_layer,
        "intelligence_v2":   intelligence_block,  # from fin_intelligence — contains health_score_v2, ratios, trends
        "debug":             fe_debug,
        "debug_full":        debug_full,
        "pipeline_validation": pipeline_validation,
        "intelligence": {
            "window":            window,
            "yoy_available":     len(all_stmts) >= 13,
            "mom_available":     len(windowed) >= 2,
            "full_year":         len(all_stmts) >= 12,
            "periods_in_window": len(windowed),
            "oldest_period":     all_stmts[0]["period"]  if all_stmts else None,
            "latest_period":     all_stmts[-1]["period"] if all_stmts else None,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 15 — What-If endpoint
# ══════════════════════════════════════════════════════════════════════════════

from pydantic import BaseModel, field_validator
from app.services.what_if import run_what_if

class WhatIfRequest(BaseModel):
    basis:             str   = "ytd"   # legacy: "latest_month"|"ytd"|"full_year"
    revenue_pct:       float = 0.0
    cogs_pct:          float = 0.0
    opex_pct:          float = 0.0
    year:              str   = ""      # legacy full_year selector
    # Phase 22 universal scope fields (override basis when set)
    scope_basis_type:  str   = ""      # month|year|ytd|custom
    scope_period:      str   = ""
    scope_year:        str   = ""
    scope_from_period: str   = ""
    scope_to_period:   str   = ""
    # Cashflow knob: modelled as proportional improvement to operating cashflow projection
    # A positive value reduces effective DSO, improving projected cashflow.
    collection_improvement_pct: float = 0.0

    @field_validator("basis")
    @classmethod
    def validate_basis(cls, v):
        # Allow empty/any value when scope_basis_type will be used instead
        # Only enforce when no scope override is present
        allowed = {"latest_month", "ytd", "full_year"}
        if v and v not in allowed:
            raise ValueError(f"basis must be one of {allowed}")
        return v or "ytd"   # default to ytd if empty


# ── GET /{company_id}/consolidated ───────────────────────────────────────────

@router.get("/{company_id}/consolidated")
def get_consolidated(
    company_id:  str,
    window:      str  = Query(default="ALL"),
    basis_type:  str  = Query(default="all"),
    period:      str  = Query(default=""),
    year:        str  = Query(default=""),
    from_period: str  = Query(default=""),
    to_period:   str  = Query(default=""),
    lang:        str  = Query(default="en"),
    db: Session = Depends(get_db),
):
    """
    Company financials derived entirely from branch Trial Balance uploads (TB-level consolidation).
    Merged branch TBs per period → classify → statements → same analysis pipeline as company scope.

    **Not the canonical product path** (Phase 1.1): different shape than
    ``GET /{company_id}/executive``. Use executive for Command Center / Statements /
    unified CFO decisions + structured bundle. See ``pipeline_profile`` in the JSON.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    all_stmts = _build_consolidated_statements(company_id, db)
    if not all_stmts:
        raise HTTPException(
            422,
            "No financial data uploaded yet (branch consolidation). Upload Trial Balances with a branch selected first.",
        )

    # Scope resolution (same as main endpoint)
    use_scope = (basis_type or "").lower() not in ("all", "")
    if use_scope:
        scope = scope_from_params(
            basis_type  = basis_type,
            period      = period or None,
            year        = year   or None,
            from_period = from_period or None,
            to_period   = to_period   or None,
            all_stmts   = all_stmts,
        )
        if scope.get("error"):
            raise HTTPException(400, scope["error"])
        windowed  = filter_by_scope(all_stmts, scope)
        scope_label = scope.get("label", basis_type)
    else:
        _win = window.upper() if window.upper() in VALID_WINDOWS else "ALL"
        windowed    = filter_periods(all_stmts, _win)
        scope       = {}
        scope_label = _win

    if not windowed:
        raise HTTPException(422, "No data in selected scope.")

    # Full analysis pipeline — reused exactly
    try:
        analysis = run_analysis(windowed)
    except Exception as exc:
        analysis = {}
        logger.warning("consolidated analysis failed: %s", exc)

    try:
        annual_layer = build_annual_layer(windowed)
    except Exception as exc:
        annual_layer = {}
        logger.warning("consolidated annual_layer failed: %s", exc)

    try:
        intelligence = build_intelligence(
            analysis     = analysis,
            annual_layer = annual_layer,
            currency     = company.currency or "",
        )
        health_v2 = intelligence.get("health_score_v2", 0)
    except Exception as exc:
        intelligence = {}
        health_v2    = 0
        logger.warning("consolidated intelligence failed: %s", exc)

    # Branch breakdown summary (canonical TB periods per branch)
    from app.api import branches as _branches_api
    from app.models.branch import Branch as _Branch

    branch_breakdown: list[dict] = []
    branches_q = (
        db.query(_Branch)
        .filter(_Branch.company_id == company_id, _Branch.is_active == True)  # noqa
        .all()
    )
    for b in branches_q:
        stmts_b = _branches_api._branch_statements_from_uploads(db, company_id, b.id)
        if not stmts_b:
            continue
        tr = sum(
            float((s.get("income_statement") or {}).get("revenue", {}).get("total") or 0)
            for s in stmts_b
        )
        branch_breakdown.append({
            "branch_id":   b.id,
            "branch_name": b.name,
            "branch_code": getattr(b, "code", None),
            "period_count": len(stmts_b),
            "periods":     [s.get("period") for s in stmts_b],
            "total_revenue": round(tr, 2),
        })

    safe_lang = lang if lang in ("en", "ar", "tr") else "en"
    deep_intel: dict = {}
    rc_consolidated: list = []
    dec_consolidated: list = []
    cfo_recommendations: list = []
    try:
        from app.services.deep_intelligence import build_deep_intelligence
        from app.services.root_cause_engine import build_root_causes, derive_phase43_metrics_trends

        deep_intel = build_deep_intelligence(windowed, analysis, safe_lang)
        _mc, _tc = derive_phase43_metrics_trends(windowed, analysis)
        rc_consolidated = build_root_causes(_mc, _tc, lang=safe_lang)
    except Exception as _cons_exc:
        logger.warning("consolidated financial brain failed: %s", _cons_exc)
    try:
        from app.services.alerts_engine import build_alerts
        from app.services.cfo_decision_engine import build_cfo_decisions

        raw_alerts = build_alerts(intelligence, lang=safe_lang).get("alerts", [])
        _dec_pack = build_cfo_decisions(
            intelligence,
            raw_alerts,
            lang=safe_lang,
            n_periods=len(windowed),
            analysis=analysis,
            branch_context=_branch_context_for_cfo_decisions(db, company_id),
        )
        dec_consolidated = _dec_pack.get("decisions", [])
        cfo_recommendations = _dec_pack.get("recommendations", [])
    except Exception as _dec_exc:
        logger.warning("consolidated CFO decisions failed: %s", _dec_exc)
        cfo_recommendations = []

    exec_forecast_consolidated: dict = {}
    try:
        exec_forecast_consolidated = _build_forecast(analysis, lang=safe_lang)
    except Exception as _efc_exc:
        logger.warning("consolidated forecast_engine failed: %s", _efc_exc)
        exec_forecast_consolidated = {"available": False, "reason": str(_efc_exc)}

    # ── Evidence blocks (additive) — consolidated financial brain payload ─────
    try:
        _resolver_cons = MetricResolver.from_statements(
            period_statements=windowed,
            scope="consolidated",
            window=(window.upper() if window and window.upper() in VALID_WINDOWS else "ALL"),  # type: ignore[arg-type]
            currency=(company.currency or "") if company else "",
            analysis=analysis,
            cashflow=None,  # not guaranteed in this route; keep deterministic but optional
        )
        if isinstance(deep_intel, dict):
            deep_intel.setdefault("evidence", {"meta": _resolver_cons.meta(), "quality": _resolver_cons.quality()})
        for rc in (rc_consolidated or []):
            dom = str(rc.get("domain") or rc.get("type") or "").lower()
            if dom in ("profitability", "profit"):
                rc["evidence"] = {"meta": _resolver_cons.meta(), "metrics": [{"key": k, **_resolver_cons.delta(k)} for k in ["net_profit", "net_margin_pct", "gross_margin_pct"]], "quality": _resolver_cons.quality()}
            elif dom in ("cashflow",):
                rc["evidence"] = {"meta": _resolver_cons.meta(), "metrics": [{"key": k, **_resolver_cons.delta(k)} for k in ["working_capital"]], "quality": _resolver_cons.quality()}
            elif dom in ("liquidity",):
                rc["evidence"] = {"meta": _resolver_cons.meta(), "metrics": [{"key": k, **_resolver_cons.delta(k)} for k in ["working_capital"]], "quality": _resolver_cons.quality()}
            elif dom in ("revenue", "growth"):
                rc["evidence"] = {"meta": _resolver_cons.meta(), "metrics": [{"key": k, **_resolver_cons.delta(k)} for k in ["revenue"]], "quality": _resolver_cons.quality()}
            elif dom in ("cost", "cost_structure", "expenses"):
                rc["evidence"] = {"meta": _resolver_cons.meta(), "metrics": [{"key": k, **_resolver_cons.delta(k)} for k in ["total_cost_ratio_pct", "operating_expenses", "cogs_ratio_pct"]], "quality": _resolver_cons.quality()}
        for d in (dec_consolidated or []):
            dom = str(d.get("domain") or "").lower()
            keys = ["revenue", "net_profit", "total_cost_ratio_pct"]
            if dom in ("profitability", "profit"):
                keys = ["net_profit", "net_margin_pct", "gross_margin_pct"]
            elif dom in ("revenue", "growth"):
                keys = ["revenue", "net_profit"]
            d["evidence"] = {"meta": _resolver_cons.meta(), "metrics": [{"key": k, **_resolver_cons.delta(k)} for k in keys], "quality": _resolver_cons.quality()}
    except Exception:
        pass

    return {
        "pipeline_profile": {
            "is_canonical_product_path": False,
            "route": "GET /{company_id}/consolidated",
            "notes": (
                "Branch consolidation summary payload — not GET /executive. "
                "Canonical UI bundle: GET /{company_id}/executive."
            ),
        },
        "company_id":       company_id,
        "company_name":     company.name,
        "data_source":      "branch_consolidation",
        "window":           window,
        "scope":            scope,
        "scope_label":      scope_label,
        "lang":             safe_lang,
        "health_score_v2":  health_v2,
        "period_count":     len(windowed),
        "total_periods":    len(all_stmts),
        "periods":          [s["period"] for s in windowed],
        "all_periods":      [s["period"] for s in all_stmts],
        "analysis":         analysis,
        "intelligence_v2":  intelligence,
        "annual_layer":     annual_layer,
        "statements":       {s["period"]: s for s in windowed},
        "branch_breakdown": branch_breakdown,
        "deep_intelligence":      deep_intel,
        "phase43_root_causes":    rc_consolidated,
        "cfo_decisions":          dec_consolidated,
        "cfo_recommendations":    cfo_recommendations,
        "forecast":               exec_forecast_consolidated,
        "note": (
            "Financial data consolidated from merged branch trial balances per period "
            "(TB-level consolidation → same statement builders as company scope)."
        ),
    }


# ── GET /{company_id}/analysis-summary ───────────────────────────────────────


def _reconciliation_warning(
    main_stmts: list[dict],
    branch_stmts: list[dict],
    tolerance_pct: float = 10.0,
    *,
    lang: str = "en",
) -> dict:
    """
    Compare MAIN entity latest-period figures against sum of branch consolidated figures.
    Returns a reconciliation warning dict if divergence exceeds tolerance.

    This is a transparency layer only — numbers are never changed.
    Divergence is expected due to: intercompany eliminations, holding entries,
    separate legal entity structures, or incomplete branch uploads.
    """
    if not main_stmts or not branch_stmts:
        return {"consolidation_warning": False}

    # Latest period of each
    m_is  = main_stmts[-1].get("income_statement", {})
    b_is  = branch_stmts[-1].get("income_statement", {})

    m_rev  = m_is.get("revenue", {}).get("total", 0) or 0
    b_rev  = b_is.get("revenue", {}).get("total", 0) or 0
    m_np   = m_is.get("net_profit", 0) or 0
    b_np   = b_is.get("net_profit", 0) or 0

    def _gap(main_v, branch_v):
        if not main_v:
            return None, None
        diff = branch_v - main_v
        pct  = round(diff / abs(main_v) * 100, 1)
        return round(diff, 0), pct

    rev_diff, rev_pct  = _gap(m_rev, b_rev)
    np_diff,  np_pct   = _gap(m_np,  b_np)

    # Warn if either diverges beyond tolerance
    rev_warn = rev_pct is not None and abs(rev_pct) > tolerance_pct
    np_warn  = np_pct  is not None and abs(np_pct)  > tolerance_pct

    if not rev_warn and not np_warn:
        return {"consolidation_warning": False}

    def _fmt(v):
        if v is None: return "N/A"
        av = abs(v)
        return f"{av/1e6:.2f}M" if av >= 1e6 else f"{av/1e3:.0f}K"

    return reconciliation_warning_payload(
        lang=lang,
        rev_warn=rev_warn,
        np_warn=np_warn,
        main_rev_fmt=_fmt(m_rev),
        branch_rev_fmt=_fmt(b_rev),
        rev_gap_pct=rev_pct,
        main_np_fmt=_fmt(m_np),
        branch_np_fmt=_fmt(b_np),
        np_gap_pct=np_pct,
    )


@router.get("/{company_id}/analysis-summary")
def get_analysis_summary(
    company_id:  str,
    window:      str  = Query(default="ALL", description="Analysis window: 3M | 6M | 12M | YTD | ALL"),
    basis_type:  str  = Query(default="all"),
    period:      str  = Query(default=""),
    year:        str  = Query(default=""),
    from_period: str  = Query(default=""),
    to_period:   str  = Query(default=""),
    consolidate: bool = Query(default=False),
    lang:        str  = Query(default="en", description="Locale for alerts, Phase-43 narratives, decisions: en | ar | tr"),
    db: Session = Depends(get_db),
):
    """
    Canonical CFO-grade analysis object.

    Assembles ratios, structured trends (with direction labels), alerts, and
    root causes from the existing pipeline — no duplicate logic, no new engines.

    Operating cashflow trend uses build_cashflow().series — same source as executive.

    Schema:
    {
      company_id, data_source, period_count, periods, latest_period,
      ratios:      { profitability, liquidity, leverage, efficiency },
      trends:      { revenue, net_profit, gross_margin, expenses, operating_cashflow },
      alerts:      [ { type, severity, title, reason, source_metrics } ],
      root_causes: [ { domain, title, direction, explanation, source_metrics } ],
    }
    """
    from app.services.analysis_engine   import run_analysis, _trend_direction
    from app.services.cashflow_engine   import build_cashflow
    from app.services.alerts_engine     import build_alerts
    from app.services.root_cause_engine import build_root_cause
    from app.services.fin_intelligence  import build_intelligence
    from app.services.period_aggregation import build_annual_layer

    _req_lang = (lang or "en").strip().lower()
    safe_lang = normalize_narrative_lang(lang)
    locale_fallback = _req_lang not in ("en", "ar", "tr")
    _debug: dict = {}

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    # ── Statements: direct or consolidated ───────────────────────────────────
    uploads = []
    if consolidate:
        all_stmts = _build_consolidated_statements(company_id, db)
        if not all_stmts:
            raise HTTPException(422, "No financial data uploaded yet (branch consolidation).")
        data_source = "branch_consolidation"
    else:
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None),
            )
            .order_by(TrialBalanceUpload.uploaded_at.asc())
            .all()
        )
        if not uploads:
            raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")
        all_stmts = _build_period_statements(company_id, uploads)
        if not all_stmts:
            raise HTTPException(422, "Could not build statements.")
        data_source = "direct_uploads"

    # ── Scope/window filtering — EXACT same logic as get_analysis() / get_intelligence() ──
    if (basis_type or "").lower() not in ("all", ""):
        scope22 = scope_from_params(basis_type, period or None, year or None,
                                    from_period or None, to_period or None, all_stmts)
        if scope22.get("error"):
            raise HTTPException(400, scope22["error"])
        windowed = filter_by_scope(all_stmts, scope22)
    else:
        windowed = filter_periods(all_stmts, window.upper() if window.upper() in VALID_WINDOWS else "ALL")

    # ── Core analysis ─────────────────────────────────────────────────────────
    analysis  = run_analysis(windowed)
    latest_r  = analysis.get("latest") or {}
    trends_r  = analysis.get("trends") or {}
    prof      = latest_r.get("profitability", {})

    # ── Cashflow — reuse build_cashflow().series (same path as executive) ─────
    cf_series: list = []
    cf_mom:    list = []
    try:
        cf_raw    = build_cashflow(windowed)
        cf_ser    = cf_raw.get("series", {})
        cf_series = cf_ser.get("operating_cashflow", [])
        # Compute MoM for cashflow series (same formula used everywhere)
        cf_mom = [None]
        for i in range(1, len(cf_series)):
            prev = cf_series[i - 1]
            curr = cf_series[i]
            if prev and prev != 0:
                cf_mom.append(round((curr - prev) / abs(prev) * 100, 2))
            else:
                cf_mom.append(None)
    except Exception as exc:
        logger.warning("analysis-summary cashflow failed: %s", exc)
        _debug["cashflow_error"] = str(exc)

    # ── Metric Resolver (foundation for evidence/confidence/attribution) ─────
    # Additive only: used for evidence blocks; no changes to existing fields.
    _resolver: Optional[MetricResolver] = None
    try:
        _win_norm = (window.upper() if window and window.upper() in VALID_WINDOWS else "ALL")
        _resolver = MetricResolver.from_statements(
            period_statements=windowed,
            scope=("consolidated" if consolidate else "company"),
            window=_win_norm,  # type: ignore[arg-type]
            currency=(company.currency or "") if company else "",
            analysis=analysis,
            cashflow=(cf_raw if "cf_raw" in locals() else None),
        )
    except Exception:
        _resolver = None

    # ── Alerts — from existing engine, normalize severity in aggregation layer ─
    intel = {}
    try:
        annual = build_annual_layer(windowed)
        intel  = build_intelligence(analysis=analysis, annual_layer=annual, currency=company.currency or "")
        raw_alerts = build_alerts(intel, lang=safe_lang).get("alerts", [])
    except Exception as exc:
        logger.warning("analysis-summary alerts/intelligence failed: %s", exc)
        _debug["alerts_intelligence_error"] = str(exc)
        raw_alerts = []

    # Normalize severity: map any non-standard values to high/medium/low
    SEV_MAP = {"critical": "high", "warning": "medium", "info": "low",
               "high": "high", "medium": "medium", "low": "low"}
    alerts = [
        {
            "type":           a.get("id", a.get("type", "unknown")),
            "severity":       SEV_MAP.get(str(a.get("severity", "medium")).lower(), "medium"),
            "title":          a.get("title", ""),
            "reason":         a.get("message", a.get("reason", "")),
            "source_metrics": a.get("source_metrics", []),
        }
        for a in raw_alerts
    ]

    # ── Root causes — add source_metrics in aggregation layer ─────────────────
    try:
        # Phase 10 root cause block (domain-keyed dict under one object)
        rc_raw = build_root_cause(analysis, cf_raw if "cf_raw" in locals() else {})
        # Extract each domain as a cause entry with source_metrics
        DOMAIN_METRICS = {
            "revenue":        ["revenue_mom_pct", "yoy_revenue_pct", "revenue_series"],
            "profit":         ["net_margin_pct", "revenue_mom_pct", "gross_margin_pct"],
            "cashflow":       ["operating_cashflow", "working_capital_change"],
            "cost_structure": ["expense_ratio", "cogs_series", "expenses_mom_pct"],
        }
        root_causes = []
        for domain, metrics in DOMAIN_METRICS.items():
            rc = rc_raw.get(domain)
            if not rc or not isinstance(rc, dict):
                continue
            key    = rc.get("key", "")
            trend  = rc.get("trend", "stable")
            sev    = rc.get("severity", "low")
            drv    = rc.get("drivers", [])
            # Use first driver detail if available, else use the key as explanation
            detail = drv[0].get("key", key) if drv else key
            root_causes.append({
                "domain":         domain,
                "title":          key,
                "direction":      trend if trend in ("improving", "deteriorating", "stable") else "neutral",
                "explanation":    detail,
                "source_metrics": metrics,
                # Evidence-first upgrade (additive)
                "evidence": (None if not _resolver else {
                    "meta": _resolver.meta(),
                    "metrics": [
                        {"key": mk, **_resolver.delta(mk)}
                        for mk in (
                            ["revenue"] if domain == "revenue" else
                            ["net_profit", "net_margin_pct", "gross_margin_pct"] if domain == "profit" else
                            ["operating_cashflow", "working_capital"] if domain == "cashflow" else
                            ["total_cost_ratio_pct", "operating_expenses"] if domain == "cost_structure" else
                            []
                        )
                    ],
                    "quality": _resolver.quality(),
                }),
            })
    except Exception as exc:
        logger.warning("root_causes failed: %s", exc)
        root_causes = []

    # ── Phase 43 intelligence layer ─────────────────────────────────────────────
    # Metrics and trends sourced ONLY from variables already computed above.
    # No recalculation. No new DB queries. Fallback to empty lists on any error.
    root_causes_v2: list = []
    anomalies:      list = []
    narratives:     list = []
    try:
        def _last_valid(series):
            """Return last non-None value from a MoM series, or None."""
            valid = [x for x in (series or []) if x is not None]
            return valid[-1] if valid else None

        # Derive ratios from latest statement snapshot when available
        _latest_stmt = windowed[-1] if windowed else {}
        _is = _latest_stmt.get("income_statement", {}) if isinstance(_latest_stmt, dict) else {}
        _rev = (_is.get("revenue", {}) or {}).get("total")
        _cogs = (_is.get("cogs", {}) or {}).get("total")
        _exp = (_is.get("expenses", {}) or {}).get("total")
        _unc = float((_is.get("unclassified_pnl_debits") or {}).get("total") or 0)

        _opex_ratio = opex_ratio_pct(
            float(_exp) if _exp is not None else None,
            float(_rev) if _rev is not None else None,
        )
        _cogs_ratio = cogs_ratio_pct(
            float(_cogs) if _cogs is not None else None,
            float(_rev) if _rev is not None else None,
        )
        _total_cost_ratio = total_cost_ratio_pct(
            float(_cogs) if _cogs is not None else None,
            float(_exp) if _exp is not None else None,
            float(_rev) if _rev is not None else None,
            _unc,
        )
        _expense_ratio = _total_cost_ratio

        # Ratio time series (per period): total cost vs revenue, cogs vs revenue
        _exp_ratio_series = []
        _cogs_ratio_series = []
        _nm_series = []
        for _s in (windowed or []):
            _is_s = (_s.get("income_statement") or {}) if isinstance(_s, dict) else {}
            _r = ((_is_s.get("revenue", {}) or {}).get("total"))
            _e = ((_is_s.get("expenses", {}) or {}).get("total"))
            _cg = ((_is_s.get("cogs", {}) or {}).get("total"))
            _u = float((_is_s.get("unclassified_pnl_debits") or {}).get("total") or 0)
            _nm = _is_s.get("net_margin_pct")
            _exp_ratio_series.append(
                total_cost_ratio_pct(
                    float(_cg) if _cg is not None else None,
                    float(_e) if _e is not None else None,
                    float(_r) if _r is not None else None,
                    _u,
                )
            )
            _cogs_ratio_series.append(
                cogs_ratio_pct(
                    float(_cg) if _cg is not None else None,
                    float(_r) if _r is not None else None,
                )
            )
            _nm_series.append(float(_nm) if _nm is not None else None)

        def _mom_series(series: list) -> list:
            out = [None]
            for i in range(1, len(series)):
                prev = series[i - 1]
                curr = series[i]
                if prev is None or curr is None or prev == 0:
                    out.append(None)
                else:
                    out.append(round((curr - prev) / abs(prev) * 100, 2))
            return out

        _total_cost_ratio_mom = _last_valid(_mom_series(_exp_ratio_series))
        _cogs_ratio_mom = _last_valid(_mom_series(_cogs_ratio_series))
        _net_margin_mom = _last_valid(_mom_series(_nm_series))

        _p43_metrics = {
            "net_margin_pct": prof.get("net_margin_pct"),
            "opex_ratio_pct":    _opex_ratio,
            "cogs_ratio_pct":    _cogs_ratio,
            "total_cost_ratio_pct": _total_cost_ratio,
            "expense_ratio":     _expense_ratio,
            "cogs_ratio":        _cogs_ratio,
        }
        _p43_trends = {
            "revenue_mom":       _last_valid(trends_r.get("revenue_mom_pct")),
            "net_profit_mom":    _last_valid(trends_r.get("net_profit_mom_pct")),
            "opex_mom_pct":      _last_valid(trends_r.get("expenses_mom_pct")),
            "expense_ratio_mom": _last_valid(trends_r.get("expenses_mom_pct")),
            "total_cost_ratio_mom": _total_cost_ratio_mom,
            "cogs_ratio_mom":    _cogs_ratio_mom,
            "net_margin_mom":    _net_margin_mom,
        }
        root_causes_v2 = build_root_causes(_p43_metrics, _p43_trends, lang=safe_lang)
        anomalies      = detect_anomalies(_p43_metrics, _p43_trends, lang=safe_lang)
        narratives     = build_narratives(root_causes_v2, anomalies, lang=safe_lang)
    except Exception as _p43_exc:
        logger.warning("phase43 intelligence failed: %s", _p43_exc)
        _debug["phase43_error"] = str(_p43_exc)

    # ── Structured trends with direction labels ───────────────────────────────
    def _trend_quality(mom_series: list) -> str:
        """
        Assess trend signal quality.
        volatile: mixed positive/negative last 2 valid MoM values
        stable:   consistent direction or insufficient data
        """
        valid = [x for x in (mom_series or []) if x is not None]
        if len(valid) < 2:
            return "stable"
        last_two = valid[-2:]
        if (last_two[0] > 0.5 and last_two[1] < -0.5) or (last_two[0] < -0.5 and last_two[1] > 0.5):
            return "volatile"
        return "stable"

    def _make_trend(series_key, mom_key, yoy_key=None):
        series  = trends_r.get(series_key, [])
        mom     = trends_r.get(mom_key, [])
        vals    = [v for v in series if v is not None]
        # loss_flag: true if latest value is negative (net_profit < 0)
        loss_flag = bool(vals and vals[-1] < 0)
        return {
            "series":        series,
            "mom_pct":       mom,
            "yoy_pct":       trends_r.get(yoy_key) if yoy_key else None,
            "direction":     _trend_direction(mom),
            "trend_quality": _trend_quality(mom),
            "loss_flag":     loss_flag,
        }

    structured_trends = {
        "revenue":      _make_trend("revenue_series",           "revenue_mom_pct",       "yoy_revenue_pct"),
        "net_profit":   _make_trend("net_profit_series",        "net_profit_mom_pct",    "yoy_net_profit_pct"),
        "gross_margin": _make_trend("gross_margin_series",      "gross_margin_mom_pct"),
        "expenses":     _make_trend("expenses_series",          "expenses_mom_pct"),
        "operating_cashflow": {
            "series":    [round(v, 2) if v else None for v in cf_series],
            "mom_pct":   cf_mom,
            "yoy_pct":   None,
            "direction": _trend_direction(cf_mom),
            "trend_quality": _trend_quality(cf_mom),
        },
    }

    for _tk in ("revenue", "net_profit", "gross_margin", "expenses", "operating_cashflow"):
        enrich_trend_object(structured_trends.get(_tk), safe_lang)

    # ── Metric Resolver shadow-mode comparisons (log-only) ────────────────────
    try:
        _win_norm = (window.upper() if window and window.upper() in VALID_WINDOWS else "ALL")
        _resolver = MetricResolver.from_statements(
            period_statements=windowed,
            scope=("consolidated" if consolidate else "company"),
            window=_win_norm,  # type: ignore[arg-type]
            currency=(company.currency or "") if company else "",
            analysis=analysis,
            cashflow=(cf_raw if "cf_raw" in locals() else None),
        )

        _latest_stmt = windowed[-1] if windowed else {}
        _is = (_latest_stmt.get("income_statement") or {}) if isinstance(_latest_stmt, dict) else {}
        _rev_latest = ((_is.get("revenue", {}) or {}).get("total"))
        _np_latest = (_is.get("net_profit"))
        _exp_latest = ((_is.get("expenses", {}) or {}).get("total"))
        _gm_latest = _is.get("gross_margin_pct")
        _nm_latest = _is.get("net_margin_pct")

        _liq = latest_r.get("liquidity", {}) if isinstance(latest_r, dict) else {}
        _cur_view = {
            "revenue": _rev_latest,
            "net_profit": _np_latest,
            "net_margin_pct": _nm_latest,
            "gross_margin_pct": _gm_latest,
            "operating_expenses": _exp_latest,
            "total_cost_ratio_pct": _is.get("total_cost_ratio_pct"),
            "current_ratio": _liq.get("current_ratio"),
            "working_capital": _liq.get("working_capital"),
            "operating_cashflow": ((cf_raw.get("operating_cashflow") if isinstance(cf_raw, dict) else None) if "cf_raw" in locals() else None),
        }
        # Normalize nested ratio structures that come from extract_ratios() layer
        for _k in ("current_ratio", "working_capital"):
            v = _cur_view.get(_k)
            if isinstance(v, dict) and "value" in v:
                _cur_view[_k] = v.get("value")

        _shadow_compare_metrics(resolver=_resolver, current=_cur_view, label="analysis-summary")
    except Exception:
        pass

    # ── Canonical response ────────────────────────────────────────────────────
    liq   = latest_r.get("liquidity", {})
    lev   = latest_r.get("leverage", {})
    eff   = latest_r.get("efficiency", {})

    # ── Reconciliation: compare MAIN vs branch sum regardless of consolidate flag ─
    reconciliation: dict = {"consolidation_warning": False}
    try:
        if consolidate:
            # Already on consolidated path — compare against MAIN direct uploads
            main_uploads = (
                db.query(TrialBalanceUpload)
                .filter(
                    TrialBalanceUpload.company_id == company_id,
                    TrialBalanceUpload.status == "ok",
                    TrialBalanceUpload.branch_id.is_(None),
                )
                .order_by(TrialBalanceUpload.uploaded_at.asc())
                .all()
            )
            if main_uploads:
                main_stmts = _build_period_statements(company_id, main_uploads)
                reconciliation = _reconciliation_warning(main_stmts, all_stmts, lang=safe_lang)
        else:
            # On MAIN path — compare against branch consolidation
            branch_stmts = _build_consolidated_statements(company_id, db)
            if branch_stmts:
                reconciliation = _reconciliation_warning(all_stmts, branch_stmts, lang=safe_lang)
    except Exception as _exc:
        logger.warning("reconciliation check failed: %s", _exc)

    # ── Branch Expense Intelligence ───────────────────────────────────────────
    branch_intelligence: dict = {"expense_breakdown": [], "expense_insights": [], "top_movers": []}
    try:
        from app.services.branch_expense_intelligence import build_branch_expense_intelligence
        from app.models.branch import Branch as _BranchModel

        _branches_active = (
            db.query(_BranchModel)
            .filter(_BranchModel.company_id == company_id, _BranchModel.is_active == True)  # noqa
            .all()
        )
        _branch_upload_map = []
        for _b in _branches_active:
            _b_uploads = (
                db.query(TrialBalanceUpload)
                .filter(
                    TrialBalanceUpload.branch_id == _b.id,
                    TrialBalanceUpload.status == "ok",
                )
                .order_by(TrialBalanceUpload.uploaded_at.asc())
                .all()
            )
            if _b_uploads:
                _branch_upload_map.append({
                    "branch_id":   _b.id,
                    "branch_name": _b.name,
                    "uploads":     _b_uploads,
                })
        if _branch_upload_map:
            branch_intelligence = build_branch_expense_intelligence(
                _branch_upload_map, _load_df, lang=safe_lang
            )
    except Exception as _bei_exc:
        logger.warning("branch_expense_intelligence failed: %s", _bei_exc)

    # ── Validation block (Task 5) ───────────────────────────────────────────────
    # Build the structured validation block for this entity's statements.
    # tb_debit/credit come from upload metadata stored in the DB.
    try:
        from app.services.reconciliation_engine import build_validation_block
        _last_upload = uploads[-1] if uploads else None
        _tb_debit  = float(_last_upload.total_debit  or 0) if _last_upload else None
        _tb_credit = float(_last_upload.total_credit or 0) if _last_upload else None
        _validation = build_validation_block(
            stmts        = all_stmts,
            tb_debit     = _tb_debit,
            tb_credit    = _tb_credit,
            branch_stmts_list = None,   # populated by reconciliation path below
        )
    except Exception as _ve:
        logger.warning("validation block failed: %s", _ve)
        _validation = {"status": "WARNING", "blocking": False, "all_pass": None, "errors": [], "warnings": ["validation engine error"], "details": {}}

    # ── Decisions (if intelligence is available in this path) ─────────────────
    decisions_out: list = []
    decisions_summary: dict = {}
    decisions_recommendations: list = []
    try:
        if intel:
            from app.services.cfo_decision_engine import build_cfo_decisions
            dec_result = build_cfo_decisions(
                intelligence=intel,
                alerts=raw_alerts,
                lang=safe_lang,
                n_periods=analysis.get("period_count", 0) or 0,
                analysis=analysis,
                branch_context=_branch_context_for_cfo_decisions(db, company_id),
            )
            decisions_out = dec_result.get("decisions", []) or []
            decisions_summary = dec_result.get("summary", {}) or {}
            decisions_recommendations = dec_result.get("recommendations", []) or []
        else:
            _debug["decisions_skipped"] = True
            decisions_recommendations = []
    except Exception as exc:
        logger.warning("analysis-summary decisions failed: %s", exc)
        _debug["decisions_error"] = str(exc)
        decisions_recommendations = []

    # ── Evidence blocks (additive) ────────────────────────────────────────────
    def _evidence_for_keys(keys: list[str]) -> Optional[dict]:
        if not _resolver:
            return None
        return {
            "meta": _resolver.meta(),
            "metrics": [{"key": k, **_resolver.delta(k)} for k in keys],
            "quality": _resolver.quality(),
        }

    def _confidence_for(keys: list[str]) -> Optional[dict]:
        if not _resolver:
            return None
        q = _resolver.quality()
        missing = sum(q.get("missing_points", {}).get(k, 0) for k in keys)
        approx = bool(q.get("approximated"))
        denom = bool(q.get("denominator_risks"))
        volatile = any(_resolver.trend_quality(k) == "volatile" for k in keys if k in ("revenue", "net_profit", "operating_expenses", "operating_cashflow"))
        return score_confidence(
            n_periods=int(q.get("n_periods") or 0),
            missing_points=int(missing or 0),
            approximated=approx,
            volatile=volatile,
            denom_risk=denom,
        )

    # Attach evidence to decisions
    try:
        for d in (decisions_out or []):
            dom = str(d.get("domain") or "").lower()
            if dom in ("liquidity",):
                keys = ["current_ratio", "quick_ratio", "working_capital"]
                d["evidence"] = _evidence_for_keys(keys)
                d["confidence"] = _confidence_for(keys)
            elif dom in ("cashflow",):
                keys = ["operating_cashflow", "working_capital"]
                d["evidence"] = _evidence_for_keys(keys)
                d["confidence"] = _confidence_for(keys)
            elif dom in ("profitability", "profit"):
                keys = ["net_profit", "net_margin_pct", "gross_margin_pct"]
                d["evidence"] = _evidence_for_keys(keys)
                d["confidence"] = _confidence_for(keys)
                # Deterministic one-step attribution (additive)
                if _resolver:
                    d["attribution"] = profit_bridge_attribution(
                        revenue_delta=_resolver.delta("revenue").get("delta"),
                        prior_net_margin_pct=_resolver.delta("net_margin_pct").get("previous"),
                        cogs_ratio_delta_pct=_resolver.delta("cogs_ratio_pct").get("delta"),
                        opex_ratio_delta_pct=_resolver.delta("opex_ratio_pct").get("delta"),
                        latest_revenue=_resolver.delta("revenue").get("current"),
                        observed_net_profit_delta=_resolver.delta("net_profit").get("delta"),
                    )
            elif dom in ("growth", "revenue"):
                keys = ["revenue", "net_profit"]
                d["evidence"] = _evidence_for_keys(keys)
                d["confidence"] = _confidence_for(keys)
            elif dom in ("efficiency",):
                keys = ["ccc_days", "dso_days", "dpo_days", "dio_days"]
                d["evidence"] = _evidence_for_keys(keys)
                d["confidence"] = _confidence_for(keys)
            else:
                # Default: revenue + profit context
                keys = ["revenue", "net_profit", "total_cost_ratio_pct"]
                d["evidence"] = _evidence_for_keys(keys)
                d["confidence"] = _confidence_for(keys)
    except Exception:
        pass

    # Attach evidence to Phase 43 root causes list (already additive in response)
    try:
        for rc in (root_causes_v2 or []):
            dom = str(rc.get("domain") or rc.get("type") or "").lower()
            if dom in ("profitability", "profit"):
                keys = ["net_profit", "net_margin_pct", "gross_margin_pct"]
                rc["evidence"] = _evidence_for_keys(keys)
                rc["confidence"] = _confidence_for(keys)
            elif dom in ("liquidity",):
                keys = ["current_ratio", "quick_ratio", "working_capital"]
                rc["evidence"] = _evidence_for_keys(keys)
                rc["confidence"] = _confidence_for(keys)
            elif dom in ("cashflow",):
                keys = ["operating_cashflow", "working_capital"]
                rc["evidence"] = _evidence_for_keys(keys)
                rc["confidence"] = _confidence_for(keys)
            elif dom in ("revenue", "growth"):
                keys = ["revenue"]
                rc["evidence"] = _evidence_for_keys(keys)
                rc["confidence"] = _confidence_for(keys)
            elif dom in ("cost", "cost_structure", "expenses"):
                keys = ["total_cost_ratio_pct", "operating_expenses", "cogs_ratio_pct"]
                rc["evidence"] = _evidence_for_keys(keys)
                rc["confidence"] = _confidence_for(keys)
            else:
                # If the engine already provided source_metrics, honor them when possible
                src = rc.get("source_metrics") or []
                keys = [k for k in src if isinstance(k, str)]
                use = keys[:4] if keys else ["revenue", "net_profit"]
                rc["evidence"] = _evidence_for_keys(use)
                rc["confidence"] = _confidence_for(use)
    except Exception:
        pass

    return {
        "company_id":   company_id,
        "company_name": company.name,
        "lang":         safe_lang,
        "locale_requested": lang,
        "locale_fallback": locale_fallback,
        "data_source":  data_source,
        **reconciliation,
        "validation":   _validation,
        "debug":        (_debug or None),
        "period_count": analysis.get("period_count", 0),
        "periods":      analysis.get("periods", []),
        "latest_period": (analysis.get("periods") or [""])[-1],

        "ratios": {
            "profitability": {
                "gross_margin_pct":     prof.get("gross_margin_pct"),
                "net_margin_pct":       prof.get("net_margin_pct"),
                "operating_margin_pct": prof.get("operating_margin_pct"),
                "ebitda_margin_pct":    prof.get("ebitda_margin_pct"),
            },
            "liquidity": {
                "current_ratio":   liq.get("current_ratio"),
                "quick_ratio":     liq.get("quick_ratio"),
                "working_capital": liq.get("working_capital"),
            },
            "leverage": {
                "debt_to_equity":    lev.get("debt_to_equity"),
                "total_liabilities": lev.get("total_liabilities"),
                "total_equity":      lev.get("total_equity"),
            },
            "efficiency": {
                "inventory_turnover": eff.get("inventory_turnover"),
                "dso_days":           eff.get("dso_days"),
                "dpo_days":           eff.get("dpo_days"),
                "ccc_days":           eff.get("ccc_days"),
            },
        },

        "trends":      structured_trends,
        "alerts":      alerts,
        "root_causes": root_causes,
        "decisions":   decisions_out,
        "decisions_summary": decisions_summary,
        "recommendations": decisions_recommendations,

        # ── Phase 43 + branch intelligence (append-only) ─────────────────────
        "root_causes_v2":      root_causes_v2,
        "anomalies":           anomalies,
        "narratives":          narratives,
        "branch_intelligence": branch_intelligence,
    }


# ── GET /{company_id}/decisions-v2 ───────────────────────────────────────────

# Domain → owner_scope mapping (V2: cfo | branch_manager | operations)
_DOMAIN_OWNER = {
    "liquidity":     "cfo",
    "profitability": "cfo",
    "cashflow":      "cfo",
    "revenue":       "cfo",
    "growth":        "cfo",
    "cost":          "operations",
    "efficiency":    "operations",
    "expenses":      "operations",
    "leverage":      "cfo",
}

# Branch action key → domain + owner_scope
_ACTION_DOMAIN = {
    "reduce_expenses":    ("cost",          "operations"),
    "improve_margin":     ("profitability", "branch_manager"),
    "scale_revenue":      ("revenue",       "branch_manager"),
    "investigate_decline":("revenue",       "cfo"),
    "investigate_loss":   ("profitability", "cfo"),
    "maintain_growth":    ("growth",        "branch_manager"),
}

# Priority → time_horizon
_TIME_HORIZON = {"high": "immediate", "medium": "short", "low": "medium"}


def _enrich_company_decision(d: dict) -> dict:
    """Map existing cfo_decision_engine output → canonical V2 decision schema."""
    domain   = d.get("domain", "profitability")
    urgency  = d.get("urgency", "medium")
    # urgency from existing engine: "high" | "medium" | "low" (already matches priority levels)
    priority = urgency if urgency in ("high", "medium", "low") else "medium"
    owner    = _DOMAIN_OWNER.get(domain.lower(), "cfo")
    horizon  = _TIME_HORIZON.get(priority, "short")

    # source_metrics: derive from domain
    DOMAIN_METRICS_MAP = {
        "liquidity":     ["current_ratio", "quick_ratio", "working_capital"],
        "profitability": ["net_margin_pct", "gross_margin_pct", "operating_margin_pct"],
        "cashflow":      ["operating_cashflow", "working_capital_change"],
        "revenue":       ["revenue_mom_pct", "yoy_revenue_pct"],
        "efficiency":    ["dso_days", "dpo_days", "ccc_days"],
        "leverage":      ["debt_to_equity", "total_liabilities"],
        "cost":          ["expense_ratio", "cogs_series"],
        "growth":        ["revenue_mom_pct", "net_profit_mom_pct"],
    }
    source_metrics = DOMAIN_METRICS_MAP.get(domain.lower(), ["net_margin_pct", "revenue_mom_pct"])

    # Conservative qualitative impact — use existing engine's impact text as-is
    impact = d.get("impact", "")

    return {
        "title":          d.get("title", ""),
        "priority":       priority,
        "domain":         domain,
        "reason":         d.get("rationale", ""),
        "impact":         impact,
        "time_horizon":   horizon,
        "owner_scope":    owner,
        "source_metrics": source_metrics,
        "scope":          "company",
    }


def _build_branch_decisions(branch_data: list, lang: str = "en") -> list:
    """
    Convert branch_intelligence profile.actions into structured V2 decisions.
    Each branch action already has: priority, action (key), detail (localised text).
    """
    decisions = []
    for b in branch_data:
        if not b.get("has_data"):
            continue
        branch_id   = b.get("branch_id", "")
        branch_name = b.get("branch_name", "")
        kpis        = b.get("kpis", {})
        flags       = b.get("flags", {})
        actions     = b.get("profile", {}).get("actions", [])

        for act in actions:
            priority   = act.get("priority", "medium")
            action_key = act.get("action", "")
            detail     = act.get("detail", "")

            domain, owner = _ACTION_DOMAIN.get(action_key, ("operations", "branch_manager"))
            horizon       = _TIME_HORIZON.get(priority, "short")

            # Source metrics — from action key
            ACTION_METRICS = {
                "reduce_expenses":     ["expense_ratio", "net_margin_pct"],
                "improve_margin":      ["net_margin_pct", "gross_margin_pct"],
                "scale_revenue":       ["revenue_mom_pct", "net_margin_pct"],
                "investigate_decline": ["revenue_mom_pct", "revenue_series"],
                "investigate_loss":    ["net_margin_pct", "net_profit"],
                "maintain_growth":     ["revenue_mom_pct"],
            }
            source_metrics = ACTION_METRICS.get(action_key, ["net_margin_pct"])

            # Conservative qualitative impact — lang-aware
            exp_r = kpis.get("expense_ratio")
            nm    = kpis.get("net_margin_pct", 0) or 0
            _ar = lang == "ar"; _tr = lang == "tr"
            if action_key == "reduce_expenses" and exp_r:
                if _ar: impact = f"تخفيض نسبة المصروف من {exp_r:.1f}٪ نحو المعيار سيوسّع هامش الربح"
                elif _tr: impact = f"Gider oranını {exp_r:.1f}%'den sektör normuna indirmek net marjı artıracak"
                else: impact = f"Improving expense ratio from {exp_r:.1f}% toward industry norm would expand net margin"
            elif action_key == "investigate_loss":
                if _ar: impact = f"العودة إلى الربحية أولوية قصوى — هامش الربح الحالي {nm:.1f}٪"
                elif _tr: impact = f"Karlılığa dönmek kritik — şube net marjı şu an %{nm:.1f}"
                else: impact = f"Returning to profitability is critical — branch net margin currently {nm:.1f}%"
            elif action_key == "scale_revenue":
                if _ar: impact = "الهامش القوي يوفر مجالاً للاستثمار في نمو الإيراد"
                elif _tr: impact = "Güçlü marj, gelir büyümesine yatırım için alan sağlıyor"
                else: impact = "Strong margin provides room to invest in revenue growth"
            elif action_key == "maintain_growth":
                if _ar: impact = "الحفاظ على المسار الحالي يدعم أداء المحفظة"
                elif _tr: impact = "Mevcut seyrin korunması portföy performansını destekliyor"
                else: impact = "Sustaining current trajectory supports portfolio performance"
            else:
                if _ar: impact = "التحسين التشغيلي يدعم الأداء العام للشركة"
                elif _tr: impact = "Operasyonel iyileştirme şirketin genel performansını destekler"
                else: impact = "Operational improvement supports overall company performance"

            decisions.append({
                "title":          detail,
                "priority":       priority,
                "domain":         domain,
                "reason":         detail,
                "impact":         impact,
                "time_horizon":   horizon,
                "owner_scope":    owner,
                "source_metrics": source_metrics,
                "scope":          "branch",
                "branch_id":      branch_id,
                "branch_name":    branch_name,
            })

    # Sort: high first, then medium, then low
    _prio_rank = {"high": 0, "medium": 1, "low": 2}
    decisions.sort(key=lambda d: _prio_rank.get(d["priority"], 1))
    return decisions


@router.get("/{company_id}/decisions-v2")
def get_decisions_v2(
    company_id:  str,
    lang:        str  = Query(default="en"),
    consolidate: bool = Query(default=False, description="true = derive company analysis from branch uploads"),
    db: Session = Depends(get_db),
):
    """
    Decision Engine V2 — structured CFO-grade decisions.

    Returns company_decisions (from company analysis path, respects consolidate)
    and branch_decisions (from branch intelligence path directly).

    Company decisions enrich existing cfo_decision_engine output with:
      source_metrics, owner_scope, time_horizon, scope=company

    Branch decisions map existing branch profile.actions to canonical schema:
      title, priority, domain, reason, impact, time_horizon, owner_scope,
      source_metrics, scope=branch, branch_id, branch_name
    """
    from app.services.fin_intelligence   import build_intelligence
    from app.services.period_aggregation import build_annual_layer
    from app.services.alerts_engine      import build_alerts
    from app.services.cfo_decision_engine import build_cfo_decisions
    from app.models.branch import Branch

    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    # ── Company analysis path (respects consolidate flag) ─────────────────────
    if consolidate:
        all_stmts = _build_consolidated_statements(company_id, db)
        if not all_stmts:
            raise HTTPException(422, "No financial data uploaded yet (branch consolidation).")
    else:
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None),
            )
            .order_by(TrialBalanceUpload.uploaded_at.asc())
            .all()
        )
        if not uploads:
            raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")
        all_stmts = _build_period_statements(company_id, uploads)
        if not all_stmts:
            raise HTTPException(422, "Could not build statements.")

    # ── Run analysis pipeline for company decisions ───────────────────────────
    try:
        analysis = run_analysis(all_stmts)
        annual   = build_annual_layer(all_stmts)
        intel    = build_intelligence(analysis=analysis, annual_layer=annual, currency=company.currency or "")
        alerts   = build_alerts(intel, lang=safe_lang).get("alerts", [])
        raw_dec = build_cfo_decisions(
            intelligence=intel,
            alerts=alerts,
            lang=safe_lang,
            n_periods=len(all_stmts),
            analysis=analysis,
            branch_context=_branch_context_for_cfo_decisions(db, company_id),
        )
    except Exception as exc:
        logger.warning("decisions-v2 company pipeline failed: %s", exc)
        raw_dec = {"decisions": [], "recommendations": []}

    company_decisions = [
        _enrich_company_decision(d) for d in raw_dec.get("decisions", [])
    ]

    # ── Branch decisions path — direct from branch intelligence ───────────────
    branch_decisions = []
    try:
        branches = (
            db.query(Branch)
            .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa
            .all()
        )
        branch_data = []
        for b in branches:
            stmts = _build_single_branch_statements(b.id, company_id, db)
            if not stmts:
                continue
            b_anal   = run_analysis(stmts)
            b_trends = b_anal.get("trends", {})
            lat_is   = stmts[-1].get("income_statement", {})
            rev      = lat_is.get("revenue", {}).get("total", 0) or 0
            exp      = lat_is.get("expenses", {}).get("total", 0) or 0
            nm       = lat_is.get("net_margin_pct", 0) or 0
            exp_r    = round(exp / rev * 100, 2) if rev > 0 else None
            mom_rev  = b_trends.get("revenue_mom_pct") or b_trends.get("revenue_mom") or []
            mom_vals = [x for x in mom_rev if x is not None]
            c_pos    = sum(1 for _ in __import__('itertools').takewhile(lambda x: x > 0, reversed(mom_vals)))
            c_neg    = sum(1 for _ in __import__('itertools').takewhile(lambda x: x < 0, reversed(mom_vals)))

            _revs = [float(x.get("revenue", {}).get("total") or 0) for x in stmts]
            _exps = [float(x.get("expenses", {}).get("total") or 0) for x in stmts]
            avg_exp = (
                round(sum(_exps) / sum(_r for _r in _revs if _r) * 100, 2)
                if _revs and sum(_r for _r in _revs if _r) > 0
                else 50.0
            )

            # Build action detail text — lang-aware inline (avoids closure import issues)
            def _act_detail(key: str, **kw) -> str:
                ar = safe_lang == "ar"
                tr_ = safe_lang == "tr"
                er = kw.get("exp_r", 0); n_m = kw.get("nm", 0); n = kw.get("n", 0)
                if key == "reduce_expenses":
                    if ar: return f"نسبة المصروف {er:.1f}٪ — مراجعة التكاليف التشغيلية فوراً"
                    if tr_: return f"Gider oranı %{er:.1f} — işletme maliyetlerini hemen gözden geçirin"
                    return f"Expense ratio at {er:.1f}% — review operating costs immediately"
                if key == "investigate_loss":
                    if ar: return f"الفرع في منطقة الخسارة ({n_m:.1f}٪) — تحليل جذري مطلوب"
                    if tr_: return f"Şube zarar bölgesinde (%{n_m:.1f}) — kök neden analizi gerekli"
                    return f"Branch in loss territory ({n_m:.1f}% net margin) — root cause analysis required"
                if key == "investigate_decline":
                    if ar: return f"تراجع الإيراد لـ {n} أشهر متتالية — مراجعة الوضع السوقي"
                    if tr_: return f"Gelir {n} ay art arda düştü — piyasa koşullarını gözden geçirin"
                    return f"Revenue declining {n} consecutive months — review market conditions"
                if key == "improve_margin":
                    if ar: return f"هامش الربح {n_m:.1f}٪ دون 20٪ — مراجعة التسعير والتكاليف"
                    if tr_: return f"Net marj %{n_m:.1f}, %20 hedefinin altında — fiyatlandırmayı gözden geçirin"
                    return f"Net margin {n_m:.1f}% below 20% target — review pricing and cost structure"
                if key == "scale_revenue":
                    if ar: return f"هامش قوي ({n_m:.1f}٪) مع زخم نمو — فرصة للتوسع"
                    if tr_: return f"Güçlü marj (%{n_m:.1f}) ve büyüme ivmesi — kapasite genişletmeyi düşünün"
                    return f"Strong margin ({n_m:.1f}%) with growth momentum — consider capacity expansion"
                # maintain_growth
                if ar: return "الحفاظ على الانضباط في التكاليف ومسار النمو الحالي"
                if tr_: return "Mevcut maliyet disiplinini ve büyüme yörüngesini koruyun"
                return "Maintain current cost discipline and growth trajectory"

            actions = []
            if exp_r is not None and exp_r > 60:
                actions.append({"priority": "high", "action": "reduce_expenses",
                    "detail": _act_detail("reduce_expenses", exp_r=exp_r)})
            if nm < 0:
                actions.append({"priority": "high", "action": "investigate_loss",
                    "detail": _act_detail("investigate_loss", nm=nm)})
            if c_neg >= 2:
                actions.append({"priority": "high", "action": "investigate_decline",
                    "detail": _act_detail("investigate_decline", n=c_neg)})
            if 0 <= nm < 20:
                actions.append({"priority": "medium", "action": "improve_margin",
                    "detail": _act_detail("improve_margin", nm=nm)})
            if nm > 20 and c_pos >= 1:
                actions.append({"priority": "medium", "action": "scale_revenue",
                    "detail": _act_detail("scale_revenue", nm=nm)})
            if c_pos >= 2 and not actions:
                actions.append({"priority": "low", "action": "maintain_growth",
                    "detail": _act_detail("maintain_growth")})

            branch_data.append({
                "branch_id":   b.id,
                "branch_name": b.name,
                "has_data":    True,
                "kpis":        {"expense_ratio": exp_r, "net_margin_pct": round(nm, 2), "revenue": round(rev, 2)},
                "flags":       {},
                "profile":     {"actions": actions},
            })

        branch_decisions = _build_branch_decisions(branch_data, lang=safe_lang)
    except Exception as exc:
        logger.warning("decisions-v2 branch pipeline failed: %s", exc)

    # ── Compose summary ───────────────────────────────────────────────────────
    all_decisions = company_decisions + branch_decisions
    prio_count    = {p: sum(1 for d in all_decisions if d["priority"] == p)
                     for p in ("high", "medium", "low")}

    return {
        "company_id":         company_id,
        "company_name":       company.name,
        "data_source":        "branch_consolidation" if consolidate else "direct_uploads",
        "lang":               safe_lang,
        "latest_period":      (all_stmts[-1].get("period", "") if all_stmts else ""),
        "summary": {
            "total":              len(all_decisions),
            "company_decisions":  len(company_decisions),
            "branch_decisions":   len(branch_decisions),
            "high_priority":      prio_count["high"],
            "medium_priority":    prio_count["medium"],
            "low_priority":       prio_count["low"],
        },
        "company_decisions":  company_decisions,
        "branch_decisions":   branch_decisions,
        "recommendations":     raw_dec.get("recommendations", []),
    }



# ── GET /{company_id}/expense-intelligence ────────────────────────────────────

@router.get("/{company_id}/expense-intelligence")
def get_expense_intelligence(
    company_id:  str,
    lang:        str  = Query(default="en"),
    consolidate: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """
    CFO-grade expense intelligence.
    Returns grouped breakdown, variance, heatmap, thresholds, insights, branch comparison.
    Branch comparison uses latest-period KPIs from canonical branch TB statements.
    """
    from app.api import branches as _branches_api
    from app.services.expense_engine import build_expense_intelligence
    from app.models.branch import Branch

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    # ── Statements ────────────────────────────────────────────────────────────
    if consolidate:
        all_stmts = _build_consolidated_statements(company_id, db)
        if not all_stmts:
            raise HTTPException(422, "No financial data uploaded yet (branch consolidation).")
        data_source = "branch_consolidation"
    else:
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None),
            )
            .order_by(TrialBalanceUpload.uploaded_at.asc())
            .all()
        )
        if not uploads:
            raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")
        all_stmts = _build_period_statements(company_id, uploads)
        if not all_stmts:
            raise HTTPException(422, "Could not build statements.")
        data_source = "direct_uploads"

    # ── Branch kpis — latest period from canonical branch statements ─────────
    branch_financials: list[dict] = []
    try:
        branches = (
            db.query(Branch)
            .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa
            .all()
        )
        for b in branches:
            stmts_b = _branches_api._branch_statements_from_uploads(db, company_id, b.id)
            if not stmts_b:
                continue
            is_ = (stmts_b[-1].get("income_statement") or {})
            rev = float((is_.get("revenue") or {}).get("total") or 0)
            exp = float((is_.get("expenses") or {}).get("total") or 0)
            exp_ratio = round(exp / rev * 100, 2) if rev > 0 else None
            branch_financials.append({
                "branch_id":   b.id,
                "branch_name": b.name,
                "kpis":        {"expense_ratio": exp_ratio},
            })
    except Exception as exc:
        logger.warning("expense-intelligence branch fetch failed: %s", exc)

    # ── Build intelligence ────────────────────────────────────────────────────
    result = build_expense_intelligence(
        period_statements = all_stmts,
        branch_financials = branch_financials or None,
        lang              = lang if lang in ("en", "ar", "tr") else "en",
    )

    return {
        "company_id":   company_id,
        "company_name": company.name,
        "data_source":  data_source,
        **result,
    }




# ── GET /{company_id}/cfo-decisions ───────────────────────────────────────────

@router.get("/{company_id}/cfo-decisions")
def get_cfo_decisions(
    company_id:  str,
    lang:        str  = Query(default="en"),
    window:      str  = Query(default="ALL"),
    basis_type:  str  = Query(default="all"),
    period:      str  = Query(default=""),
    year_scope:  str  = Query(default="", alias="year"),
    from_period: str  = Query(default=""),
    to_period:   str  = Query(default=""),
    consolidate: bool = Query(default=False),
    branch_id:   str  = Query(default="", description="Single-branch TB scope (same as GET /executive)"),
    current_user       = Depends(get_current_user),
    db:          Session = Depends(get_db),
):
    """
    Canonical CFO decisions — same scope rules and engine as GET /executive.
    Deterministic: build_cfo_decisions only (no secondary decision taxonomy layer).
    """
    from app.services.fin_intelligence import build_intelligence
    from app.services.period_aggregation import build_annual_layer
    from app.services.alerts_engine import build_alerts

    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company, _all_stmts, windowed, resolved_scope, _scope22 = _product_windowed_statements(
        db,
        company_id,
        consolidate=consolidate,
        branch_id=branch_id or None,
        window=window,
        basis_type=basis_type,
        period=period,
        year_scope=year_scope,
        from_period=from_period,
        to_period=to_period,
    )

    analysis: dict = {}
    try:
        analysis = run_analysis(windowed)
        annual = build_annual_layer(windowed)
        intel = build_intelligence(
            analysis=analysis, annual_layer=annual, currency=company.currency or "",
        )
        alerts = build_alerts(intel, lang=safe_lang).get("alerts", [])
        raw_dec = build_cfo_decisions(
            intel,
            alerts=alerts,
            lang=safe_lang,
            n_periods=analysis.get("period_count", len(windowed)),
            analysis=analysis,
            branch_context=_branch_context_for_cfo_decisions(db, company_id),
        )
    except Exception as exc:
        logger.warning("cfo-decisions pipeline failed: %s", exc)
        raw_dec = {
            "decisions": [],
            "recommendations": [],
            "summary": {
                "insufficient": True,
                "reason_code": "pipeline_error",
                "detail": str(exc),
            },
            "causal_items": [],
        }

    try:
        fc = _build_forecast(analysis, lang=safe_lang) if analysis else {"available": False, "reason": "unavailable"}
    except Exception:
        fc = {"available": False, "reason": "unavailable"}

    exec_cf: dict = {}
    exec_pv: dict = {}
    try:
        exec_cf = build_cashflow(windowed) if windowed else {}
        exec_pv = _validate_pipeline(windowed, analysis, exec_cf)
    except Exception as _pv_exc:
        logger.warning("cfo-decisions pipeline_validation failed: %s", _pv_exc)

    return {
        "status":       "success",
        "company_id":   company_id,
        "company_name": company.name,
        "lang":         safe_lang,
        "data_source": (
            "branch_upload"
            if (branch_id or "").strip()
            else ("branch_consolidation" if consolidate else "direct_uploads")
        ),
        "meta":         {
            "scope": resolved_scope,
            "window": window,
            "pipeline_validation": exec_pv,
        },
        "data": {
            "decisions":       raw_dec.get("decisions", []),
            "decisions_summary": raw_dec.get("summary", {}),
            "recommendations": raw_dec.get("recommendations", []),
            "causal_items":    raw_dec.get("causal_items", []),
            "forecast":        fc,
        },
    }

# NOTE: Canonical GET /{company_id}/cfo-decisions is implemented above.
# The Phase 25 scoped version below was a duplicate route registration and is removed
# to avoid ambiguity at runtime.

# ── GET /{company_id}/board-report ────────────────────────────────────────────

@router.get("/{company_id}/board-report")
def get_board_report(
    company_id:  str,
    lang:        str  = Query(default="en"),
    window:      str  = Query(default="ALL", description="3M | 6M | 12M | YTD | ALL"),
    branch_id:   str  = Query(default="",    description="Optional: single branch report"),
    consolidate: bool = Query(default=False),
    db:          Session = Depends(get_db),
):
    """
    CFO Board Report — assembles from analysis + executive outputs.
    No new financial calculations. Pure aggregation and narrative layer.
    """
    from app.services.report_generator import build_board_report
    from datetime import datetime, timezone
    import traceback

    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    # ── Build analysis dict (reuse existing pipeline) ─────────────────────────
    analysis_dict: dict = {}
    try:
        if branch_id:
            all_stmts = _build_single_branch_statements(branch_id, company_id, db)
            if not all_stmts:
                raise HTTPException(404, f"No financial data for branch {branch_id}.")
        elif consolidate:
            all_stmts = _build_consolidated_statements(company_id, db)
        else:
            uploads = (
                db.query(TrialBalanceUpload)
                .filter(
                    TrialBalanceUpload.company_id == company_id,
                    TrialBalanceUpload.status == "ok",
                    TrialBalanceUpload.branch_id.is_(None),
                )
                .order_by(TrialBalanceUpload.uploaded_at.asc())
                .all()
            )
            if not uploads:
                raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")
            all_stmts = _build_period_statements(company_id, uploads)

        if not all_stmts:
            raise HTTPException(422, "Could not build financial statements.")

        from app.services.analysis_engine import run_analysis, _trend_direction
        from app.services.cashflow_engine  import build_cashflow

        # Apply window filter — same logic as get_analysis() / get_intelligence()
        # 1M is handled by _agg_stmts below (not via filter_periods)
        _safe_window = window.upper() if window.upper() in VALID_WINDOWS else "ALL"
        windowed_stmts = filter_periods(all_stmts, _safe_window)
        if not windowed_stmts:
            windowed_stmts = all_stmts  # fallback to all if window too narrow

        _analysis = run_analysis(windowed_stmts)
        _trends_r = _analysis.get("trends") or {}
        _latest_r = _analysis.get("latest") or {}
        _prof     = _latest_r.get("profitability", {})
        _liq      = _latest_r.get("liquidity", {})
        _lev      = _latest_r.get("leverage", {})
        _eff      = _latest_r.get("efficiency", {})

        # Phase 43 intelligence
        from app.services.root_cause_engine import build_root_causes
        from app.services.anomaly_engine    import detect_anomalies
        from app.services.narrative_builder import build_narratives

        def _lv(s): return next((x for x in reversed(s or []) if x is not None), None)
        # Derive ratios from already-available windowed statement data (statement_engine SSOT).
        _last_is = (windowed_stmts[-1].get("income_statement", {}) if windowed_stmts else {}) or {}
        _rev = _last_is.get("revenue", {}).get("total")
        _cogs = _last_is.get("cogs", {}).get("total")
        _exp = _last_is.get("expenses", {}).get("total")
        _lunc = float((_last_is.get("unclassified_pnl_debits") or {}).get("total") or 0)
        _opex_ratio = opex_ratio_pct(
            float(_exp) if _exp is not None else None,
            float(_rev) if _rev is not None else None,
        )
        _cogs_ratio = cogs_ratio_pct(
            float(_cogs) if _cogs is not None else None,
            float(_rev) if _rev is not None else None,
        )
        _total_cost_ratio = total_cost_ratio_pct(
            float(_cogs) if _cogs is not None else None,
            float(_exp) if _exp is not None else None,
            float(_rev) if _rev is not None else None,
            _lunc,
        )
        _expense_ratio = _total_cost_ratio

        def _ratio_mom(get_num):
            if not windowed_stmts or len(windowed_stmts) < 2:
                return None
            _a = windowed_stmts[-2].get("income_statement", {}) or {}
            _b = windowed_stmts[-1].get("income_statement", {}) or {}
            _ar = _a.get("revenue", {}).get("total")
            _br = _b.get("revenue", {}).get("total")
            _an = get_num(_a)
            _bn = get_num(_b)
            if _ar in (None, 0) or _br in (None, 0) or _an is None or _bn is None:
                return None
            _ra = (_an / _ar) * 100
            _rb = (_bn / _br) * 100
            return round(_rb - _ra, 2)

        _cogs_ratio_mom = _ratio_mom(lambda is_: (is_.get("cogs", {}) or {}).get("total"))
        _net_margin_mom = _lv(_trends_r.get("net_margin_pct_mom")) if "net_margin_pct_mom" in (_trends_r or {}) else None
        if _net_margin_mom is None:
            # Fallback: derive from statement-engine net_margin_pct series if present.
            if windowed_stmts and len(windowed_stmts) >= 2:
                _p = (windowed_stmts[-2].get("income_statement", {}) or {}).get("net_margin_pct")
                _c = (windowed_stmts[-1].get("income_statement", {}) or {}).get("net_margin_pct")
                _net_margin_mom = round(_c - _p, 2) if (_p is not None and _c is not None) else None

        _p43m = {
            "net_margin_pct": _prof.get("net_margin_pct"),
            "opex_ratio_pct": _opex_ratio,
            "cogs_ratio_pct": _cogs_ratio,
            "total_cost_ratio_pct": _total_cost_ratio,
            "expense_ratio": _expense_ratio,
            "cogs_ratio": _cogs_ratio,
        }
        _p43t = {"revenue_mom": _lv(_trends_r.get("revenue_mom_pct")),
                 "net_profit_mom": _lv(_trends_r.get("net_profit_mom_pct")),
                 "opex_mom_pct": _lv(_trends_r.get("expenses_mom_pct")),
                 "expense_ratio_mom": _lv(_trends_r.get("expenses_mom_pct")),
                 "cogs_ratio_mom": _cogs_ratio_mom, "net_margin_mom": _net_margin_mom}
        _rc2       = build_root_causes(_p43m, _p43t, lang=safe_lang)
        _anomalies = detect_anomalies(_p43m, _p43t, lang=safe_lang)
        _narratives= build_narratives(_rc2, _anomalies, lang=safe_lang)

        # Trends
        def _tq(mom):
            v = [x for x in (mom or []) if x is not None]
            if len(v) < 2: return "stable"
            lt = v[-2:]
            return "volatile" if (lt[0]>0.5 and lt[1]<-0.5) or (lt[0]<-0.5 and lt[1]>0.5) else "stable"
        def _mt(sk, mk):
            s=_trends_r.get(sk,[]); m=_trends_r.get(mk,[])
            v=[x for x in s if x is not None]
            d = {"series": s, "mom_pct": m, "direction": _trend_direction(m), "trend_quality": _tq(m),
                 "loss_flag": bool(v and v[-1] < 0)}
            enrich_trend_object(d, safe_lang)
            return d

        analysis_dict = {
            "company_id":   company_id,
            "company_name": company.name,
            "latest_period": (_analysis.get("periods") or [""])[-1],
            "period_count":  _analysis.get("period_count", 0),
            "periods":       _analysis.get("periods", []),
            "ratios": {
                "profitability": {"gross_margin_pct": _prof.get("gross_margin_pct"),
                                  "net_margin_pct":   _prof.get("net_margin_pct"),
                                  "operating_margin_pct": _prof.get("operating_margin_pct")},
                "liquidity":     {"current_ratio": _liq.get("current_ratio"),
                                  "quick_ratio":   _liq.get("quick_ratio"),
                                  "working_capital":_liq.get("working_capital")},
                "efficiency":    {"inventory_turnover":_eff.get("inventory_turnover"),
                                  "dso_days": _eff.get("dso_days"),
                                  "dpo_days": _eff.get("dpo_days"),
                                  "ccc_days": _eff.get("ccc_days")},
            },
            "trends":        {"revenue": _mt("revenue_series","revenue_mom_pct"),
                              "net_profit":_mt("net_profit_series","net_profit_mom_pct")},
            "anomalies":     _anomalies,
            "narratives":    _narratives,
            "structured_income_statement": _analysis.get("structured_income_statement"),
            "structured_income_statement_meta": _analysis.get("structured_income_statement_meta"),
            "structured_income_statement_variance": _analysis.get("structured_income_statement_variance"),
            "structured_income_statement_margin_variance": _analysis.get(
                "structured_income_statement_margin_variance"
            ),
            "structured_income_statement_variance_meta": _analysis.get(
                "structured_income_statement_variance_meta"
            ),
            "structured_profit_bridge": _analysis.get("structured_profit_bridge"),
            "structured_profit_bridge_interpretation": _analysis.get(
                "structured_profit_bridge_interpretation"
            ),
            "structured_profit_bridge_meta": _analysis.get("structured_profit_bridge_meta"),
            "structured_profit_story": _analysis.get("structured_profit_story"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("board-report analysis build failed: %s", exc)
        raise HTTPException(500, "Internal processing error")

    # ── Build executive dict (inline — reuse same engines) ────────────────────
    executive_dict: dict = {}
    try:
        from app.services.expense_engine import build_expense_intelligence

        # Aggregate across windowed periods:
        # 1M  → latest period only (single month)
        # 3M+ → SUM across all periods in window
        _safe_window2 = window.upper() if window.upper() in VALID_WINDOWS else "ALL"
        _raw_window   = window.upper()  # preserve original for 1M check
        if _raw_window == "1M":
            # Single month — use latest period only
            _agg_stmts = [windowed_stmts[-1]]
        else:
            # Multi-period window — sum across all periods
            _agg_stmts = windowed_stmts

        _rev = round(sum(
            (s.get("income_statement", {}).get("revenue", {}).get("total") or 0)
            for s in _agg_stmts
        ), 2)
        _np  = round(sum(
            (s.get("income_statement", {}).get("net_profit") or 0)
            for s in _agg_stmts
        ), 2)
        _exp = round(sum(
            (s.get("income_statement", {}).get("expenses", {}).get("total") or 0)
            for s in _agg_stmts
        ), 2)
        _cogs_sum = round(sum(
            (s.get("income_statement", {}).get("cogs", {}).get("total") or 0)
            for s in _agg_stmts
        ), 2)
        _uncls_sum = round(sum(
            float((s.get("income_statement", {}).get("unclassified_pnl_debits") or {}).get("total") or 0)
            for s in _agg_stmts
        ), 2)
        _last_is_bm = (windowed_stmts[-1].get("income_statement", {}) or {}) if windowed_stmts else {}
        _latest_rev = _last_is_bm.get("revenue", {}).get("total")
        _latest_np = _last_is_bm.get("net_profit")
        _latest_nm = _last_is_bm.get("net_margin_pct")
        _latest_gm = _last_is_bm.get("gross_margin_pct")
        _latest_cogs = _last_is_bm.get("cogs", {}).get("total")
        _latest_opex = _last_is_bm.get("expenses", {}).get("total")
        _latest_unc = float((_last_is_bm.get("unclassified_pnl_debits") or {}).get("total") or 0)
        _nm       = round(_np / _rev * 100, 2) if _rev else 0   # window blended net margin
        _gm       = round(sum(
            (s.get("income_statement", {}).get("gross_profit") or 0)
            for s in _agg_stmts
        ) / _rev * 100, 2) if _rev else None                     # window blended gross margin
        _opex_ratio_w = opex_ratio_pct(float(_exp), float(_rev) if _rev else None)
        _cogs_ratio_w = cogs_ratio_pct(float(_cogs_sum), float(_rev) if _rev else None)
        _tc_ratio_w = total_cost_ratio_pct(
            float(_cogs_sum), float(_exp), float(_rev) if _rev else None, float(_uncls_sum)
        )
        _expr = _tc_ratio_w
        _opex_ratio_l = opex_ratio_pct(
            float(_latest_opex) if _latest_opex is not None else None,
            float(_latest_rev) if _latest_rev is not None else None,
        )
        _cogs_ratio_l = cogs_ratio_pct(
            float(_latest_cogs) if _latest_cogs is not None else None,
            float(_latest_rev) if _latest_rev is not None else None,
        )
        _tc_ratio_l = total_cost_ratio_pct(
            float(_latest_cogs) if _latest_cogs is not None else None,
            float(_latest_opex) if _latest_opex is not None else None,
            float(_latest_rev) if _latest_rev is not None else None,
            _latest_unc,
        )
        _mom_rev  = _trends_r.get("revenue_mom_pct", [])
        _mom_np   = _trends_r.get("net_profit_mom_pct", [])
        _rev_dir  = _trend_direction(_mom_rev)
        _np_dir   = _trend_direction(_mom_np)

        # Health score (rule-based)
        _mom_np_v = [x for x in _mom_np if x is not None]
        _np_vol   = len(_mom_np_v) >= 2 and (((_mom_np_v[-2]>0.5 and _mom_np_v[-1]<-0.5) or (_mom_np_v[-2]<-0.5 and _mom_np_v[-1]>0.5)))
        if _np < 0:          _hs = 20
        elif _tc_ratio_w and _tc_ratio_w > 80: _hs = 35
        elif _np_dir == "declining" and _nm < 10: _hs = 40
        elif _np_vol:        _hs = 48
        elif _rev_dir == "improving" and _np_dir == "improving": _hs = 82
        elif _rev_dir == "improving": _hs = 70
        else:                _hs = 58
        _hl = next((l for lo,hi,l in [(0,31,"critical"),(31,51,"weak"),(51,66,"stable"),(66,81,"good"),(81,101,"strong")] if lo<=_hs<hi), "stable")

        # Expense signals
        _ei = build_expense_intelligence(all_stmts, branch_financials=None, lang=safe_lang)
        _exp_ins = [{"type":i["type"],"severity":i["severity"],"summary":i["what_happened"]} for i in _ei.get("insights",[])]

        # Priorities, risks, opportunities from Phase 43
        _SEV = {"high":3,"critical":3,"medium":2,"warning":2,"low":1,"info":1}
        _PRI = {"high":0,"critical":0,"medium":1,"warning":1,"low":2,"info":3}
        _p43_pris = [{"src":"narrative","type":n.get("type",""),"severity":n.get("priority","medium"),
                      "summary":n.get("what_happened",""),"urgency":n.get("urgency","soon")}
                     for n in _narratives if n.get("priority") in ("high","medium")]
        _leg_pris  = [{"src":"expense","type":e.get("type",""),"severity":e.get("severity","medium"),
                       "summary":e.get("summary",""),"urgency":"soon"}
                      for e in _exp_ins if _SEV.get(e.get("severity",""),0) >= 2]
        _seen = set(); _merged = []
        for s in _p43_pris + _leg_pris:
            if s["type"] not in _seen: _seen.add(s["type"]); _merged.append(s)
        _merged.sort(key=lambda x: _PRI.get(x.get("severity","medium"), 2))

        _risks = [{"type":a.get("type",""),"severity":a.get("severity",""),
                   "description":a.get("what_happened",""),"source":"phase43"}
                  for a in _anomalies if a.get("severity") in ("high","medium")]
        _risks += [{"type":e["type"],"severity":e["severity"],"description":e["summary"],"source":"expense"}
                   for e in _exp_ins if _SEV.get(e.get("severity",""),0) >= 2]

        _opps = []
        for n in _narratives:
            if n.get("priority") == "low" and n.get("type") in ("strong_profitability",):
                _opps.append({"type":n["type"],"description":n.get("what_happened",""),"source":"phase43"})
        if _rev_dir == "improving" and _np_dir == "improving":
            if safe_lang=="ar":   _od="الإيرادات والأرباح في تحسن — فرصة للتوسع"
            elif safe_lang=="tr": _od="Gelir ve kâr iyileşiyor — büyüme fırsatı"
            else:                 _od="Revenue and profit improving — expansion opportunity"
            _opps.append({"type":"growth_momentum","description":_od,"source":"trend"})

        executive_dict = {
            "company_id":    company_id,
            "company_name":  company.name,
            "lang":          safe_lang,
            "latest_period": analysis_dict["latest_period"],
            "period_count":  analysis_dict["period_count"],
            "health": {"score": _hs, "label": _hl, "score_method": "rule_based"},
            "quick_metrics": {
                "metric_basis": "window_blended_and_latest_snapshot",
                "window_revenue_total": round(_rev, 2),
                "window_net_profit_total": round(_np, 2),
                "window_net_margin_pct": _nm,
                "window_gross_margin_pct": _gm,
                "window_opex_total": _exp,
                "window_cogs_total": _cogs_sum,
                "window_unclassified_pnl_debits_total": _uncls_sum,
                "window_opex_ratio_pct": _opex_ratio_w,
                "window_cogs_ratio_pct": _cogs_ratio_w,
                "window_total_cost_ratio_pct": _tc_ratio_w,
                "latest_revenue": _latest_rev,
                "latest_net_profit": _latest_np,
                "latest_net_margin_pct": _latest_nm,
                "latest_gross_margin_pct": _latest_gm,
                "latest_opex_ratio_pct": _opex_ratio_l,
                "latest_cogs_ratio_pct": _cogs_ratio_l,
                "latest_total_cost_ratio_pct": _tc_ratio_l,
                "revenue": round(_rev, 2),
                "net_profit": round(_np, 2),
                "net_margin_pct": _nm,
                "gross_margin_pct": _gm,
                "opex_ratio_pct": _opex_ratio_w,
                "cogs_ratio_pct": _cogs_ratio_w,
                "total_cost_ratio_pct": _tc_ratio_w,
                "expense_ratio": _expr,
                "operating_cashflow": None,
                "revenue_mom_pct": _lv(_mom_rev),
                "net_profit_mom_pct": _lv(_mom_np),
                "latest_period": analysis_dict["latest_period"],
            },
            "top_priorities": [{"rank":i+1,"source":s["src"],"summary":s.get("summary",""),
                                 "severity":s.get("severity","medium"),"urgency":s.get("urgency","soon"),
                                 "type":s.get("type","")} for i,s in enumerate(_merged[:3])],
            "risks":          _risks[:5],
            "opportunities":  _opps[:3],
        }
    except Exception as exc:
        logger.warning("board-report executive build failed: %s", exc)
        executive_dict = executive_dict or {}  # use whatever was built

    # ── Previous-window comparison for KPI context ───────────────────────────────
    prev_comparison: dict = {}
    try:
        _safe_win2 = window.upper() if window.upper() in VALID_WINDOWS else "ALL"
        if _safe_win2 not in ("ALL", "YTD") and len(all_stmts) > 0:
            # Determine window size
            _win_sizes = {"1M": 1, "3M": 3, "6M": 6, "12M": 12}
            _wn = _win_sizes.get(_safe_win2, 0)
            if _wn and len(all_stmts) >= _wn * 2:
                # Previous window = periods before current window
                _prev_stmts = all_stmts[-(_wn * 2):-_wn]
                _prev_agg   = _prev_stmts  # sum all
                _prev_rev   = sum((s.get("income_statement",{}).get("revenue",{}).get("total") or 0) for s in _prev_agg)
                _prev_np    = sum((s.get("income_statement",{}).get("net_profit") or 0)               for s in _prev_agg)
                _curr_rev   = _rev  # already computed
                _curr_np    = _np
                def _chg(curr, prev):
                    if prev and abs(prev) > 0:
                        return round((curr - prev) / abs(prev) * 100, 2)
                    return None
                _prev_nm    = round(_prev_np / _prev_rev * 100, 2) if _prev_rev > 0 else None
                _curr_nm    = round(_np / _rev * 100, 2) if _rev > 0 else None
                prev_comparison = {
                    "window":         _safe_win2,
                    "prev_revenue":   round(_prev_rev, 2),
                    "prev_net_profit":round(_prev_np,  2),
                    "prev_net_margin":_prev_nm,
                    "rev_chg_pct":    _chg(_curr_rev, _prev_rev),
                    "np_chg_pct":     _chg(_curr_np,  _prev_np),
                    "nm_chg_pts":     round(_curr_nm - _prev_nm, 2) if (_curr_nm is not None and _prev_nm is not None) else None,
                    "label":          format_prev_comparison_label(_safe_win2, safe_lang),
                    "label_key":      "prev_comparison_vs_window",
                    "label_params":   {"window": _safe_win2},
                }
    except Exception as _exc:
        logger.warning("previous-window comparison failed: %s", _exc)

    # ── Assemble report ───────────────────────────────────────────────────────
    try:
        from app.services.deep_intelligence import build_deep_intelligence
        from app.services.period_aggregation import build_annual_layer
        from app.services.fin_intelligence import build_intelligence
        from app.services.alerts_engine import build_alerts
        from app.services.cfo_decision_engine import build_cfo_decisions

        _di_board: dict = {}
        try:
            _di_board = build_deep_intelligence(windowed_stmts, _analysis, lang=safe_lang)
        except Exception as _di_exc:
            logger.warning("board-report deep_intelligence failed: %s", _di_exc)

        _dec_pack_board: dict = {}
        _dec_board: list = []
        try:
            _ann_b = build_annual_layer(windowed_stmts)
            _intel_b = build_intelligence(
                analysis=_analysis, annual_layer=_ann_b, currency=company.currency or "",
            )
            _al_b = build_alerts(_intel_b, lang=safe_lang).get("alerts", [])
            _bc_board = None if branch_id else _branch_context_for_cfo_decisions(db, company_id)
            _dec_pack_board = build_cfo_decisions(
                _intel_b,
                _al_b,
                lang=safe_lang,
                n_periods=len(windowed_stmts),
                analysis=_analysis,
                branch_context=_bc_board,
            )
            _dec_board = _dec_pack_board.get("decisions", [])
        except Exception as _de_exc:
            logger.warning("board-report CFO decisions assembly failed: %s", _de_exc)

        _dec_board_aug, _, _board_merged_causal = _augment_cfo_decision_pack_for_api(
            _dec_pack_board or None,
            safe_lang,
            deep_intel=_di_board or None,
            profit_intel=None,
        )
        _dec_board = _dec_board_aug
        report = build_board_report(
            analysis_dict,
            executive_dict,
            lang=safe_lang,
            deep_intelligence=_di_board or None,
            phase43_root_causes=_rc2,
            cfo_decisions=_dec_board,
            causal_items=_board_merged_causal,
        )
        report["prev_comparison"] = prev_comparison
        report["branch_id"]       = branch_id or None
        # Include underlying blocks for the board UI (additive; no contract break).
        # BoardReport.jsx expects data.analysis.trends.*.series for charts.
        report["analysis"]        = analysis_dict
        report["executive"]       = executive_dict
        report["deep_intelligence"] = _di_board
        report["generated_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        logger.warning("build_board_report failed: %s", exc)
        raise HTTPException(500, "Internal processing error")

    return report


# ── GET /{company_id}/forecast-scenarios ─────────────────────────────────────

# Internal forecast_engine scenario keys → canonical output keys
# Mapping done at output layer only — forecast_engine internals unchanged
_SCENARIO_KEY_MAP = {
    "base":       "base",
    "optimistic": "aggressive",
    "risk":       "conservative",
}

# SCENARIO_DELTA mirrors — for assumptions transparency only (not recomputed here)
_SCENARIO_ASSUMPTIONS = {
    "base":        {"revenue_growth_adj_pp": 0.0,  "expense_adj_pp": 0.0},
    "aggressive":  {"revenue_growth_adj_pp": +2.0, "expense_adj_pp": -1.0},
    "conservative":{"revenue_growth_adj_pp": -3.0, "expense_adj_pp": +1.5},
}


def _extract_points(series: list) -> list:
    """Pull point values from _project_series output [{step, point, ...}]."""
    return [s.get("point") for s in series] if series else []


def _extrapolate_cashflow(cf_series: list, revenue_scenario: list, base_revenue: list) -> list:
    """
    Extrapolate operating cashflow using the same MoM growth rate implied by
    the revenue scenario — no new formula, reuses the ratio from existing series.

    cashflow_method: trend_extrapolation (revenue-indexed)
    """
    if not cf_series or not base_revenue or not revenue_scenario:
        return []
    last_cf = cf_series[-1]
    if not last_cf:
        return []
    result = []
    prev = last_cf
    for rev_pt in revenue_scenario:
        base_rev_pt = base_revenue[len(result)] if len(result) < len(base_revenue) else base_revenue[-1]
        # Scale cashflow by the same ratio as revenue scenario vs base revenue
        if base_rev_pt and base_rev_pt != 0:
            ratio = rev_pt / base_rev_pt
        else:
            ratio = 1.0
        # Apply ratio relative to last actual cashflow trend
        # Conservative: cap upside at 1.5x, floor at 0.5x per step
        ratio = max(0.5, min(1.5, ratio))
        projected = round(prev * ratio, 2)
        result.append(projected)
        prev = projected
    return result


@router.get("/{company_id}/forecast-scenarios")
def get_forecast_scenarios(
    company_id:  str,
    lang:        str  = Query(default="en"),
    consolidate: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """
    Canonical forecast + scenario endpoint.

    Returns 3 scenarios with stable keys (base / aggressive / conservative).
    Internal forecast engine uses base/optimistic/risk — mapped at output layer only.
    Engine internals are unchanged.

    Operating cashflow forecast derived via trend_extrapolation from existing
    build_cashflow().series — same cashflow path as executive/analysis-summary.

    Scenario labels are NOT returned — frontend uses i18n keys:
    fc_scenario_base, fc_scenario_aggressive, fc_scenario_conservative
    """
    from app.services.forecast_engine import build_forecast
    from app.services.cashflow_engine import build_cashflow

    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    # ── Data source (respects consolidate) ───────────────────────────────────
    if consolidate:
        all_stmts = _build_consolidated_statements(company_id, db)
        if not all_stmts:
            raise HTTPException(422, "No financial data uploaded yet (branch consolidation).")
        data_source = "branch_consolidation"
    else:
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None),
            )
            .order_by(TrialBalanceUpload.uploaded_at.asc())
            .all()
        )
        if not uploads:
            raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")
        all_stmts = _build_period_statements(company_id, uploads)
        if not all_stmts:
            raise HTTPException(422, "Could not build statements.")
        data_source = "direct_uploads"

    # ── Existing forecast pipeline (unchanged) ────────────────────────────────
    analysis = run_analysis(all_stmts)
    raw_fc   = build_forecast(analysis, lang=safe_lang)

    if not raw_fc.get("available"):
        raise HTTPException(422, raw_fc.get("reason", "Insufficient data for forecast."))

    # ── Cashflow actuals from existing engine (same path as executive) ────────
    cf_actuals: list = []
    try:
        cf_raw    = build_cashflow(all_stmts)
        cf_ser    = cf_raw.get("series", {})
        cf_actuals = cf_ser.get("operating_cashflow", [])
    except Exception:
        pass

    # ── Build canonical scenario output — map at output layer only ────────────
    raw_scenarios  = raw_fc.get("scenarios", {})
    base_rev_pts   = _extract_points(raw_scenarios.get("base", {}).get("revenue", []))
    canonical_scenarios = {}

    for internal_key, canonical_key in _SCENARIO_KEY_MAP.items():
        sc = raw_scenarios.get(internal_key, {})
        rev_series  = sc.get("revenue", [])
        np_series   = sc.get("net_profit", [])
        exp_series  = sc.get("expenses", [])

        rev_pts  = _extract_points(rev_series)
        np_pts   = _extract_points(np_series)
        exp_pts  = _extract_points(exp_series)

        # Cashflow forecast: trend_extrapolation via revenue ratio
        # collection_improvement not wired here — applied in what-if only
        cf_forecast = _extrapolate_cashflow(cf_actuals, rev_pts, base_rev_pts)

        # Confidence: take from first step of revenue series (degrades per step)
        confidence = rev_series[0].get("confidence") if rev_series else raw_fc.get("summary", {}).get("base_confidence")

        canonical_scenarios[canonical_key] = {
            "assumptions":   _SCENARIO_ASSUMPTIONS[canonical_key],
            "forecast_series": {
                "revenue":            rev_pts,
                "net_profit":         np_pts,
                "expenses":           exp_pts,
                "operating_cashflow": cf_forecast,
            },
            "cashflow_method": "trend_extrapolation",
            "summary": {
                "projected_revenue":    rev_pts[-1]  if rev_pts  else None,
                "projected_profit":     np_pts[-1]   if np_pts   else None,
                "projected_cashflow":   cf_forecast[-1] if cf_forecast else None,
                "confidence":           confidence,
                "forecast_quality":     raw_fc.get("summary", {}).get("risk_level", "medium"),
            },
        }

    return {
        "company_id":      company_id,
        "company_name":    company.name,
        "lang":            safe_lang,
        "data_source":     data_source,
        "latest_period":   (analysis.get("periods") or [""])[-1],
        "forecast_periods":raw_fc.get("future_periods", []),
        "method":          raw_fc.get("method", "weighted_moving_average"),
        "forecast_quality":raw_fc.get("summary", {}).get("risk_level", "medium"),
        "actuals": {
            "periods":             raw_fc.get("periods", []),
            "revenue":             raw_fc.get("actuals", {}).get("revenue", []),
            "net_profit":          raw_fc.get("actuals", {}).get("net_profit", []),
            "expenses":            raw_fc.get("actuals", {}).get("expenses", []),
            "operating_cashflow":  cf_actuals,
        },
        "scenarios": canonical_scenarios,
        "what_if_template": {
            "revenue_uplift_pct":         0.0,
            "expense_reduction_pct":      0.0,
            "margin_improvement_pct":     0.0,
            "collection_improvement_pct": 0.0,
        },
        "insight": raw_fc.get("summary", {}).get("insight", ""),
    }


@router.post("/{company_id}/what-if")
def what_if(
    company_id: str,
    body: WhatIfRequest,
    lang: str = Query(default="en", description="Locale for period data-quality warnings: en | ar | tr"),
    db: Session = Depends(get_db),
):
    CLAMP_MAX = 500.0
    CLAMP_MIN = -100.0
    _lang = normalize_narrative_lang(lang)

    # ── Company ───────────────────────────────────────────────────────────────
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    # ── Build statements ──────────────────────────────────────────────────────
    uploads = (
        db.query(TrialBalanceUpload)
        .filter(
            TrialBalanceUpload.company_id == company_id,
            TrialBalanceUpload.status == "ok",
            TrialBalanceUpload.branch_id.is_(None),  # company-level only
        )
        .order_by(TrialBalanceUpload.uploaded_at.asc())
        .all()
    )
    if not uploads:
        raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")

    all_stmts = _build_period_statements(company_id, uploads)
    if not all_stmts:
        raise HTTPException(422, "Could not build statements.")

    annual = build_annual_layer(all_stmts)
    if not annual:
        raise HTTPException(422, "Could not build annual layer.")

    # ── Collect warnings ──────────────────────────────────────────────────────
    warnings: list[str] = []

    # Input clamping warnings (localized templates)
    for field, val in [("revenue_pct", body.revenue_pct),
                       ("cogs_pct",    body.cogs_pct),
                       ("opex_pct",    body.opex_pct)]:
        if val > CLAMP_MAX:
            warnings.append(format_narrative_warning_item({
                "key": "warn_whatif_clamp_max",
                "params": {"field": field, "from_value": val, "to_value": CLAMP_MAX},
            }, _lang))
        elif val < CLAMP_MIN:
            warnings.append(format_narrative_warning_item({
                "key": "warn_whatif_clamp_min",
                "params": {"field": field, "from_value": val, "to_value": CLAMP_MIN},
            }, _lang))

    # ── Resolve baseline block (scope22 overrides legacy basis) ─────────────
    period_kind: str = "ytd"
    if body.scope_basis_type and body.scope_basis_type.strip().lower() not in ("","all"):
        # Phase 22 universal scope path
        scoped_stmts, scope22 = _apply_scope(
            all_stmts,
            body.scope_basis_type, body.scope_period,
            body.scope_year, body.scope_from_period, body.scope_to_period
        )
        annual_for_wi = build_annual_layer(scoped_stmts) if scoped_stmts else annual
        block        = annual_for_wi.get("ytd") or annual_for_wi.get("latest_month") or {}
        period_label = scope22["label"] if scope22 else "custom"
        basis        = "scope"
        period_kind = "ytd" if annual_for_wi.get("ytd") else "latest_month"
    else:
        # Legacy basis path
        scope22 = None
        basis   = body.basis   # always defined here — validator guarantees valid value

        if basis == "latest_month":
            block = annual.get("latest_month")
            if not block:
                raise HTTPException(422, "latest_month data not available.")
            period_label = block.get("period", "latest_month")
            period_kind = "latest_month"
            if not block.get("tax"):
                warnings.append(format_narrative_warning_item(
                    {"key": "warn_tax_not_in_source", "params": {}}, _lang))

        elif basis == "ytd":
            block = annual.get("ytd")
            if not block:
                raise HTTPException(422, "YTD data not available.")
            period_label = f"YTD {block.get('year', '')}"
            period_kind = "ytd"
            if not block.get("tax"):
                warnings.append(format_narrative_warning_item(
                    {"key": "warn_tax_not_in_source", "params": {}}, _lang))

        elif basis == "full_year":
            fy_list = annual.get("full_years", [])
            if not fy_list:
                raise HTTPException(422, "No full-year data available.")
            if body.year:
                block = next((fy for fy in fy_list if fy["year"] == body.year), None)
                if not block:
                    raise HTTPException(422, f"Year {body.year} not found.")
            else:
                block = fy_list[0]
            period_label = f"FY {block['year']}"
            period_kind = "full_year"
            if not block.get("tax"):
                warnings.append(format_narrative_warning_item(
                    {"key": "warn_tax_not_in_source", "params": {}}, _lang))

        else:
            # Should never reach here — field_validator enforces allowed values
            raise HTTPException(422, f"Unexpected basis value: {basis}")

    wi_period = collect_period_block_warning_items(block, period_kind=period_kind, what_if_mode=True)
    warnings.extend(format_narrative_warning_items(wi_period, _lang))

    # ── Run simulation ────────────────────────────────────────────────────────
    result = run_what_if(
        baseline_block = block,
        revenue_pct    = body.revenue_pct,
        cogs_pct       = body.cogs_pct,
        opex_pct       = body.opex_pct,
    )

    # ── Apply collection_improvement_pct to projected cash flow ───────────────
    # Conservative model: each 1% improvement in cash conversion reduces DSO ~3 days,
    # translating to a proportional improvement in operating cashflow.
    # Capped at ±30% to prevent unrealistic projections.
    collection_adj: dict = {}
    cip = float(body.collection_improvement_pct or 0.0)
    if cip != 0.0:
        cip_clamped = max(-30.0, min(30.0, cip))
        # Estimate current operating cashflow from baseline net profit + DA proxy
        baseline_np = result.get("baseline", {}).get("net_profit", 0) or 0
        # Apply cash conversion improvement as proportional cash flow uplift
        projected_ocf = round(baseline_np * (1 + cip_clamped / 100), 2)
        _cf_note_key = "whatif_cashflow_collection_note"
        collection_adj = {
            "collection_improvement_pct": cip_clamped,
            "projected_operating_cashflow": projected_ocf,
            "cashflow_method":  "collection_adjustment",
            "cashflow_note":    format_simple_narrative(_cf_note_key, _lang),
            "cashflow_note_key": _cf_note_key,
            "cashflow_note_params": {},
        }

    return {
        "company_id":   company_id,
        "company_name": company.name,
        "basis":        basis,
        "period_label": period_label,
        "warnings":     warnings,
        "period_warning_items": wi_period,
        "lang":         _lang,
        **result,
        **({"cashflow_impact": collection_adj} if collection_adj else {}),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 16 — Decision Intelligence endpoint
# ══════════════════════════════════════════════════════════════════════════════

from app.services.scenario_ranker import rank_scenarios

class DecisionRequest(BaseModel):
    basis:             str = "ytd"  # legacy basis
    year:              str = ""
    # Phase 22 scope
    scope_basis_type:  str = ""
    scope_period:      str = ""
    scope_year:        str = ""
    scope_from_period: str = ""
    scope_to_period:   str = ""

    @field_validator("basis")
    @classmethod
    def validate_basis_d(cls, v):
        if v not in {"latest_month", "ytd", "full_year"}:
            raise ValueError("basis must be latest_month | ytd | full_year")
        return v


@router.post("/{company_id}/decisions")
def get_decisions(
    company_id: str,
    body: DecisionRequest,
    lang: str = Query("en"),
    db: Session = Depends(get_db),
):
    _req_lang = (lang or "en").strip().lower()
    safe_lang = normalize_narrative_lang(lang)
    locale_fallback = _req_lang not in ("en", "ar", "tr")

    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(404, "Company not found.")

        uploads = (
            db.query(TrialBalanceUpload)
            .filter(TrialBalanceUpload.company_id == company_id,
                    TrialBalanceUpload.status == "ok",
                    (TrialBalanceUpload.branch_id.is_(None) | (TrialBalanceUpload.branch_id == "")))
            .order_by(TrialBalanceUpload.uploaded_at.asc())
            .all()
        )
        if not uploads:
            raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")

        all_stmts = _build_period_statements(company_id, uploads)
        if not all_stmts:
            raise HTTPException(422, "Could not build statements.")

        annual = build_annual_layer(all_stmts)
        if not annual:
            raise HTTPException(422, "Could not build annual layer.")

        # Phase 22: scope override
        period_kind: str = "ytd"
        if body.scope_basis_type and body.scope_basis_type.strip().lower() not in ("","all"):
            scoped_stmts, scope22 = _apply_scope(
                all_stmts,
                body.scope_basis_type, body.scope_period,
                body.scope_year, body.scope_from_period, body.scope_to_period
            )
            annual_scoped = build_annual_layer(scoped_stmts) if scoped_stmts else annual
            block = annual_scoped.get("ytd") or annual_scoped.get("latest_month") or {}
            period_label = scope22["label"] if scope22 else "custom"
            period_kind = "ytd" if annual_scoped.get("ytd") else "latest_month"
        else:
            scope22 = None
            # Resolve baseline block (legacy)
            basis = body.basis
            if basis == "latest_month":
                block = annual.get("latest_month")
                if not block:
                    raise HTTPException(422, "latest_month not available.")
                period_label = block.get("period", "latest_month")
                period_kind = "latest_month"
            elif basis == "ytd":
                block = annual.get("ytd")
                if not block:
                    raise HTTPException(422, "YTD not available.")
                period_label = f"YTD {block.get('year', '')}"
                period_kind = "ytd"
            else:  # full_year
                fy_list = annual.get("full_years", [])
                if not fy_list:
                    raise HTTPException(422, "No full-year data.")
                block = next((fy for fy in fy_list if fy["year"] == body.year), fy_list[0]) if body.year else fy_list[0]
                period_label = f"FY {block['year']}"
                period_kind = "full_year"

        wi_period = collect_period_block_warning_items(block, period_kind=period_kind, what_if_mode=False)
        warnings = format_narrative_warning_items(wi_period, safe_lang)

        result = rank_scenarios(block, lang=safe_lang)

        return {
            "status":       "success",
            "company_id":   company_id,
            "company_name": company.name,
            "basis":        getattr(body, 'basis', 'scope') if not (body.scope_basis_type and body.scope_basis_type.strip().lower() not in ("","all")) else "scope",
            "period_label": period_label,
            "warnings":     warnings,
            "warning_items": wi_period,
            "meta":         {
                "company_id": company_id,
                "lang": safe_lang,
                "locale_requested": lang,
                "locale_fallback": locale_fallback,
            },
            **result,
        }

    except HTTPException:
        raise   # re-raise FastAPI HTTP errors as-is (still JSON)
    except Exception as e:
        logger.error("get_decisions error for %s: %s", company_id, e, exc_info=True)
        return {
            "status":  "error",
            "message": str(e),
            "meta":    {"company_id": company_id},
        }


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 17 — Narrative endpoint
# ══════════════════════════════════════════════════════════════════════════════

from app.services.scenario_ranker import rank_scenarios


@router.get("/{company_id}/narrative")
def get_narrative(
    company_id: str,
    basis: str = "ytd",
    lang:  str = "en",
    basis_type:  str = Query(default="all"),
    period:      str = Query(default=""),
    year_scope:  str = Query(default="", alias="year"),
    from_period: str = Query(default=""),
    to_period:   str = Query(default=""),
    db: Session = Depends(get_db),
):
    if basis not in {"latest_month", "ytd", "full_year"}:
        raise HTTPException(400, "basis must be latest_month | ytd | full_year")

    _req_lang = (lang or "en").strip().lower()
    effective_lang = normalize_narrative_lang(lang)
    locale_fallback = _req_lang not in ("en", "ar", "tr")

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    uploads = (
        db.query(TrialBalanceUpload)
        .filter(TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None))
        .order_by(TrialBalanceUpload.uploaded_at.asc())
        .all()
    )
    if not uploads:
        raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")

    all_stmts = _build_period_statements(company_id, uploads)
    if not all_stmts:
        raise HTTPException(422, "Could not build statements.")

    annual   = build_annual_layer(all_stmts)
    analysis = run_analysis(filter_periods(all_stmts, "ALL"))

    # Get best scenario (basis = ytd by default for narrative)
    ytd_block = annual.get("ytd") or annual.get("latest_month") or {}
    best_sc = None
    try:
        ranked   = rank_scenarios(ytd_block, lang=effective_lang)
        best_sc  = ranked.get("best_scenario")
    except Exception:
        pass

    narrative_warning_items = collect_default_narrative_warning_items(annual)

    narrative = build_narrative(
        annual_layer  = annual,
        analysis      = analysis,
        best_scenario = best_sc,
        warnings      = [],
        warning_items = narrative_warning_items,
        currency      = company.currency or "",
        lang          = effective_lang,
    )

    return {
        "company_id":   company_id,
        "company_name": company.name,
        "basis":        basis,
        "locale_requested": lang,
        "locale_effective": effective_lang,
        "locale_fallback": locale_fallback,
        **narrative,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 18 — Export endpoints
# ══════════════════════════════════════════════════════════════════════════════

from fastapi.responses import JSONResponse, StreamingResponse
import io as _io

from app.services.export_engine import build_excel, build_report_bundle


def _resolve_export_data(company_id: str, basis: str, lang: str, db, scope_basis_type: str = "", scope_period: str = "", scope_year: str = "", scope_from_period: str = "", scope_to_period: str = ""):
    """
    Shared data-building pipeline for both export endpoints.
    Returns (company, period_label, status, annual, decisions, what_if, narrative, warnings)
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    uploads = (
        db.query(TrialBalanceUpload)
        .filter(TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None))
        .order_by(TrialBalanceUpload.uploaded_at.asc())
        .all()
    )
    if not uploads:
        raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")

    all_stmts = _build_period_statements(company_id, uploads)
    if not all_stmts:
        raise HTTPException(422, "Could not build statements.")

    # Phase 22: apply scope if provided
    if scope_basis_type and scope_basis_type.strip().lower() not in ("","all"):
        scoped_stmts, scope22 = _apply_scope(all_stmts, scope_basis_type, scope_period, scope_year, scope_from_period, scope_to_period)
        stmts_for_analysis = scoped_stmts if scoped_stmts else all_stmts
    else:
        stmts_for_analysis = all_stmts
        scope22 = None

    annual   = build_annual_layer(stmts_for_analysis)
    analysis = run_analysis(filter_periods(stmts_for_analysis, "ALL"))

    lang_eff = normalize_narrative_lang(lang)
    narrative_wi = collect_default_narrative_warning_items(annual)
    warnings: list[str] = format_narrative_warning_items(narrative_wi, lang_eff)
    ytd_block = annual.get("ytd") or annual.get("latest_month") or {}

    # Period label
    if basis == "latest_month":
        lm = annual.get("latest_month") or {}
        period_label = lm.get("period", "latest")
    elif basis == "full_year":
        fy = (annual.get("full_years") or [{}])[0]
        period_label = f"FY {fy.get('year','')}"
    else:
        ytd = annual.get("ytd") or {}
        period_label = f"YTD {ytd.get('year','')}"

    # Decisions
    decisions: dict = {}
    try:
        decisions = rank_scenarios(ytd_block, lang=lang_eff)
    except Exception as e:
        logger.warning("decisions failed: %s", e)

    best_sc = decisions.get("best_scenario")

    # What-If (combined scenario on YTD basis)
    what_if: dict = {}
    try:
        from app.services.what_if import run_what_if
        what_if = run_what_if(ytd_block, revenue_pct=5.0, cogs_pct=-2.0, opex_pct=-2.0)
        what_if["basis"] = basis
        what_if["period_label"] = period_label
    except Exception as e:
        logger.warning("what_if failed: %s", e)
        what_if = {"error": str(e)}

    # Narrative
    narrative: dict = {}
    try:
        narrative = build_narrative(
            annual_layer  = annual,
            analysis      = analysis,
            best_scenario = best_sc,
            warnings      = [],
            warning_items = narrative_wi,
            currency      = company.currency or "",
            lang          = lang_eff,
        )
    except Exception as e:
        logger.warning("narrative failed: %s", e)
        narrative = {"error": str(e)}

    status = narrative.get("status", "neutral")

    return (company, period_label, status, annual, decisions, what_if, narrative, warnings)


@router.get("/{company_id}/report-bundle")
def report_bundle(
    company_id: str,
    basis: str = "ytd",
    lang:  str = "en",
    scope_basis_type:  str = Query(default=""),
    scope_period:      str = Query(default=""),
    scope_year:        str = Query(default=""),
    scope_from_period: str = Query(default=""),
    scope_to_period:   str = Query(default=""),
    db: Session = Depends(get_db),
):
    company, period_label, status, annual, decisions, what_if, narrative, warnings = \
        _resolve_export_data(company_id, basis, lang, db, scope_basis_type, scope_period, scope_year, scope_from_period, scope_to_period)

    bundle = build_report_bundle(
        company      = {"id": company.id, "name": company.name, "currency": company.currency},
        basis        = basis,
        period_label = period_label,
        status       = status,
        annual       = annual,
        decisions    = decisions,
        what_if      = what_if,
        narrative    = narrative,
        warnings     = warnings,
    )
    return JSONResponse(content=bundle)


@router.get("/{company_id}/export.xlsx")
def export_xlsx(
    company_id: str,
    basis: str = "ytd",
    lang:  str = "en",
    scope_basis_type:  str = Query(default=""),
    scope_period:      str = Query(default=""),
    scope_year:        str = Query(default=""),
    scope_from_period: str = Query(default=""),
    scope_to_period:   str = Query(default=""),
    db: Session = Depends(get_db),
):
    company, period_label, status, annual, decisions, what_if, narrative, warnings = \
        _resolve_export_data(company_id, basis, lang, db, scope_basis_type, scope_period, scope_year, scope_from_period, scope_to_period)

    xlsx_bytes = build_excel(
        company      = {"id": company.id, "name": company.name},
        basis        = basis,
        period_label = period_label,
        status       = status,
        annual       = annual,
        decisions    = decisions,
        what_if      = what_if,
        narrative    = narrative,
        currency     = company.currency or "",
        lang         = lang if lang in ("en", "ar", "tr") else "en",
    )

    filename = f"VCFO_{company.name.replace(' ','_')}_{period_label.replace(' ','_')}.xlsx"
    return StreamingResponse(
        _io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 20 — Management Report endpoint
# ══════════════════════════════════════════════════════════════════════════════

from app.services.management_report import build_management_report


@router.get("/{company_id}/management-report")
def management_report(
    company_id: str,
    basis: str = "ytd",
    lang:  str = "en",
    scope_basis_type:  str = Query(default=""),
    scope_period:      str = Query(default=""),
    scope_year:        str = Query(default=""),
    scope_from_period: str = Query(default=""),
    scope_to_period:   str = Query(default=""),
    db: Session = Depends(get_db),
):
    if basis not in {"latest_month", "ytd", "full_year"}:
        raise HTTPException(400, "basis must be latest_month | ytd | full_year")
    if lang not in {"en", "ar", "tr"}:
        lang = "en"

    # Reuse shared export pipeline
    company, period_label, status, annual, decisions, what_if, narrative, warnings = \
        _resolve_export_data(company_id, basis, lang, db, scope_basis_type, scope_period, scope_year, scope_from_period, scope_to_period)

    report = build_management_report(
        company      = {"id": company.id, "name": company.name},
        basis        = basis,
        period_label = period_label,
        status       = status,
        annual       = annual,
        decisions    = decisions,
        what_if      = what_if,
        narrative    = narrative,
        warnings     = warnings,
        currency     = company.currency or "",
        lang         = lang,
    )

    return report


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 21 — Financial Intelligence endpoint
# ══════════════════════════════════════════════════════════════════════════════

from app.services.fin_intelligence import build_intelligence, _health_score_v2 as _compute_health_v2, extract_ratios as _extract_ratios
from app.services.trend_analysis import build_trends as _build_trends
from app.services.anomaly_detector import detect_anomalies as _detect_anomalies


@router.get("/{company_id}/intelligence")
def get_intelligence(
    company_id: str,
    window: str = Query("ALL", description="Analysis window: 3M|6M|12M|YTD|ALL"),
    basis_type:  str = Query(default="all"),
    period:      str = Query(default=""),
    year_scope:  str = Query(default="", alias="year"),
    from_period: str = Query(default=""),
    to_period:   str = Query(default=""),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    uploads = (
        db.query(TrialBalanceUpload)
        .filter(TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None))
        .order_by(TrialBalanceUpload.uploaded_at.asc())
        .all()
    )
    if not uploads:
        raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")

    all_stmts = _build_period_statements(company_id, uploads)
    if not all_stmts:
        raise HTTPException(422, "Could not build statements.")

    if (basis_type or "").lower() not in ("all", ""):
        scope22 = scope_from_params(basis_type, period or None, year_scope or None,
                                     from_period or None, to_period or None, all_stmts)
        if scope22.get("error"):
            raise HTTPException(400, scope22["error"])
        windowed = filter_by_scope(all_stmts, scope22)
    else:
        windowed  = filter_periods(all_stmts, window.upper() if window.upper() in VALID_WINDOWS else "ALL")
    analysis  = run_analysis(windowed)
    annual    = build_annual_layer(windowed)

    result = build_intelligence(
        analysis     = analysis,
        annual_layer = annual,
        currency     = company.currency or "",
    )

    return {
        "status":      "success",
        "company_id":  company_id,
        "company_name": company.name,
        "window":      window,
        "data":        result,
        "meta": {
            "period_count": analysis.get("period_count", 0),
            "periods":      analysis.get("periods", []),
            "currency":     company.currency or "",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 23 — Alerts endpoint
# ══════════════════════════════════════════════════════════════════════════════

from app.services.alerts_engine import build_alerts


@router.get("/{company_id}/alerts")
def get_alerts(
    company_id:  str,
    lang:        str = Query(default="en"),
    window:      str = Query(default="ALL"),
    basis_type:  str = Query(default="all"),
    period:      str = Query(default=""),
    year_scope:  str = Query(default="", alias="year"),
    from_period: str = Query(default=""),
    to_period:   str = Query(default=""),
    consolidate: bool = Query(default=False, description="Same as GET /executive — branch consolidation"),
    branch_id:   str  = Query(default="", description="Single-branch TB scope (same as GET /executive)"),
    db: Session = Depends(get_db),
):
    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company, _all_stmts, windowed, resolved_scope, _scope22 = _product_windowed_statements(
        db,
        company_id,
        consolidate=consolidate,
        branch_id=branch_id or None,
        window=window,
        basis_type=basis_type,
        period=period,
        year_scope=year_scope,
        from_period=from_period,
        to_period=to_period,
    )

    analysis = run_analysis(windowed)
    annual   = build_annual_layer(windowed)
    cf_raw = build_cashflow(windowed) if windowed else {}
    pv = _validate_pipeline(windowed, analysis, cf_raw)

    intelligence = build_intelligence(
        analysis     = analysis,
        annual_layer = annual,
        currency     = company.currency or "",
    )

    alerts_data = build_alerts(intelligence, lang=safe_lang)

    return {
        "status": "success",
        "company_id":   company_id,
        "company_name": company.name,
        "data": alerts_data,
        "meta": {
            "scope":        resolved_scope,
            "period_count": analysis.get("period_count", 0),
            "periods":      analysis.get("periods", []),
            "currency":     company.currency or "",
            "lang":         safe_lang,
            "pipeline_validation": pv,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 25 — CFO Decision Engine  GET /decisions
#  (separate from POST /decisions which is the Phase 19 scenario ranker)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{company_id}/decisions")
def get_cfo_decisions_v2(
    company_id:  str,
    lang:        str = Query(default="en"),
    window:      str = Query(default="ALL"),
    basis_type:  str = Query(default="all"),
    period:      str = Query(default=""),
    year_scope:  str = Query(default="", alias="year"),
    from_period: str = Query(default=""),
    to_period:   str = Query(default=""),
    consolidate: bool = Query(default=False, description="Same as GET /executive — branch consolidation"),
    branch_id:   str  = Query(default="", description="Single-branch TB scope (same as GET /executive)"),
    db: Session = Depends(get_db),
):
    """
    Phase 25 CFO Decision Engine — Phase 3: identical statement scope + alert path as GET /executive.
    Returns top 3 prioritized CFO-level decisions based on financial intelligence.
    """
    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company, _all_stmts, windowed, resolved_scope, _scope22 = _product_windowed_statements(
        db,
        company_id,
        consolidate=consolidate,
        branch_id=branch_id or None,
        window=window,
        basis_type=basis_type,
        period=period,
        year_scope=year_scope,
        from_period=from_period,
        to_period=to_period,
    )

    try:
        analysis     = run_analysis(windowed)
        annual       = build_annual_layer(windowed)
        intelligence = build_intelligence(
            analysis     = analysis,
            annual_layer = annual,
            currency     = company.currency or "",
        )
        alerts_data  = build_alerts(intelligence, lang=safe_lang)
        alerts_list  = alerts_data.get("alerts", [])
        result = build_cfo_decisions(
            intelligence=intelligence,
            alerts=alerts_list,
            lang=safe_lang,
            n_periods=analysis.get("period_count", 3),
            analysis=analysis,
            branch_context=_branch_context_for_cfo_decisions(db, company_id),
        )
    except Exception as _e:
        logger.error("get_cfo_decisions_v2 error for %s: %s", company_id, _e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Decision engine error: {_e}")

    cf_raw = build_cashflow(windowed) if windowed else {}
    pv = _validate_pipeline(windowed, analysis, cf_raw)

    decisions_aug, realized_list, merged_templates = _augment_cfo_decision_pack_for_api(
        result, safe_lang, deep_intel=None, profit_intel=None
    )
    data_payload = {
        **result,
        "decisions": decisions_aug,
        "causal_items": merged_templates,
        "realized_causal_items": realized_list,
    }

    return {
        "status":       "success",
        "company_id":   company_id,
        "company_name": company.name,
        "data":         data_payload,
        "meta": {
            "scope":             resolved_scope,
            "period_count":      analysis.get("period_count", 0),
            "periods":           analysis.get("periods", []),
            "lang":              safe_lang,
            "currency":          company.currency or "",
            "pipeline_validation": pv,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 26 — CFO Root Cause endpoint
# ══════════════════════════════════════════════════════════════════════════════

from app.services.cfo_root_cause_engine import build_root_causes as _build_root_causes


@router.get("/{company_id}/root-causes")
def get_root_causes(
    company_id:  str,
    lang:        str = Query(default="en"),
    window:      str = Query(default="ALL"),
    basis_type:  str = Query(default="all"),
    period:      str = Query(default=""),
    year_scope:  str = Query(default="", alias="year"),
    from_period: str = Query(default=""),
    to_period:   str = Query(default=""),
    consolidate: bool = Query(default=False, description="Same as GET /executive — branch consolidation"),
    branch_id:   str  = Query(default="", description="Single-branch TB scope (same as GET /executive)"),
    db: Session = Depends(get_db),
):
    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company, _all_stmts, windowed, resolved_scope, _scope22 = _product_windowed_statements(
        db,
        company_id,
        consolidate=consolidate,
        branch_id=branch_id or None,
        window=window,
        basis_type=basis_type,
        period=period,
        year_scope=year_scope,
        from_period=from_period,
        to_period=to_period,
    )

    analysis     = run_analysis(windowed)
    annual       = build_annual_layer(windowed)
    intelligence = build_intelligence(analysis=analysis, annual_layer=annual,
                                      currency=company.currency or "")

    alerts_data = build_alerts(intelligence, lang=safe_lang)
    dec_result = build_cfo_decisions(
        intelligence=intelligence,
        alerts=alerts_data.get("alerts", []),
        lang=safe_lang,
        n_periods=analysis.get("period_count", 3),
        analysis=analysis,
        branch_context=_branch_context_for_cfo_decisions(db, company_id),
    )
    decisions = dec_result.get("decisions", [])

    result = _build_root_causes(
        intelligence = intelligence,
        decisions    = decisions,
        lang         = safe_lang,
        n_periods    = analysis.get("period_count", 3),
    )

    cf_raw = build_cashflow(windowed) if windowed else {}
    pv = _validate_pipeline(windowed, analysis, cf_raw)

    return {
        "status":       "success",
        "company_id":   company_id,
        "company_name": company.name,
        "data":         result,
        "meta": {
            "scope":             resolved_scope,
            "period_count":      analysis.get("period_count", 0),
            "periods":           analysis.get("periods", []),
            "lang":              safe_lang,
            "currency":          company.currency or "",
            "pipeline_validation": pv,
            "cfo_recommendations": dec_result.get("recommendations", []),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 27 — Forecast endpoint
# ══════════════════════════════════════════════════════════════════════════════

from app.services.forecast_engine import build_forecast as _build_forecast
from app.services.impact_engine import build_decision_impacts as _build_impacts
from app.services.statement_engine import (
    build_statement_bundle as _build_statements,
    extract_structured_financial_overlay,
    strip_structured_keys_for_nested_statements,
)
from app.services.intel_surface_scores import build_intel_surface_scores, build_intel_tile_hints
from app.services.advanced_metrics  import compute_advanced_metrics as _compute_adv


@router.get("/{company_id}/forecast")
def get_forecast(
    company_id:  str,
    lang:        str = Query(default="en"),
    window:      str = Query(default="ALL"),
    basis_type:  str = Query(default="all"),
    period:      str = Query(default=""),
    year_scope:  str = Query(default="", alias="year"),
    from_period: str = Query(default=""),
    to_period:   str = Query(default=""),
    db: Session = Depends(get_db),
):
    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found.")

    uploads = (
        db.query(TrialBalanceUpload)
        .filter(TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None))
        .order_by(TrialBalanceUpload.uploaded_at.asc())
        .all()
    )
    if not uploads:
        raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")

    all_stmts = _build_period_statements(company_id, uploads)
    if not all_stmts:
        raise HTTPException(422, "Could not build statements.")

    scope22 = None
    if (basis_type or "").lower() not in ("all", ""):
        scope22 = scope_from_params(basis_type, period or None, year_scope or None,
                                     from_period or None, to_period or None, all_stmts)
        if scope22.get("error"):
            raise HTTPException(400, scope22["error"])
        windowed = filter_by_scope(all_stmts, scope22)
    else:
        windowed = filter_periods(all_stmts,
                                  window.upper() if window.upper() in VALID_WINDOWS else "ALL")

    available = sorted(s.get("period", "") for s in windowed if s.get("period"))
    resolved_scope = scope22 if scope22 else {
        "basis_type": "all",
        "label":      f"{available[0]} → {available[-1]}" if len(available) > 1
                      else (available[0] if available else "all"),
        "months":      available,
        "year":        None,
        "from_period": available[0]  if available else None,
        "to_period":   available[-1] if available else None,
        "error":       None,
    }

    analysis = run_analysis(windowed)
    result   = _build_forecast(analysis, lang=safe_lang)

    return {
        "status":       "success",
        "company_id":   company_id,
        "company_name": company.name,
        "data":         result,
        "meta": {
            "scope":             resolved_scope,
            "period_count":      analysis.get("period_count", 0),
            "periods":           analysis.get("periods", []),
            "lang":              safe_lang,
            "currency":          company.currency or "",
            "pipeline_validation": {},  # validation not run in this endpoint
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 29.5 — Executive aggregate endpoint
#  Single fetch for ExecutiveDashboard — no formula changes, pure consolidation
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{company_id}/executive")
def get_executive(
    company_id:  str,
    lang:        str = Query(default="en"),
    window:      str = Query(default="ALL"),
    basis_type:  str = Query(default="all"),
    period:      str = Query(default=""),
    year_scope:  str = Query(default="", alias="year"),
    from_period: str = Query(default=""),
    to_period:   str = Query(default=""),
    consolidate: bool = Query(default=False, description="true = merge all branch TBs per period"),
    branch_id:   str  = Query(default="", description="single branch TB scope (mutually exclusive with consolidate)"),
    db: Session = Depends(get_db),
):
    """
    Phase 29.5 — Executive aggregate.
    Consolidates intelligence + decisions + alerts + root-causes + KPIs
    into a single response for ExecutiveDashboard.
    No new logic — calls same engines as individual endpoints.
    """
    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company, all_stmts, windowed, resolved_scope, scope22 = _product_windowed_statements(
        db,
        company_id,
        consolidate=consolidate,
        branch_id=branch_id or None,
        window=window,
        basis_type=basis_type,
        period=period,
        year_scope=year_scope,
        from_period=from_period,
        to_period=to_period,
    )

    # ── Shared computation (done once, reused below) ──────────────────────────
    analysis     = run_analysis(windowed)
    annual       = build_annual_layer(windowed)
    cashflow_raw = build_cashflow(windowed)

    # ── Intelligence (ratios, trends, anomalies, health_score_v2) ────────────
    intelligence = build_intelligence(
        analysis     = analysis,
        annual_layer = annual,
        currency     = company.currency or "",
    )

    # ── Alerts ────────────────────────────────────────────────────────────────
    alerts_data = build_alerts(intelligence, lang=safe_lang)

    # ── Decisions (top 3 CFO-level) ───────────────────────────────────────────
    dec_result = build_cfo_decisions(
        intelligence=intelligence,
        alerts=alerts_data.get("alerts", []),
        lang=safe_lang,
        n_periods=analysis.get("period_count", 3),
        analysis=analysis,
        branch_context=_branch_context_for_cfo_decisions(db, company_id),
    )

    # ── Root causes ───────────────────────────────────────────────────────────
    rc_result = _build_root_causes(
        intelligence = intelligence,
        decisions    = dec_result.get("decisions", []),
        lang         = safe_lang,
        n_periods    = analysis.get("period_count", 3),
    )

    # ── Deep intelligence (Phase 47) — deterministic, data-backed ─────────────
    deep_intelligence: dict = {}
    try:
        from app.services.deep_intelligence import build_deep_intelligence
        deep_intelligence = build_deep_intelligence(windowed, analysis, lang=safe_lang)
    except Exception as _di_exc:
        logger.warning("exec deep_intelligence failed: %s", _di_exc)
        deep_intelligence = {}

    profitability_intelligence: dict = {}
    try:
        from app.services.deep_intelligence import build_executive_profitability_intelligence
        profitability_intelligence = build_executive_profitability_intelligence(
            windowed, analysis, lang=safe_lang
        )
    except Exception as _epi_exc:
        logger.warning("exec profitability_intelligence failed: %s", _epi_exc)
        profitability_intelligence = {"available": False, "reason": str(_epi_exc)}

    trend_analysis: dict = {}
    try:
        from app.services.deep_intelligence import build_executive_trend_analysis
        trend_analysis = build_executive_trend_analysis(windowed, analysis, lang=safe_lang)
    except Exception as _ta_exc:
        logger.warning("exec trend_analysis failed: %s", _ta_exc)
        trend_analysis = {"available": False, "reason": str(_ta_exc)}

    # ── KPI block — window-consistent ──────────────────────────────────────────
    # When scope is active (month/year): pass windowed+"ALL" so filter is a no-op.
    # When rolling window: pass all_stmts+window so build_kpi_block filters internally.
    # Either way enrich_kpi() uses w_* (windowed series) and produces correct SUM.
    _exec_use_scope = scope22 is not None
    if _exec_use_scope:
        kpi_block = build_kpi_block(windowed, "ALL")
    else:
        _win_label = window.upper() if window.upper() in VALID_WINDOWS else "ALL"
        kpi_block  = build_kpi_block(all_stmts, _win_label)

    # ── Forecast (canonical: forecast_engine only; same object as GET /forecast) ─
    try:
        forecast_pkg = _build_forecast(analysis, lang=safe_lang)
    except Exception as _fc_exc:
        logger.warning("exec forecast_engine failed: %s", _fc_exc)
        forecast_pkg = {"available": False, "reason": str(_fc_exc)}

    intelligence_out = dict(intelligence)
    intelligence_out["surface_scores"] = build_intel_surface_scores(
        intelligence, alerts_data.get("alerts", [])
    )
    intel_tile_hints = build_intel_tile_hints(cashflow_raw, kpi_block)

    # ── Advanced metrics (EBITDA, risk scores) ─────────────────────────────
    try:
        advanced_metrics = _compute_adv(windowed, analysis.get("ratios", {}))
    except Exception as _adv_exc:
        logger.warning("exec advanced_metrics failed: %s", _adv_exc)
        advanced_metrics = {}

    # ── Statement bundle (Phase 32.9) ───────────────────────────────────────
    statement_bundle = _build_statements(
        windowed     = windowed,
        cashflow_raw = cashflow_raw,
        intelligence = intelligence,
        lang         = safe_lang,
    )
    _structured_overlay = extract_structured_financial_overlay(statement_bundle)
    statements_nested = strip_structured_keys_for_nested_statements(statement_bundle)

    # ── Comparative Intelligence (company + branches; no group logic) ─────────
    comparative_intelligence: dict = {
        "branch_rankings": {},
        "cost_pressure": {},
        "efficiency_ranking": {},
        "category_comparison": {},
    }
    company_expense_bundle: dict | None = None
    try:
        from app.services.expense_intelligence_engine import build_expense_intelligence_bundle
        from app.services.comparative_intelligence import build_comparative_intelligence
        from app.models.branch import Branch as _BranchModel

        _periods_in_scope = set(resolved_scope.get("months") or [])

        # Company bundle first (executive expense_intel + decisions + brain share this).
        company_for_compare = None
        try:
            _cons_stmts = _build_consolidated_statements(company_id, db)
            if _cons_stmts:
                if _periods_in_scope:
                    _cons_stmts = [s for s in _cons_stmts if (s.get("period") in _periods_in_scope)]
                company_for_compare = _cons_stmts
        except Exception:
            company_for_compare = None

        company_expense_bundle = build_expense_intelligence_bundle(
            company_for_compare or windowed, lang=safe_lang
        )

        _branches_active = (
            db.query(_BranchModel)
            .filter(_BranchModel.company_id == company_id, _BranchModel.is_active == True)  # noqa
            .all()
        )

        branch_bundles: list[dict] = []
        for _b in _branches_active:
            _b_uploads = (
                db.query(TrialBalanceUpload)
                .filter(
                    TrialBalanceUpload.branch_id == _b.id,
                    TrialBalanceUpload.status == "ok",
                )
                .order_by(TrialBalanceUpload.uploaded_at.asc())
                .all()
            )
            if not _b_uploads:
                continue

            _b_stmts_all = _build_period_statements(company_id, _b_uploads)
            if not _b_stmts_all:
                continue

            if _periods_in_scope:
                _b_stmts = [s for s in _b_stmts_all if (s.get("period") in _periods_in_scope)]
            else:
                _b_stmts = _b_stmts_all

            if not _b_stmts:
                continue

            _bundle = build_expense_intelligence_bundle(_b_stmts, lang=safe_lang)
            branch_bundles.append(
                {
                    "branch_id": _b.id,
                    "branch_name": _b.name,
                    "expense_bundle": _bundle,
                }
            )

        if branch_bundles:
            comparative_intelligence = build_comparative_intelligence(
                company_expense_bundle=company_expense_bundle,
                branch_bundles=branch_bundles,
            )
    except Exception as _ci_exc:
        logger.warning("comparative_intelligence build failed: %s", _ci_exc)

    if company_expense_bundle is None:
        try:
            from app.services.expense_intelligence_engine import build_expense_intelligence_bundle as _beb_fb

            _periods_fb = set(resolved_scope.get("months") or [])
            _cons_fb = None
            try:
                _cons_fb = _build_consolidated_statements(company_id, db)
                if _cons_fb and _periods_fb:
                    _cons_fb = [s for s in _cons_fb if (s.get("period") in _periods_fb)]
            except Exception:
                pass
            company_expense_bundle = _beb_fb(_cons_fb or windowed, lang=safe_lang)
        except Exception as _fb_exc:
            logger.warning("expense bundle fallback failed: %s", _fb_exc)
            company_expense_bundle = {
                "expense_analysis": {
                    "meta": {"error": "unavailable"},
                    "by_period": [],
                },
                "expense_anomalies": [],
                "expense_decisions": [],
                "expense_explanation": {},
            }

    try:
        from app.services.expense_intelligence_engine import build_expense_intelligence_executive_view

        expense_intelligence = build_expense_intelligence_executive_view(company_expense_bundle)
    except Exception as _ei_exc:
        logger.warning("expense_intelligence executive view failed: %s", _ei_exc)
        expense_intelligence = {
            "available": False,
            "reason": "build_failed",
            "categories": {},
            "totals": None,
            "top_category": None,
            "mom_change": None,
            "expense_ratio": None,
            "anomalies": [],
            "decisions": [],
        }

    # ── Decision impacts (Phase 32) ──────────────────────────────────────────
    decision_impacts = _build_impacts(
        decisions    = dec_result.get("decisions", []),
        intelligence = intelligence,
        kpi_block    = kpi_block,
        lang         = safe_lang,
    )

    # ── Derive top_focus from #1 decision ────────────────────────────────────
    top_decision = dec_result.get("decisions", [{}])[0]
    top_focus    = top_decision.get("title") or dec_result.get("summary", {}).get("top_focus")

    # ── FIX-4.1: Validation layer — runs in ALL main endpoints ─────────────
    exec_validation: dict = {}
    try:
        exec_validation = _validate_pipeline(windowed, analysis, cashflow_raw)
    except Exception as _ve:
        logger.warning("exec _validate_pipeline failed: %s", _ve)
        exec_validation = {"consistent": None, "warnings": [], "checked": 0,
                           "error": str(_ve)}

    _exec_integrity = _assess_financial_integrity(exec_validation)
    _gov_block = _exec_integrity.get("suppress_governance_outputs", False)

    # ── Expense decisions upgrade (company-level; additive) ───────────────────
    expense_decisions_v2: list = []
    try:
        from app.services.expense_decisions_upgrade import build_company_expense_decisions_v2

        expense_decisions_v2 = build_company_expense_decisions_v2(
            company_id=company_id,
            company_name=company.name,
            currency=(company.currency or ""),
            company_bundle=company_expense_bundle,
            comparative_intelligence=comparative_intelligence,
            lang=safe_lang,
        )
    except Exception as _ed2_exc:
        logger.warning("expense_decisions_v2 build failed: %s", _ed2_exc)

    # ── Financial brain (explainable reasoning; additive) ─────────────────────
    financial_brain: dict = {"available": False, "reason": "unavailable"}
    try:
        from app.services.financial_brain import build_financial_brain_company

        financial_brain = build_financial_brain_company(
            company_id=company_id,
            company_name=company.name,
            currency=(company.currency or ""),
            expense_bundle=company_expense_bundle,
            comparative_intelligence=comparative_intelligence,
            expense_decisions_v2=expense_decisions_v2,
            anomalies=(company_expense_bundle or {}).get("expense_anomalies") or [],
            lang=safe_lang,
        )
    except Exception as _fb_exc:
        logger.warning("financial_brain build failed: %s", _fb_exc)

    # ── Realized causal (single UI-facing financial wording source) ───────────
    from app.services.causal_realize import realize_causal_items

    _merged_causal_exec = _merge_causal_sources_for_realize(
        dec_result, deep_intelligence, profitability_intelligence
    )
    realized_causal_items = realize_causal_items(_merged_causal_exec, safe_lang)
    _raw_cfo_causal = dec_result.get("causal_items") or []
    _realized_cfo_only = realize_causal_items(_raw_cfo_causal, safe_lang)
    decisions_for_api: list[dict] = []
    for i, dec in enumerate(dec_result.get("decisions", [])):
        row = dict(dec)
        if i < len(_realized_cfo_only):
            r = _realized_cfo_only[i]
            row["causal_realized"] = {
                "id": r.get("id"),
                "change_text": r.get("change_text") or "",
                "cause_text": r.get("cause_text") or "",
                "action_text": r.get("action_text") or "",
            }
        decisions_for_api.append(row)

    # ── Phase 2: integrity gate — strip governance outputs when validation errors ─
    if _gov_block:
        top_focus = None
        decisions_for_api = []
        realized_causal_items = []
        expense_decisions_v2 = []
        financial_brain = {"available": False, "reason": "data_integrity_blocking"}
        deep_intelligence = {"available": False, "reason": "data_integrity_blocking"}
        profitability_intelligence = {"available": False, "reason": "data_integrity_blocking"}
        trend_analysis = {"available": False, "reason": "data_integrity_blocking"}
        decision_impacts = {}
        intel_tile_hints = {
            "liquidity_primary": None,
            "liquidity_ocf": None,
            "liquidity_wc": None,
            "efficiency_primary": None,
            "efficiency_expense_mom": None,
            "efficiency_net_margin_pct": None,
        }
        intelligence_out = {**intelligence_out, "integrity_gated": True, "surface_scores": {}}
        alerts_data = {"alerts": [], "summary": {}}
        rc_result = {"causes": [], "summary": {"integrity_blocked": True}}

    # ── Canonical response — single source of truth ──────────────────────────
    _all_periods = sorted(s.get("period", "") for s in all_stmts if s.get("period"))
    return {
        "status":       "success",
        "company_id":   company_id,
        "company_name": company.name,
        "currency":     company.currency or "",
        "data_source": (
            "branch_upload"
            if (branch_id or "").strip()
            else ("branch_consolidation" if consolidate else "direct_uploads")
        ),

        "data": {
            **_structured_overlay,
            # ── Health ────────────────────────────────────────────────────────
            "health_score_v2":   (None if _gov_block else intelligence.get("health_score_v2")),
            "status":            ("integrity_blocked" if _gov_block else intelligence.get("status")),
            "top_focus":         top_focus,

            # ── Intelligence (ratios, trends, anomalies, surface_scores) ────
            "intelligence":      intelligence_out,
            "intel_tile_hints":  intel_tile_hints,

            # ── KPI block (windowed, SUM for flow / LAST for rates) ───────────
            "kpi_block":         kpi_block,

            # ── Cash flow ─────────────────────────────────────────────────────
            "cashflow":          cashflow_raw,

            # ── Decisions ─────────────────────────────────────────────────────
            "decisions":         decisions_for_api,
            "realized_causal_items": realized_causal_items,
            "decisions_summary": dec_result.get("summary", {}),
            "recommendations":   [] if _gov_block else dec_result.get("recommendations", []),

            # ── Alerts ────────────────────────────────────────────────────────
            "alerts":            alerts_data.get("alerts", [])[:5],
            "alerts_summary":    alerts_data.get("summary", {}),

            # ── Root causes ───────────────────────────────────────────────────
            "root_causes":       rc_result.get("causes", [])[:8],
            "root_causes_summary": rc_result.get("summary", {}),

            # ── Deep intelligence (drivers/anomalies/signals) ─────────────────
            "deep_intelligence": deep_intelligence,

            # ── Financial Brain Phase 1 — profitability diagnostics (additive) ─
            "profitability_intelligence": profitability_intelligence,

            # ── Trend analysis (current vs previous, volatility) ──────────────
            "trend_analysis":    trend_analysis,

            # ── Forecast (forecast_engine — identical to GET /forecast) ─────
            "forecast":         forecast_pkg,

            # ── Decision impacts ──────────────────────────────────────────────
            "decision_impacts":  decision_impacts,

            # ── Statement bundle (no duplicate structured_* — see root overlay) ─
            "statements":        statements_nested,

            # ── Comparative intelligence (branches within company) ────────────
            "comparative_intelligence": comparative_intelligence,

            # ── Expense intelligence (structured UI + same source as v2 decisions) ─
            "expense_intelligence": expense_intelligence,

            # ── Expense decisions upgrade (additive; does not replace expense_decisions) ─
            "expense_decisions_v2": expense_decisions_v2,

            # ── Financial brain (explainable reasoning; additive) ─────────────
            "financial_brain": financial_brain,

            # ── Annual layer (full-year strips) ───────────────────────────────
            "annual_layer":      annual,

            # ── Advanced metrics (EBITDA, risk scores) ────────────────────────
            "advanced_metrics":  advanced_metrics,
        },

        "meta": {
            "scope":              resolved_scope,
            "period_count":       analysis.get("period_count", 0),
            "periods":            analysis.get("periods", []),
            "all_periods":        _all_periods,
            "window":             window,
            "lang":               safe_lang,
            "currency":           company.currency or "",
            "pipeline_validation": exec_validation,
            "integrity": {**_exec_integrity, "pipeline_validation": exec_validation},
            "product_intelligence": {
                "primary_engine": "fin_intelligence.build_intelligence",
                "alerts_engine": "alerts_engine.build_alerts",
                "decision_engine": "cfo_decision_engine.build_cfo_decisions",
                "interpretation_secondary": [
                    "deep_intelligence",
                    "profitability_intelligence",
                    "trend_analysis",
                    "financial_brain",
                ],
                "legacy_non_product": "intelligence_engine.run_intelligence — GET /{company_id} aggregate only",
                "scenario_ranker": "POST /{company_id}/decisions — not CFO primary decisions",
            },
            "metric_semantics": {
                "kpi_block_flow_is_sum_over_window": True,
                "kpi_block_rates_are_last_period_in_window": True,
                "statement_summary_flow_is_sum_over_window": True,
                "statement_income_detail_is_latest_period": True,
                "formula_opex_ratio_pct": "operating_expenses / revenue * 100",
                "formula_cogs_ratio_pct": "cogs / revenue * 100",
                "formula_total_cost_ratio_pct":
                    "(cogs + operating_expenses + unclassified_pnl_debits) / revenue * 100",
            },
        },
    }


# ── GET /{company_id}/advisor-context ─────────────────────────────────────────

@router.get("/{company_id}/advisor-context")
def get_advisor_context(
    company_id:  str,
    window:      str  = Query(default="ALL"),
    scope:       str  = Query(default="company"),
    branch_id:   str  = Query(default=None),
    lang:        str  = Query(default="en"),
    db:          Session = Depends(get_db),
):
    """
    Build full AI CFO context for the advisor.
    Returns all financial data the AI needs to answer any question.
    No recalculation — assembles from existing engines.
    """
    from app.services.vcfo_advisor_context import build_advisor_context
    from app.services.vcfo_ai_advisor import build_quick_actions

    # Membership enforced by router-level Depends(require_company_access)

    try:
        ctx = build_advisor_context(
            company_id = company_id,
            db         = db,
            window     = window,
            scope      = scope,
            branch_id  = branch_id,
            lang       = lang,
        )
        ctx["quick_actions"] = build_quick_actions(ctx, lang)
        return ctx
    except Exception as exc:
        logger.warning("advisor-context failed: %s", exc)
        raise HTTPException(500, "Internal processing error")
