from app.core.security import get_current_user
from app.services.analysis_engine import run_analysis, compute_trends, _trend_direction
from app.services.root_cause_engine import build_root_causes
from app.services.anomaly_engine    import detect_anomalies
from app.services.narrative_builder import build_narratives
"""
api/branches.py — Phase 7.6
Branch management + comparison engine.

Endpoints:
  POST   /branches                        → create branch
  GET    /branches?company_id=            → list branches for company
  GET    /branches/{branch_id}            → get branch
  DELETE /branches/{branch_id}            → soft-delete
  GET    /branches/{branch_id}/financials → financial history
  GET    /companies/{company_id}/branch-comparison
         → ranking, top/bottom, margin comparison

Branch financials are populated via the normal upload flow:
  POST /uploads with branch_id form field → triggers branch_financial upsert
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_company_access, require_active_membership
from app.models.branch import Branch, BranchFinancial
from app.models.company import Company
from app.models.trial_balance import TrialBalanceUpload
from app.services.financial_statements import build_statements, statements_to_dict
from app.services.metric_definitions import cogs_ratio_pct, opex_ratio_pct, total_cost_ratio_pct

router = APIRouter(tags=["branches"])

logger = logging.getLogger("vcfo.branches")

# Rolling windows — same vocabulary as company analysis / executive
_VALID_BRANCH_WINDOWS = frozenset({"3M", "6M", "12M", "YTD", "ALL"})


def _scoped_branch_statements(
    stmts_all: list[dict],
    *,
    window: str,
    basis_type: str,
    period: str,
    year_scope: str,
    from_period: str,
    to_period: str,
) -> tuple[list[dict], str]:
    """
    Phase 22 parity with company executive:
    if basis_type is set and not 'all' → scope_from_params + filter_by_scope
    else → filter_periods(window)
    """
    from app.services.time_intelligence import filter_periods
    from app.services.time_scope import filter_by_scope, scope_from_params

    _win = (window or "ALL").strip().upper()
    if _win not in _VALID_BRANCH_WINDOWS:
        _win = "ALL"

    if (basis_type or "").lower() not in ("all", ""):
        scope22 = scope_from_params(
            basis_type,
            period or None,
            year_scope or None,
            from_period or None,
            to_period or None,
            stmts_all,
        )
        if scope22.get("error"):
            raise HTTPException(status_code=400, detail=scope22["error"])
        stmts = filter_by_scope(stmts_all, scope22)
    else:
        stmts = filter_periods(stmts_all, _win) if _win != "ALL" else stmts_all

    if not stmts:
        stmts = stmts_all[-1:]
    return stmts, _win

# ── Metric Resolver shadow-mode (log-only) ────────────────────────────────────
from app.services.metric_resolver import MetricResolver  # local import is OK: pure functions
from app.services.confidence_engine import score_confidence
from app.services.attribution_engine import profit_bridge_attribution

_BR_METRIC_SHADOW_KEYS = (
    "revenue",
    "net_profit",
    "net_margin_pct",
    "operating_expenses",
    "total_cost_ratio_pct",
    "working_capital",
    "operating_cashflow",
)


def _shadow_compare_metrics(
    *,
    resolver: MetricResolver,
    current: dict,
    label: str,
) -> None:
    try:
        for k in _BR_METRIC_SHADOW_KEYS:
            rv = resolver.get(k)
            cv = current.get(k)
            if rv is None and cv is None:
                continue
            tol = 0.05
            if k in ("revenue", "net_profit", "operating_expenses", "working_capital", "operating_cashflow"):
                tol = 0.5
            if k in ("total_cost_ratio_pct", "net_margin_pct"):
                tol = 0.05
            try:
                if rv is None or cv is None:
                    if (rv is None) != (cv is None):
                        logger.warning("metric-shadow %s %s mismatch: resolver=%s current=%s meta=%s", label, k, rv, cv, resolver.meta())
                    continue
                diff = abs(float(rv) - float(cv))
                if diff > tol:
                    logger.warning("metric-shadow %s %s mismatch: resolver=%s current=%s diff=%.4f meta=%s", label, k, rv, cv, diff, resolver.meta())
            except Exception:
                if rv != cv:
                    logger.warning("metric-shadow %s %s mismatch (non-numeric): resolver=%s current=%s meta=%s", label, k, rv, cv, resolver.meta())
    except Exception as exc:
        logger.warning("metric-shadow %s failed: %s", label, exc)


def _confidence_from_resolver(resolver: MetricResolver, keys: list[str]) -> dict:
    q = resolver.quality()
    missing = sum(q.get("missing_points", {}).get(k, 0) for k in keys)
    approx = bool(q.get("approximated"))
    denom = bool(q.get("denominator_risks"))
    volatile = any(resolver.trend_quality(k) == "volatile" for k in keys if k in ("revenue", "net_profit", "operating_expenses", "operating_cashflow"))
    return score_confidence(
        n_periods=int(q.get("n_periods") or 0),
        missing_points=int(missing or 0),
        approximated=approx,
        volatile=volatile,
        denom_risk=denom,
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class BranchCreate(BaseModel):
    company_id: str
    code:       Optional[str] = None
    name:       str
    name_ar:    Optional[str] = None
    city:       Optional[str] = None
    country:    Optional[str] = None
    currency:   str = "USD"

    @field_validator("company_id")
    @classmethod
    def company_id_required(cls, v: str) -> str:
        if v is None or not str(v).strip():
            raise ValueError("company_id is required and cannot be empty")
        return str(v).strip()

    @field_validator("name")
    @classmethod
    def name_non_empty(cls, v: str) -> str:
        if v is None or not str(v).strip():
            raise ValueError("name is required")
        return str(v).strip()


class BranchUpdate(BaseModel):
    code:      Optional[str] = None
    name:      Optional[str] = None
    name_ar:   Optional[str] = None
    city:      Optional[str] = None
    country:   Optional[str] = None
    currency:  Optional[str] = None
    is_active: Optional[bool] = None


class BranchResponse(BaseModel):
    id:         str
    company_id: str
    code:       Optional[str]
    name:       str
    name_ar:    Optional[str]
    city:       Optional[str]
    country:    Optional[str]
    currency:   str
    is_active:  bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Branch CRUD ───────────────────────────────────────────────────────────────

@router.post("/branches", response_model=BranchResponse, status_code=201)
def create_branch(
    payload:      BranchCreate,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    company = db.query(Company).filter(Company.id == payload.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    membership = require_active_membership(db, current_user.id, payload.company_id)
    if membership.role not in ("owner", "analyst"):
        raise HTTPException(status_code=403, detail="Viewer role cannot create branches")
    branch = Branch(**payload.model_dump())
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch


@router.get("/branches", response_model=list[BranchResponse])
def list_branches(
    company_id:   str,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    require_active_membership(db, current_user.id, company_id)
    return (
        db.query(Branch)
        .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa
        .order_by(Branch.name)
        .all()
    )


@router.get("/branches/{branch_id}", response_model=BranchResponse)
def get_branch(
    branch_id:    str,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    b = db.query(Branch).filter(Branch.id == branch_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Branch not found")
    require_active_membership(db, current_user.id, b.company_id)
    return b


@router.delete("/branches/{branch_id}", status_code=204)
def delete_branch(
    branch_id:    str,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    b = db.query(Branch).filter(Branch.id == branch_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Branch not found")
    membership = require_active_membership(db, current_user.id, b.company_id)
    if membership.role not in ("owner", "analyst"):
        raise HTTPException(status_code=403, detail="Viewer role cannot delete branches")
    b.is_active = False
    db.commit()


@router.put("/branches/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id:    str,
    payload:      BranchUpdate,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    b = db.query(Branch).filter(Branch.id == branch_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Branch not found")
    membership = require_active_membership(db, current_user.id, b.company_id)
    if membership.role not in ("owner", "analyst"):
        raise HTTPException(status_code=403, detail="Viewer role cannot update branches")
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(b, field, value)
    db.commit()
    db.refresh(b)
    return b


# ── Branch financials ─────────────────────────────────────────────────────────

@router.get("/branches/{branch_id}/financials")
def get_branch_financials(
    branch_id:    str,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    b = db.query(Branch).filter(Branch.id == branch_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Branch not found")
    require_active_membership(db, current_user.id, b.company_id)

    financials = (
        db.query(BranchFinancial)
        .filter(BranchFinancial.branch_id == branch_id)
        .order_by(BranchFinancial.period)
        .all()
    )

    return {
        "branch_id":   branch_id,
        "branch_name": b.name,
        "periods":     [f.period for f in financials],
        "financials":  [
            {
                "period":       f.period,
                "revenue":      f.revenue,
                "expenses":     f.expenses,
                "gross_profit": f.gross_profit,
                "net_profit":   f.net_profit,
                "total_assets": f.total_assets,
                "net_margin":   round(f.net_profit / f.revenue * 100, 2)
                                if (f.revenue is not None and f.revenue > 0
                                    and f.net_profit is not None) else None,
            }
            for f in financials
        ],
    }


# ── Branch analysis helpers ───────────────────────────────────────────────────

def _bf_to_stmt_dict(bf: "BranchFinancial") -> dict:
    """
    Convert a BranchFinancial row into a synthetic statement dict
    compatible with analysis_engine.compute_ratios() and compute_trends().
    Only the fields stored in branch_financials are populated.
    BS-derived ratios (liquidity, leverage) will be None — that's correct.
    """
    rev  = bf.revenue    or 0.0
    cogs = bf.cogs       or 0.0
    gp   = bf.gross_profit if bf.gross_profit is not None else (rev - cogs)
    exp  = bf.expenses   or 0.0
    np_  = bf.net_profit if bf.net_profit is not None else (gp - exp)
    ta   = bf.total_assets or 0.0

    gm_pct = round(gp / rev * 100, 2) if rev > 0 else 0.0
    nm_pct = round(np_ / rev * 100, 2) if rev > 0 else 0.0
    op_    = gp - exp
    om_pct = round(op_ / rev * 100, 2) if rev > 0 else 0.0
    rv_f = rev if rev else None
    ox_r = opex_ratio_pct(exp, rv_f)
    cg_r = cogs_ratio_pct(cogs, rv_f)
    tc_r = total_cost_ratio_pct(cogs, exp, rv_f, 0.0)

    return {
        "period": bf.period,
        "company_id": bf.company_id,
        "data_scope": "branch",
        "branch_id": getattr(bf, "branch_id", None),
        "income_statement": {
            "revenue":          {"total": rev,  "items": []},
            "cogs":             {"total": cogs, "items": []},
            "gross_profit":     gp,
            "gross_margin_pct": gm_pct,
            "expenses":         {"total": exp, "items": []},
            "unclassified_pnl_debits": {"items": [], "total": 0.0},
            "operating_profit": op_,
            "operating_margin_pct": om_pct,
            "tax":              {"total": 0.0,  "items": []},
            "net_profit":       np_,
            "net_margin_pct":   nm_pct,
            "opex_ratio_pct":       ox_r,
            "cogs_ratio_pct":       cg_r,
            "total_cost_ratio_pct": tc_r,
            "expense_ratio_pct":    tc_r,
        },
        "balance_sheet": {
            "assets":      {"total": ta, "items": []},
            "liabilities": {"total": 0.0, "items": []},
            "equity":      {"total": 0.0, "items": []},
            "current_assets":      None,
            "current_liabilities": None,
            "working_capital":     None,
            "total_assets":        ta,
            "is_balanced":         False,
        },
    }


# ── GET /branches/{branch_id}/analysis ───────────────────────────────────────

@router.get("/branches/{branch_id}/analysis")
def get_branch_analysis(
    branch_id:    str,
    window:       str = Query(default="ALL", description="3M | 6M | 12M | YTD | ALL"),
    lang:         str = Query(default="en"),
    basis_type:   str = Query(default="all"),
    period:       str = Query(default=""),
    year_scope:   str = Query(default="", alias="year"),
    from_period:  str = Query(default=""),
    to_period:    str = Query(default=""),
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Branch-level financial analysis using the existing analysis pipeline.

    Converts BranchFinancial rows → synthetic statement dicts →
    run_analysis() — same core as company path. Optional time window.
    Additive: deep_intelligence, phase43_root_causes, cfo_decisions (financial brain V1).
    """
    from app.services.alerts_engine import build_alerts
    from app.services.analysis_engine                       import run_analysis
    from app.services.cfo_decision_engine import build_cfo_decisions
    from app.services.deep_intelligence import build_deep_intelligence
    from app.services.fin_intelligence import build_intelligence
    from app.services.period_aggregation import build_annual_layer
    from app.services.root_cause_engine import build_root_causes, derive_phase43_metrics_trends

    b = db.query(Branch).filter(Branch.id == branch_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Branch not found")

    require_active_membership(db, current_user.id, b.company_id)

    financials = (
        db.query(BranchFinancial)
        .filter(BranchFinancial.branch_id == branch_id)
        .order_by(BranchFinancial.period)
        .all()
    )

    if not financials:
        return {
            "branch_id":    branch_id,
            "branch_name":  b.name,
            "branch_code":  getattr(b, "code", None),
            "company_id":   b.company_id,
            "has_data":     False,
            "message":      "No financial data uploaded for this branch yet.",
        }

    stmts_all = [_bf_to_stmt_dict(f) for f in financials]
    stmts, _win = _scoped_branch_statements(
        stmts_all,
        window=window,
        basis_type=basis_type,
        period=period,
        year_scope=year_scope,
        from_period=from_period,
        to_period=to_period,
    )

    safe_lang = lang if lang in ("en", "ar", "tr") else "en"
    company = db.query(Company).filter(Company.id == b.company_id).first()

    analysis = run_analysis(stmts)
    trends   = analysis.get("trends") or {}

    latest_stmt = stmts[-1]
    latest_is   = latest_stmt.get("income_statement", {})
    latest_bf   = financials[-1]

    rev  = latest_is.get("revenue",  {}).get("total", 0) or 0
    exp  = latest_is.get("expenses", {}).get("total", 0) or 0
    exp_ratio_legacy = round(exp / rev * 100, 2) if rev > 0 else None
    tc_ratio = latest_is.get("total_cost_ratio_pct")

    # ── Insights ──────────────────────────────────────────────────────────────
    rev_series = trends.get("revenue_series",    [])
    np_series  = trends.get("net_profit_series", [])
    mom_rev    = trends.get("revenue_mom_pct") or trends.get("revenue_mom") or []

    growing     = len([x for x in (mom_rev or []) if x is not None and x > 0])
    declining   = len([x for x in (mom_rev or []) if x is not None and x < 0])
    last_mom    = next((x for x in reversed(mom_rev or []) if x is not None), None)

    insights = {
        "periods_growing":  growing,
        "periods_declining": declining,
        "last_mom_revenue": last_mom,
        "trend": (
            "growing"   if growing > declining else
            "declining" if declining > growing else
            "stable"
        ),
        "avg_revenue":    round(sum(rev_series) / len(rev_series), 2) if rev_series else None,
        "avg_net_profit": round(sum(np_series)  / len(np_series),  2) if np_series  else None,
        "profitable":     (latest_is.get("net_profit", 0) or 0) > 0,
    }

    deep_intel: dict = {}
    rc_phase43: list  = []
    decisions: list  = []
    branch_recommendations: list = []
    try:
        deep_intel = build_deep_intelligence(stmts, analysis, safe_lang)
    except Exception as exc:
        logger.warning("branch analysis deep_intelligence failed: %s", exc)
    try:
        _m43, _t43 = derive_phase43_metrics_trends(stmts, analysis)
        rc_phase43 = build_root_causes(_m43, _t43, lang=safe_lang)
    except Exception as exc:
        logger.warning("branch analysis phase43 root causes failed: %s", exc)
    try:
        annual = build_annual_layer(stmts)
        intel_b = build_intelligence(
            analysis=analysis, annual_layer=annual, currency=(company.currency if company else "") or "",
        )
        al_b = build_alerts(intel_b, lang=safe_lang).get("alerts", [])
        _pack_b = build_cfo_decisions(
            intel_b,
            al_b,
            lang=safe_lang,
            n_periods=len(stmts),
            analysis=analysis,
            branch_context=None,
        )
        decisions = _pack_b.get("decisions", [])
        branch_recommendations = _pack_b.get("recommendations", [])
    except Exception as exc:
        logger.warning("branch analysis CFO decisions failed: %s", exc)
        branch_recommendations = []

    branch_forecast: dict = {}
    try:
        from app.services.deep_intelligence import (
            build_executive_basic_forecast,
            build_executive_forecast_unavailable,
        )

        branch_forecast = build_executive_basic_forecast(stmts, analysis, lang=safe_lang)
    except Exception as _bfc_exc:
        logger.warning("branch analysis forecast failed: %s", _bfc_exc)
        from app.services.deep_intelligence import build_executive_forecast_unavailable

        branch_forecast = build_executive_forecast_unavailable(safe_lang, reason="unavailable")

    # ── Metric Resolver shadow-mode comparisons (log-only) ────────────────────
    try:
        from app.services.cashflow_engine import build_cashflow
        cf_raw = build_cashflow(stmts)
        _resolver = MetricResolver.from_statements(
            period_statements=stmts,
            scope="branch",
            window=_win,  # type: ignore[arg-type]
            currency=(company.currency if company else "") or "",
            analysis=analysis,
            cashflow=cf_raw,
        )
        _cur = {
            "revenue": rev,
            "net_profit": latest_is.get("net_profit"),
            "net_margin_pct": latest_is.get("net_margin_pct"),
            "operating_expenses": latest_is.get("expenses", {}).get("total"),
            "total_cost_ratio_pct": tc_ratio,
            "working_capital": (analysis.get("latest", {}).get("liquidity", {}) or {}).get("working_capital"),
            "operating_cashflow": cf_raw.get("operating_cashflow") if isinstance(cf_raw, dict) else None,
        }
        # Normalize nested dict ratios if present
        if isinstance(_cur.get("working_capital"), dict) and "value" in _cur["working_capital"]:
            _cur["working_capital"] = _cur["working_capital"].get("value")
        _shadow_compare_metrics(resolver=_resolver, current=_cur, label="branch-analysis")
    except Exception:
        pass

    # ── Evidence blocks (additive) ────────────────────────────────────────────
    try:
        # Reuse the resolver we just built when available; otherwise build a minimal one.
        if "cf_raw" in locals():
            _resolver_e = MetricResolver.from_statements(
                period_statements=stmts,
                scope="branch",
                window=_win,  # type: ignore[arg-type]
                currency=(company.currency if company else "") or "",
                analysis=analysis,
                cashflow=cf_raw if isinstance(cf_raw, dict) else None,
            )
        else:
            _resolver_e = MetricResolver.from_statements(
                period_statements=stmts,
                scope="branch",
                window=_win,  # type: ignore[arg-type]
                currency=(company.currency if company else "") or "",
                analysis=analysis,
                cashflow=None,
            )

        # deep intelligence meta evidence
        if isinstance(deep_intel, dict):
            deep_intel.setdefault("evidence", {"meta": _resolver_e.meta(), "quality": _resolver_e.quality()})

        # decisions evidence
        for d in (decisions or []):
            dom = str(d.get("domain") or "").lower()
            keys = ["revenue", "net_profit", "total_cost_ratio_pct"]
            if dom in ("profitability", "profit"):
                keys = ["net_profit", "net_margin_pct", "gross_margin_pct"]
            elif dom in ("liquidity",):
                keys = ["current_ratio", "quick_ratio", "working_capital"]
            elif dom in ("cashflow",):
                keys = ["operating_cashflow", "working_capital"]
            d["evidence"] = {"meta": _resolver_e.meta(), "metrics": [{"key": k, **_resolver_e.delta(k)} for k in keys], "quality": _resolver_e.quality()}
            d["confidence"] = _confidence_from_resolver(_resolver_e, keys)
            if dom in ("profitability", "profit"):
                d["attribution"] = profit_bridge_attribution(
                    revenue_delta=_resolver_e.delta("revenue").get("delta"),
                    prior_net_margin_pct=_resolver_e.delta("net_margin_pct").get("previous"),
                    cogs_ratio_delta_pct=_resolver_e.delta("cogs_ratio_pct").get("delta"),
                    opex_ratio_delta_pct=_resolver_e.delta("opex_ratio_pct").get("delta"),
                    latest_revenue=_resolver_e.delta("revenue").get("current"),
                    observed_net_profit_delta=_resolver_e.delta("net_profit").get("delta"),
                )

        # phase43 root causes evidence
        for rc in (rc_phase43 or []):
            dom = str(rc.get("domain") or rc.get("type") or "").lower()
            keys = ["revenue", "net_profit"]
            if dom in ("profitability", "profit"):
                keys = ["net_profit", "net_margin_pct", "gross_margin_pct"]
            elif dom in ("liquidity",):
                keys = ["current_ratio", "quick_ratio", "working_capital"]
            elif dom in ("cashflow",):
                keys = ["operating_cashflow", "working_capital"]
            elif dom in ("cost", "expenses", "cost_structure"):
                keys = ["total_cost_ratio_pct", "operating_expenses", "cogs_ratio_pct"]
            rc["evidence"] = {"meta": _resolver_e.meta(), "metrics": [{"key": k, **_resolver_e.delta(k)} for k in keys], "quality": _resolver_e.quality()}
            rc["confidence"] = _confidence_from_resolver(_resolver_e, keys)
    except Exception:
        pass

    return {
        "branch_id":   branch_id,
        "branch_name": b.name,
        "branch_code": getattr(b, "code", None),
        "name_ar":     b.name_ar,
        "city":        b.city,
        "country":     b.country,
        "company_id":  b.company_id,
        "has_data":    True,
        "window":      _win,
        "period_count": len(stmts),
        "total_periods_available": len(financials),
        "periods":     [s.get("period") for s in stmts],
        "all_periods": [f.period for f in financials],
        "last_period": latest_stmt.get("period") or financials[-1].period,
        "latest": {
            "revenue":             rev,
            "net_profit":          latest_is.get("net_profit"),
            "gross_profit":        latest_is.get("gross_profit"),
            "gross_margin_pct":    latest_is.get("gross_margin_pct"),
            "net_margin_pct":      latest_is.get("net_margin_pct"),
            "operating_margin_pct": latest_is.get("operating_margin_pct"),
            "expense_ratio":       tc_ratio if tc_ratio is not None else exp_ratio_legacy,
            "total_cost_ratio_pct": tc_ratio,
            "opex_ratio_pct":       latest_is.get("opex_ratio_pct"),
            "cogs_ratio_pct":       latest_is.get("cogs_ratio_pct"),
            "total_assets":        latest_bf.total_assets,
        },
        "trends":   trends,
        "analysis": {
            "latest": analysis.get("latest"),
            "trends": analysis.get("trends"),
        },
        "insights": insights,
        "deep_intelligence":     deep_intel,
        "phase43_root_causes":    rc_phase43,
        "cfo_decisions":          decisions,
        "cfo_recommendations":    branch_recommendations,
        "forecast":               branch_forecast,
    }


# ── Branch Drill-Down ─────────────────────────────────────────────────────────

@router.get("/branches/{branch_id}/drill-down")
def get_branch_drill_down(
    branch_id:  str,
    lang:       str = Query(default="en"),
    db:         Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Full branch drill-down: header, KPIs, trends, expense intelligence,
    root causes, decisions, and forecast.

    All generated text is language-aware (lang=en|ar|tr).
    All components reuse existing locked engines — no duplicate calculations.
    Branch data is isolated: no company-level data leaks into any section.

    Adjustments applied per approval:
    - forecast only when ≥3 periods of branch history exist
    - health_score_method = "rule_based" for transparency
    - expense_intelligence called with branch_financials=None (no company avg)
    - root causes fed from branch-only analysis
    - decisions fed from branch profile only (_build_branch_decisions)
    - all text fields language-aware
    """
    from app.services.alerts_engine import build_alerts
    from app.services.analysis_engine   import run_analysis, _trend_direction
    from app.services.cashflow_engine   import build_cashflow
    from app.services.cfo_decision_engine import build_cfo_decisions
    from app.services.deep_intelligence import build_deep_intelligence
    from app.services.expense_engine    import build_expense_intelligence
    from app.services.fin_intelligence import build_intelligence
    from app.services.forecast_engine   import build_forecast
    from app.services.period_aggregation import build_annual_layer
    from app.services.root_cause_engine import build_root_cause, build_root_causes, derive_phase43_metrics_trends
    from app.i18n                       import translate as _t

    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    # ── Load branch and its financial history ─────────────────────────────────
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(404, "Branch not found.")

    require_active_membership(db, current_user.id, branch.company_id)

    financials = (
        db.query(BranchFinancial)
        .filter(BranchFinancial.branch_id == branch_id)
        .order_by(BranchFinancial.period)
        .all()
    )

    if not financials:
        return {
            "branch_id":   branch_id,
            "branch_name": branch.name,
            "name_ar":     branch.name_ar,
            "city":        branch.city,
            "country":     branch.country,
            "has_data":    False,
            "status":      "active" if branch.is_active else "inactive",
        }

    # ── Build synthetic statements (branch-only — no company data) ────────────
    stmts = [_bf_to_stmt_dict(f) for f in financials]

    # ── Core analysis (reuse locked engine) ──────────────────────────────────
    analysis = run_analysis(stmts)
    trends   = analysis.get("trends", {})
    latest_r = analysis.get("latest") or {}
    prof     = latest_r.get("profitability", {})

    # ── KPIs ──────────────────────────────────────────────────────────────────
    last_is   = stmts[-1].get("income_statement", {})
    rev       = last_is.get("revenue", {}).get("total", 0) or 0
    exp_total = last_is.get("expenses", {}).get("total", 0) or 0
    _tc_r     = last_is.get("total_cost_ratio_pct")
    exp_ratio = _tc_r if _tc_r is not None else (round(exp_total / rev * 100, 2) if rev > 0 else None)

    # Operating cashflow — branch-only via build_cashflow (safe on synthetic stmts)
    ocf = None
    try:
        cf_raw = build_cashflow(stmts)
        if not cf_raw.get("error"):
            ocf = cf_raw.get("operating_cashflow")
    except Exception:
        pass

    kpis = {
        "revenue":             round(rev, 2),
        "net_profit":          round(last_is.get("net_profit", 0) or 0, 2),
        "gross_margin_pct":    prof.get("gross_margin_pct"),
        "net_margin_pct":      prof.get("net_margin_pct"),
        "expense_ratio":       exp_ratio,
        "total_cost_ratio_pct": last_is.get("total_cost_ratio_pct"),
        "opex_ratio_pct":      last_is.get("opex_ratio_pct"),
        "cogs_ratio_pct":      last_is.get("cogs_ratio_pct"),
        "operating_margin_pct":prof.get("operating_margin_pct"),
        "operating_cashflow":  ocf,
    }

    # ── Trends with loss_flag and trend_quality ───────────────────────────────
    def _trend_quality(mom_series):
        valid = [x for x in (mom_series or []) if x is not None]
        if len(valid) < 2: return "stable"
        lt = valid[-2:]
        return "volatile" if (lt[0]>0.5 and lt[1]<-0.5) or (lt[0]<-0.5 and lt[1]>0.5) else "stable"

    def _make_br_trend(series_key, mom_key):
        series = trends.get(series_key, [])
        mom    = trends.get(mom_key, [])
        vals   = [v for v in series if v is not None]
        return {
            "series":        series,
            "mom_pct":       mom,
            "direction":     _trend_direction(mom),
            "trend_quality": _trend_quality(mom),
            "loss_flag":     bool(vals and vals[-1] < 0),
        }

    branch_trends = {
        "revenue":    _make_br_trend("revenue_series",     "revenue_mom_pct"),
        "net_profit": _make_br_trend("net_profit_series",  "net_profit_mom_pct"),
        "expenses":   _make_br_trend("expenses_series",    "expenses_mom_pct"),
    }

    # ── Health score (rule-based from existing flags) ─────────────────────────
    np_latest   = kpis["net_profit"]
    nm_latest   = kpis["net_margin_pct"] or 0
    rev_dir     = branch_trends["revenue"]["direction"]
    np_dir      = branch_trends["net_profit"]["direction"]
    np_volatile = branch_trends["net_profit"]["trend_quality"] == "volatile"

    if np_latest < 0:
        health_score = 20
    elif exp_ratio and exp_ratio > 80:
        health_score = 35
    elif exp_ratio and exp_ratio > 60 and np_dir == "declining":
        health_score = 40
    elif np_dir == "declining" or rev_dir == "declining":
        health_score = 45
    elif np_volatile:
        health_score = 48
    elif rev_dir == "stable" and np_dir == "stable":
        health_score = 58
    elif rev_dir == "improving" and np_dir == "stable":
        health_score = 68
    elif rev_dir == "improving" and np_dir == "improving":
        health_score = 80
    else:
        health_score = 55

    HEALTH_LABELS = {
        range(0,31):  "branch_drill_health_critical",
        range(31,51): "branch_drill_health_weak",
        range(51,66): "branch_drill_health_stable",
        range(66,81): "branch_drill_health_good",
        range(81,101):"branch_drill_health_strong",
    }
    health_label_key = next(
        (v for r,v in HEALTH_LABELS.items() if health_score in r),
        "branch_drill_health_stable"
    )
    health_label = _t(health_label_key, safe_lang)

    # ── Expense Intelligence (branch-isolated — branch_financials=None) ───────
    # Passing branch_financials=None suppresses company-avg comparison block
    # ensuring no company-level assumptions enter the branch expense analysis
    expense_intel = build_expense_intelligence(
        period_statements = stmts,
        branch_financials = None,
        lang              = safe_lang,
    )

    # ── Expense Decisions Upgrade (branch-level; additive, comparative-aware) ─
    expense_decisions_v2: list = []
    try:
        from app.services.expense_intelligence_engine import build_expense_intelligence_bundle
        from app.services.expense_decisions_upgrade import build_branch_expense_decisions_v2
        from app.api.analysis import _build_consolidated_statements
        from app.services.comparative_intelligence import build_comparative_intelligence

        # Branch bundle from the same statement dicts used in this endpoint
        branch_bundle = build_expense_intelligence_bundle(stmts, lang=safe_lang)

        # Company bundle for contribution + comparative context (prefer consolidated from branches)
        cons = _build_consolidated_statements(branch.company_id, db) or []
        periods_union = set(s.get("period") for s in stmts if s.get("period"))
        if periods_union:
            cons = [s for s in cons if s.get("period") in periods_union]
        company_bundle = build_expense_intelligence_bundle(cons, lang=safe_lang) if cons else {}

        # Build minimal comparative context for this company across branches in this period-set
        # (deterministic and statement-derived; needed for contribution + abnormal category driver).
        from app.models.branch import Branch as _BModel
        branches_active = (
            db.query(_BModel)
            .filter(_BModel.company_id == branch.company_id, _BModel.is_active == True)  # noqa
            .all()
        )
        branch_bundles = []
        for b2 in branches_active:
            # Drill-down uses BranchFinancial-derived synthetic statements.
            # For comparative signals we only need consistent by_period totals/ratios/categories.
            if str(b2.id) == str(branch.id):
                stmts_b = stmts
            else:
                # Best-effort: use BranchFinancial synthetic statements if present
                bfs = (
                    db.query(BranchFinancial)
                    .filter(BranchFinancial.branch_id == b2.id)
                    .order_by(BranchFinancial.period)
                    .all()
                )
                if not bfs:
                    continue
                stmts_b = [_bf_to_stmt_dict(f) for f in bfs]
                if periods_union:
                    stmts_b = [s for s in stmts_b if s.get("period") in periods_union]
            if not stmts_b:
                continue
            bun = build_expense_intelligence_bundle(stmts_b, lang=safe_lang)
            branch_bundles.append({"branch_id": b2.id, "branch_name": b2.name, "expense_bundle": bun})

        comp_ctx = build_comparative_intelligence(
            company_expense_bundle=company_bundle,
            branch_bundles=branch_bundles,
        ) if branch_bundles and company_bundle else {}

        expense_decisions_v2 = build_branch_expense_decisions_v2(
            branch_id=branch_id,
            branch_name=branch.name,
            company_id=branch.company_id,
            company_name=(company_drill.name if company_drill else ""),
            currency=((company_drill.currency if company_drill else "") or ""),
            branch_bundle=branch_bundle,
            comparative_intelligence=comp_ctx,
            lang=safe_lang,
        )
    except Exception as exc:
        logger.warning("branch drill-down expense_decisions_v2 failed: %s", exc)

    deep_intel: dict = {}
    try:
        deep_intel = build_deep_intelligence(stmts, analysis, safe_lang)
    except Exception as exc:
        logger.warning("branch drill-down deep_intelligence failed: %s", exc)

    phase43_rc: list = []
    try:
        _m43, _t43 = derive_phase43_metrics_trends(stmts, analysis)
        phase43_rc = build_root_causes(_m43, _t43, lang=safe_lang)
    except Exception as exc:
        logger.warning("branch drill-down phase43 root causes failed: %s", exc)

    cfo_decisions_br: list = []
    cfo_recommendations_br: list = []
    try:
        company_drill = db.query(Company).filter(Company.id == branch.company_id).first()
        annual_d = build_annual_layer(stmts)
        intel_d = build_intelligence(
            analysis=analysis, annual_layer=annual_d,
            currency=(company_drill.currency if company_drill else "") or "",
        )
        al_d = build_alerts(intel_d, lang=safe_lang).get("alerts", [])
        _pack_dr = build_cfo_decisions(
            intel_d,
            al_d,
            lang=safe_lang,
            n_periods=len(stmts),
            analysis=analysis,
            branch_context=None,
        )
        cfo_decisions_br = _pack_dr.get("decisions", [])
        cfo_recommendations_br = _pack_dr.get("recommendations", [])
    except Exception as exc:
        logger.warning("branch drill-down CFO decisions failed: %s", exc)

    # ── Root Causes (branch-only analysis fed in — no company data) ───────────
    branch_root_causes = []
    try:
        cf_for_rc = {}
        try:
            cf_for_rc = build_cashflow(stmts)
        except Exception:
            pass
        rc_raw = build_root_cause(analysis=analysis, cashflow=cf_for_rc)
        DOMAIN_METRICS = {
            "revenue":        ["revenue_mom_pct","yoy_revenue_pct"],
            "profit":         ["net_margin_pct","gross_margin_pct"],
            "cashflow":       ["operating_cashflow","working_capital_change"],
            "cost_structure": ["expense_ratio","cogs_ratio_pct"],
        }
        for domain in ("revenue","profit","cashflow","cost_structure"):
            rc = rc_raw.get(domain)
            if not rc or not isinstance(rc, dict): continue
            branch_root_causes.append({
                "domain":         domain,
                "title":          rc.get("key",""),
                "direction":      rc.get("trend","stable"),
                "explanation":    rc.get("drivers",[{}])[0].get("key","") if rc.get("drivers") else rc.get("key",""),
                "source_metrics": DOMAIN_METRICS.get(domain, []),
            })
    except Exception as exc:
        logger.warning("branch drill-down root_causes failed: %s", exc)

    # ── Decisions (branch-only via _build_branch_decisions) ───────────────────
    # Build minimal branch profile from computed data — exactly as intelligence does
    mom_rev  = trends.get("revenue_mom_pct") or []
    mom_vals = [x for x in mom_rev if x is not None]
    import itertools
    c_pos = sum(1 for _ in itertools.takewhile(lambda x: x > 0, reversed(mom_vals)))
    c_neg = sum(1 for _ in itertools.takewhile(lambda x: x < 0, reversed(mom_vals)))

    branch_profile = [{
        "branch_id":   branch_id,
        "branch_name": branch.name if safe_lang != "ar" else (branch.name_ar or branch.name),
        "has_data":    True,
        "kpis":        {"expense_ratio": exp_ratio, "net_margin_pct": nm_latest, "revenue": rev},
        "flags":       {},
        "profile": {"actions": _build_branch_actions(
            exp_ratio=exp_ratio, nm=nm_latest, c_pos=c_pos, c_neg=c_neg, lang=safe_lang,
        )},
    }]

    from app.api.analysis import _build_branch_decisions
    branch_decisions = _build_branch_decisions(branch_profile, lang=safe_lang)

    period_count = len(stmts)
    from app.services.deep_intelligence import (
        build_executive_basic_forecast,
        build_executive_forecast_unavailable,
    )
    try:
        forecast_block = build_executive_basic_forecast(stmts, analysis, lang=safe_lang)
    except Exception as _cfe:
        logger.warning("branch drill-down canonical forecast failed: %s", _cfe)
        forecast_block = build_executive_forecast_unavailable(safe_lang, reason="unavailable")

    forecast_scenarios = None
    if period_count >= 3:
        try:
            raw_fc = build_forecast(analysis, lang=safe_lang)
            if raw_fc.get("available"):
                _SCENARIO_KEY_MAP = {"base":"base","optimistic":"aggressive","risk":"conservative"}
                _SCENARIO_ASSUMPTIONS = {
                    "base":         {"revenue_growth_adj_pp":0.0,"expense_adj_pp":0.0},
                    "aggressive":   {"revenue_growth_adj_pp":+2.0,"expense_adj_pp":-1.0},
                    "conservative": {"revenue_growth_adj_pp":-3.0,"expense_adj_pp":+1.5},
                }
                def _pts(sc): return [s.get("point") for s in sc] if sc else []
                raw_sc = raw_fc.get("scenarios",{})
                fc_scenarios = {}
                for ik, ck in _SCENARIO_KEY_MAP.items():
                    sc = raw_sc.get(ik,{})
                    r_pts = _pts(sc.get("revenue",[]))
                    n_pts = _pts(sc.get("net_profit",[]))
                    fc_scenarios[ck] = {
                        "assumptions":    _SCENARIO_ASSUMPTIONS[ck],
                        "forecast_series":{"revenue":r_pts,"net_profit":n_pts},
                        "cashflow_method":"trend_extrapolation",
                        "summary":{
                            "projected_revenue": r_pts[-1] if r_pts else None,
                            "projected_profit":  n_pts[-1] if n_pts else None,
                            "confidence": sc.get("revenue",[{}])[0].get("confidence") if sc.get("revenue") else None,
                        },
                    }
                # ── Loss-aware insight correction (narrative layer only) ──────
                # Numbers are NEVER changed. Only insight text is overridden
                # when the engine narrative contradicts the actual NP sign.
                raw_insight = raw_fc.get("summary", {}).get("insight", "")
                np_latest   = kpis.get("net_profit", 0) or 0
                rev_dir_fc  = branch_trends.get("revenue", {}).get("direction", "stable")
                np_dir_fc   = branch_trends.get("net_profit", {}).get("direction", "stable")
                np_vol_fc   = branch_trends.get("net_profit", {}).get("trend_quality") == "volatile"

                _need_correction = (
                    np_latest < 0
                    or (rev_dir_fc == "improving" and np_dir_fc == "declining")
                    or (rev_dir_fc == "improving" and np_latest < 0)
                )

                if _need_correction:
                    _ar = safe_lang == "ar"; _tr = safe_lang == "tr"
                    if np_vol_fc:
                        if _ar:   _insight = "الإيرادات تتحسن لكن الربحية متذبذبة — الخسائر لم تتحول إلى مكاسب مستدامة بعد"
                        elif _tr: _insight = "Gelir artıyor ancak kârlılık dalgalı — kayıplar henüz istikrarlı kâra dönüşmedi"
                        else:     _insight = "Revenue is improving, but profitability is volatile — losses have not yet converted to sustained gains"
                    elif rev_dir_fc == "improving" and np_latest < 0:
                        if _ar:   _insight = "الإيرادات تتحسن، لكن الخسائر مستمرة — النمو لا يترجم إلى ربحية بعد"
                        elif _tr: _insight = "Gelir artıyor ancak zarar devam ediyor — büyüme henüz kârlılığa yansımıyor"
                        else:     _insight = "Revenue is improving, but losses persist — growth is not yet translating into profitability"
                    else:
                        if _ar:   _insight = "الفرع يحقق نمواً في الإيرادات، لكن ضغط المصروفات ما زال يدفع الربحية إلى المنطقة السلبية"
                        elif _tr: _insight = "Gelir büyüyor ancak maliyet baskısı kârlılığı hâlâ negatif tutuyor"
                        else:     _insight = "Revenue is growing, but cost pressure is still keeping profitability negative"
                else:
                    _insight = raw_insight

                forecast_scenarios = {
                    "forecast_available": True,
                    "method":             raw_fc.get("method"),
                    "forecast_periods":   raw_fc.get("future_periods",[]),
                    "forecast_quality":   raw_fc.get("summary",{}).get("risk_level"),
                    "scenarios":          fc_scenarios,
                    "insight":            _insight,
                }
        except Exception as exc:
            logger.warning("branch drill-down scenario forecast failed: %s", exc)

    return {
        "branch_id":    branch_id,
        "branch_name":  branch.name,
        "name_ar":      branch.name_ar,
        "city":         branch.city,
        "country":      branch.country,
        "latest_period": financials[-1].period,
        "period_count": period_count,
        "periods":      [f.period for f in financials],
        "has_data":     True,
        "status":       "active" if branch.is_active else "inactive",
        "lang":         safe_lang,
        "health_score": health_score,
        "health_label": health_label,
        "health_score_method": "rule_based",

        "kpis":                 kpis,
        "trends":               branch_trends,
        "expense_intelligence": expense_intel,
        "expense_decisions_v2": expense_decisions_v2,
        "deep_intelligence":    deep_intel,
        "phase43_root_causes":  phase43_rc,
        "cfo_decisions":        cfo_decisions_br,
        "cfo_recommendations":  cfo_recommendations_br,
        "root_causes":          branch_root_causes,
        "decisions":            branch_decisions,
        "forecast":             forecast_block,
        "forecast_scenarios":   forecast_scenarios,
    }


def _build_branch_actions(exp_ratio, nm, c_pos, c_neg, lang):
    """Build branch action list with lang-aware text — same logic as decisions-v2."""
    ar = lang == "ar"; tr_ = lang == "tr"
    actions = []
    if exp_ratio and exp_ratio > 60:
        if ar:   d = f"نسبة المصروف {exp_ratio:.1f}٪ — مراجعة التكاليف التشغيلية فوراً"
        elif tr_:d = f"Gider oranı %{exp_ratio:.1f} — işletme maliyetlerini hemen gözden geçirin"
        else:    d = f"Expense ratio at {exp_ratio:.1f}% — review operating costs immediately"
        actions.append({"priority":"high","action":"reduce_expenses","detail":d})
    if nm < 0:
        if ar:   d = f"الفرع في منطقة الخسارة ({nm:.1f}٪) — تحليل جذري مطلوب"
        elif tr_:d = f"Şube zarar bölgesinde (%{nm:.1f}) — kök neden analizi gerekli"
        else:    d = f"Branch in loss territory ({nm:.1f}% net margin) — root cause analysis required"
        actions.append({"priority":"high","action":"investigate_loss","detail":d})
    if c_neg >= 2:
        if ar:   d = f"تراجع الإيراد لـ {c_neg} أشهر متتالية — مراجعة الوضع السوقي"
        elif tr_:d = f"Gelir {c_neg} ay art arda düştü — piyasa koşullarını gözden geçirin"
        else:    d = f"Revenue declining {c_neg} consecutive months — review market conditions"
        actions.append({"priority":"high","action":"investigate_decline","detail":d})
    if 0 <= nm < 20:
        if ar:   d = f"هامش الربح {nm:.1f}٪ دون 20٪ — مراجعة التسعير والتكاليف"
        elif tr_:d = f"Net marj %{nm:.1f}, %20 hedefinin altında — fiyatlandırmayı gözden geçirin"
        else:    d = f"Net margin {nm:.1f}% below 20% target — review pricing and cost structure"
        actions.append({"priority":"medium","action":"improve_margin","detail":d})
    if nm > 20 and c_pos >= 1:
        if ar:   d = f"هامش قوي ({nm:.1f}٪) مع زخم نمو — فرصة للتوسع"
        elif tr_:d = f"Güçlü marj (%{nm:.1f}) ve büyüme ivmesi — kapasite genişletmeyi düşünün"
        else:    d = f"Strong margin ({nm:.1f}%) with growth momentum — consider capacity expansion"
        actions.append({"priority":"medium","action":"scale_revenue","detail":d})
    if not actions and c_pos >= 2:
        if ar:   d = "الحفاظ على الانضباط في التكاليف ومسار النمو الحالي"
        elif tr_:d = "Mevcut maliyet disiplinini ve büyüme yörüngesini koruyun"
        else:    d = "Maintain current cost discipline and growth trajectory"
        actions.append({"priority":"low","action":"maintain_growth","detail":d})
    return actions



# ── Branch comparison engine ──────────────────────────────────────────────────

@router.get("/companies/{company_id}/branch-comparison")
def branch_comparison(
    window:       str = Query(default="ALL", description="3M | 6M | 12M | YTD | ALL"),
    basis_type:   str = Query(default="all"),
    period:       str = Query(default=""),
    year_scope:   str = Query(default="", alias="year"),
    from_period:  str = Query(default=""),
    to_period:    str = Query(default=""),
    db:           Session = Depends(get_db),
    company:      Company = Depends(get_current_company_access),
):
    """
    Compare all active branches for a company.

    Returns:
    {
      "has_data": bool,
      "branch_count": int,
      "ranking": [...],         sorted by total revenue desc
      "top_branches": [...],    top 5 by revenue
      "bottom_branches": [...], bottom 5 by revenue
      "margin_leaders": [...],  top 5 by net margin
      "growth_leaders": [...],  top 5 by MoM revenue growth (latest period)
      "periods_available": [...],  # periods in the active scope / window (not full history)
      "active_periods":    [...],  # same as periods_available (explicit alias for clients)
    }
    """
    from app.services.time_intelligence import filter_periods as _fp
    from app.services.time_scope import scope_from_params

    company_id = company.id

    # Get all active branches
    branches = (
        db.query(Branch)
        .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa
        .all()
    )

    if not branches:
        return {
            "has_data":          False,
            "branch_count":      0,
            "message":           "No branches configured. Create branches and upload branch-level trial balances.",
            "ranking":           [],
            "top_branches":      [],
            "bottom_branches":   [],
            "margin_leaders":    [],
            "growth_leaders":    [],
            "periods_available": [],
            "active_periods":    [],
        }

    branch_rows: list[tuple] = []
    all_periods_union: set[str] = set()

    for b in branches:
        financials = (
            db.query(BranchFinancial)
            .filter(BranchFinancial.branch_id == b.id)
            .order_by(BranchFinancial.period)
            .all()
        )
        branch_rows.append((b, financials))
        for f in financials:
            all_periods_union.add(f.period)

    _win = (window or "ALL").strip().upper()
    if _win not in _VALID_BRANCH_WINDOWS:
        _win = "ALL"

    active_months: set[str] | None = None
    if (basis_type or "").lower() not in ("all", ""):
        _synthetic = [{"period": p} for p in sorted(all_periods_union)]
        scope22 = scope_from_params(
            basis_type,
            period or None,
            year_scope or None,
            from_period or None,
            to_period or None,
            _synthetic,
        )
        if scope22.get("error"):
            raise HTTPException(status_code=400, detail=scope22["error"])
        active_months = set(scope22.get("months") or [])

    # Gather financials for all branches (same order as branch_rows)
    branch_data = []
    active_periods_union: set[str] = set()

    for b, financials in branch_rows:

        if not financials:
            branch_data.append({
                "branch_id":   b.id,
                "branch_name": b.name,
                "city":        b.city,
                "has_data":    False,
            })
            continue

        # Apply scope or rolling window — convert to period-keyed dicts (same shape as before)
        _all_periods_list = [
            {"period": f.period,
             "income_statement": {"revenue": {"total": f.revenue or 0.0},
                                  "net_profit": f.net_profit or 0.0,
                                  "gross_profit": f.gross_profit or 0.0,
                                  "expenses": {"total": f.expenses or 0.0},
                                  "cogs": {"total": f.cogs or 0.0}},
             "_bf": f}
            for f in financials
        ]
        if active_months is not None:
            _windowed_list = [item for item in _all_periods_list if item["period"] in active_months]
        else:
            _windowed_list = _fp(_all_periods_list, _win)
        _windowed_bf = [item["_bf"] for item in _windowed_list]
        if not _windowed_bf:
            _windowed_bf = [financials[-1]]   # fallback: at least latest

        for _bf in _windowed_bf:
            active_periods_union.add(_bf.period)

        latest   = _windowed_bf[-1]
        prev_rev = _windowed_bf[-2].revenue if len(_windowed_bf) >= 2 else None
        mom_rev  = _safe_pct(latest.revenue, prev_rev)

        total_rev = sum(f.revenue or 0.0 for f in _windowed_bf)
        total_np  = sum(f.net_profit or 0.0 for f in _windowed_bf)

        avg_margin = None
        margin_pts = [
            (f.net_profit / f.revenue * 100)
            for f in _windowed_bf
            if f.revenue is not None and f.revenue > 0 and f.net_profit is not None
        ]
        if margin_pts:
            avg_margin = round(sum(margin_pts) / len(margin_pts), 2)

        # latest net_margin — safe: revenue is always abs() from upsert
        latest_net_margin = None
        if latest.revenue is not None and latest.revenue > 0 and latest.net_profit is not None:
            latest_net_margin = round(latest.net_profit / latest.revenue * 100, 2)

        _rv = float(latest.revenue or 0)
        _cg = float(latest.cogs or 0)
        _ex = float(latest.expenses or 0)
        _rvf = _rv if _rv else None
        _opex_l = opex_ratio_pct(_ex, _rvf)
        _cogs_l = cogs_ratio_pct(_cg, _rvf)
        _tc_l = total_cost_ratio_pct(_cg, _ex, _rvf, 0.0)

        branch_data.append({
            "branch_id":       b.id,
            "branch_name":     b.name,
            "name_ar":         b.name_ar,
            "code":            getattr(b, "code", None),
            "city":            b.city,
            "has_data":        True,
            "period_count":    len(_windowed_bf),
            "latest_period":   latest.period,
            "revenue":         latest.revenue,
            "cogs":            latest.cogs,
            "expenses":        latest.expenses,
            "net_profit":      latest.net_profit,
            "net_margin":      latest_net_margin,
            "total_revenue":   round(total_rev, 2),
            "total_net_profit": round(total_np, 2),
            "avg_net_margin":  avg_margin,
            "mom_revenue_pct": mom_rev,
            "mom_trend":       _trend(mom_rev),
            "opex_ratio_pct":       _opex_l,
            "cogs_ratio_pct":       _cogs_l,
            "total_cost_ratio_pct": _tc_l,
        })

    # Sort by total revenue descending
    with_data = [b for b in branch_data if b.get("has_data")]
    no_data   = [b for b in branch_data if not b.get("has_data")]

    ranking          = sorted(with_data, key=lambda x: x.get("total_revenue") or 0, reverse=True)
    net_profit_ranking = sorted(with_data, key=lambda x: x.get("total_net_profit") or 0, reverse=True)
    margin_ranking   = sorted([b for b in with_data if b.get("avg_net_margin") is not None],
                              key=lambda x: x["avg_net_margin"], reverse=True)
    margin_leaders   = sorted([b for b in with_data if b.get("avg_net_margin") is not None],
                               key=lambda x: x["avg_net_margin"], reverse=True)
    growth_leaders   = sorted([b for b in with_data if b.get("mom_revenue_pct") is not None],
                               key=lambda x: x["mom_revenue_pct"], reverse=True)

    # ── Branch Intelligence Layer (additive) ──────────────────────────────────
    best_branch = net_profit_ranking[0] if net_profit_ranking else (ranking[0] if ranking else None)
    worst_branch = net_profit_ranking[-1] if len(net_profit_ranking) > 1 else (ranking[-1] if ranking else None)
    eff_sorted = sorted([b for b in with_data if b.get("total_cost_ratio_pct") is not None],
                        key=lambda x: x.get("total_cost_ratio_pct") or 0)
    most_efficient_branch = eff_sorted[0] if eff_sorted else None
    least_efficient_branch = eff_sorted[-1] if len(eff_sorted) > 1 else None

    branch_intelligence_insights: list[str] = []
    if worst_branch and best_branch and worst_branch.get("branch_id") != best_branch.get("branch_id"):
        branch_intelligence_insights.append(
            f"{worst_branch.get('branch_name')} is underperforming compared to others."
        )
        branch_intelligence_insights.append(
            f"{best_branch.get('branch_name')} drives most of company profit."
        )

    # ── Insights block ────────────────────────────────────────────────────────
    insights: dict = {"warnings": []}

    if no_data:
        insights["warnings"].append({
            "type":     "no_data",
            "branches": [b["branch_name"] for b in no_data],
            "message":  f"{len(no_data)} branch(es) have no uploaded financial data.",
        })

    if ranking:
        strongest = ranking[0]
        weakest   = ranking[-1] if len(ranking) > 1 else None
        best_margin = margin_leaders[0] if margin_leaders else None
        best_growth = growth_leaders[0] if growth_leaders else None

        insights["strongest_branch"] = {
            "branch_id":   strongest.get("branch_id"),
            "branch_name": strongest.get("branch_name"),
            "revenue":     strongest.get("revenue"),
            "reason":      "Highest total revenue",
        }
        if weakest:
            insights["weakest_branch"] = {
                "branch_id":   weakest.get("branch_id"),
                "branch_name": weakest.get("branch_name"),
                "revenue":     weakest.get("revenue"),
                "reason":      "Lowest total revenue",
            }
        if best_margin:
            insights["best_margin_branch"] = {
                "branch_id":      best_margin.get("branch_id"),
                "branch_name":    best_margin.get("branch_name"),
                "avg_net_margin": best_margin.get("avg_net_margin"),
                "reason":         "Highest average net margin",
            }
        if best_growth:
            insights["best_growth_branch"] = {
                "branch_id":      best_growth.get("branch_id"),
                "branch_name":    best_growth.get("branch_name"),
                "mom_revenue_pct": best_growth.get("mom_revenue_pct"),
                "reason":         "Highest MoM revenue growth",
            }

        # Revenue concentration
        total_all_rev = sum(b.get("total_revenue") or 0 for b in with_data)
        if total_all_rev > 0 and len(ranking) > 1:
            top_share = round((strongest.get("total_revenue") or 0) / total_all_rev * 100, 1)
            insights["revenue_concentration"] = {
                "top_branch_share_pct": top_share,
                "concentrated": top_share > 60,
            }

    cross_branch_intelligence: dict = {}
    if with_data:
        margin_cmp_sorted = sorted(
            (
                {
                    "branch_id":            b["branch_id"],
                    "branch_name":          b["branch_name"],
                    "net_margin_pct":       b.get("net_margin"),
                    "avg_net_margin_pct":   b.get("avg_net_margin"),
                    "total_cost_ratio_pct": b.get("total_cost_ratio_pct"),
                    "opex_ratio_pct":       b.get("opex_ratio_pct"),
                    "cogs_ratio_pct":       b.get("cogs_ratio_pct"),
                }
                for b in with_data
            ),
            key=lambda x: (x["net_margin_pct"] if x["net_margin_pct"] is not None else -999),
            reverse=True,
        )
        cost_pressure = sorted(
            [x for x in with_data if x.get("total_cost_ratio_pct") is not None],
            key=lambda x: (x["total_cost_ratio_pct"] or 0),
            reverse=True,
        )
        risk_rows: list = []
        for b in with_data:
            nm = b.get("net_margin")
            if nm is None:
                nm = 0.0
            tc = float(b.get("total_cost_ratio_pct") or 0.0)
            npv = float(b.get("net_profit") or 0)
            mom = b.get("mom_revenue_pct")
            score = 0.0
            if npv < 0:
                score += 50.0
            score += max(0.0, min(40.0, (tc - 70.0) * 1.2))
            score += max(0.0, min(30.0, (15.0 - float(nm)) * 1.5))
            if mom is not None and mom < -5:
                score += 12.0
            risk_rows.append({
                "branch_id":   b["branch_id"],
                "branch_name": b["branch_name"],
                "risk_score":  round(score, 2),
            })
        risk_rows.sort(key=lambda x: -x["risk_score"])
        risk_ranking = [{**r, "risk_rank": i + 1} for i, r in enumerate(risk_rows)]

        _vals_nm = [b.get("net_margin") for b in with_data if b.get("net_margin") is not None]
        port_avg = round(sum(_vals_nm) / len(_vals_nm), 2) if _vals_nm else None

        prof_strong = max(
            with_data,
            key=lambda x: (x.get("net_margin") if x.get("net_margin") is not None else -1e9),
        )
        prof_weak = min(
            with_data,
            key=lambda x: (x.get("net_margin") if x.get("net_margin") is not None else 1e9),
        )

        cross_branch_intelligence = {
            "margin_comparison": margin_cmp_sorted,
            "cost_pressure_by_branch": [
                {
                    "branch_id":            br["branch_id"],
                    "branch_name":          br["branch_name"],
                    "total_cost_ratio_pct": br.get("total_cost_ratio_pct"),
                    "opex_ratio_pct":       br.get("opex_ratio_pct"),
                    "cost_pressure_rank":   i + 1,
                }
                for i, br in enumerate(cost_pressure)
            ],
            "risk_ranking":                   risk_ranking,
            "strongest_branch_profitability": {
                "branch_id":      prof_strong.get("branch_id"),
                "branch_name":    prof_strong.get("branch_name"),
                "net_margin_pct": prof_strong.get("net_margin"),
                "reason":         "Highest latest net margin among branches with data",
            },
            "weakest_branch_profitability": {
                "branch_id":      prof_weak.get("branch_id"),
                "branch_name":    prof_weak.get("branch_name"),
                "net_margin_pct": prof_weak.get("net_margin"),
                "reason":         "Lowest latest net margin among branches with data",
            },
            "portfolio_avg_net_margin_pct":   port_avg,
        }

    return {
        "has_data":                    len(with_data) > 0,
        "branch_count":                len(branches),
        "branches_with_data":          len(with_data),
        "ranking":                     ranking,
        # Additive rankings
        "revenue_ranking":             ranking,
        "net_profit_ranking":          net_profit_ranking,
        "margin_ranking":              margin_ranking,
        # Additive branch intelligence picks
        "best_branch":                 best_branch,
        "worst_branch":                worst_branch,
        "most_efficient_branch":       most_efficient_branch,
        "least_efficient_branch":      least_efficient_branch,
        "branch_intelligence_insights": branch_intelligence_insights,
        "top_branches":                ranking[:5],
        "bottom_branches":             list(reversed(ranking[-5:])),
        "margin_leaders":              margin_leaders[:5],
        "growth_leaders":              growth_leaders[:5],
        "no_data_branches":            no_data,
        "periods_available":           sorted(active_periods_union),
        "active_periods":              sorted(active_periods_union),
        "insights":                    insights,
        "cross_branch_intelligence":  cross_branch_intelligence,
    }


# ── Branch Intelligence endpoint ──────────────────────────────────────────────

@router.get("/companies/{company_id}/branch-intelligence")
def get_branch_intelligence(
    lang:         str = Query(default="en"),
    db:           Session = Depends(get_db),
    company:      Company = Depends(get_current_company_access),
):
    """
    CFO-grade branch intelligence.
    Reuses _bf_to_stmt_dict → run_analysis → compute_trends per branch.
    Adds rankings, classifications, per-branch profiles, insights, CFO actions.
    """
    from app.services.analysis_engine import run_analysis, compute_trends

    company_id = company.id

    branches = (
        db.query(Branch)
        .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa
        .all()
    )
    if not branches:
        return {"has_data": False, "branch_count": 0, "branches": [],
                "rankings": {}, "classifications": {}, "company_insights": [], "cfo_actions": []}

    # ── Translation helper for generated text ────────────────────────────────────
    _safe_lang = lang if lang in ("en", "ar", "tr") else "en"
    from app.i18n import translate as _t
    def _tr(key): return _t(key, _safe_lang)

    # Localised sentence builders
    def _s_leads(rev, nm):
        if _safe_lang == "ar":
            return f"يتصدر الشركة في الإيراد ({rev}) مع هامش ربح صحي ({nm:.1f}٪)"
        if _safe_lang == "tr":
            return f"Şirket gelirinde lider ({rev}), sağlıklı marj (%{nm:.1f})"
        return f"Leads company in revenue ({rev}) with healthy margin ({nm:.1f}%)"

    def _s_best_margin(nm):
        if _safe_lang == "ar": return f"أعلى صافي هامش ربح في المحفظة ({nm:.1f}٪)"
        if _safe_lang == "tr": return f"Portföydeki en yüksek net marj (%{nm:.1f})"
        return f"Highest net margin in portfolio ({nm:.1f}%)"

    def _s_consec_growth(n, mom):
        if _safe_lang == "ar": return f"نمو متواصل لـ {n} فترات متتالية (+{mom:.1f}٪ آخر شهر)"
        if _safe_lang == "tr": return f"{n} ardışık dönem büyüme (+%{mom:.1f} son MoM)"
        return f"Consistent growth for {n} consecutive periods (+{mom:.1f}% latest MoM)"

    def _s_fastest_growth(mom):
        if _safe_lang == "ar": return f"أسرع نمو إيراد ({_fmt(mom)}٪ ش/ش)"
        if _safe_lang == "tr": return f"En hızlı gelir artışı (%{_fmt(mom)} MoM)"
        return f"Fastest revenue growth ({_fmt(mom)}% MoM)"

    def _s_strong_profit(nm):
        if _safe_lang == "ar": return f"ربحية قوية — صافي هامش {nm:.1f}٪"
        if _safe_lang == "tr": return f"Güçlü karlılık — net marj %{nm:.1f}"
        return f"Strong profitability — net margin {nm:.1f}%"

    def _s_weakest_margin(nm):
        if _safe_lang == "ar": return f"أدنى هامش في المحفظة ({nm:.1f}٪)"
        if _safe_lang == "tr": return f"Portföydeki en düşük marj (%{nm:.1f})"
        return f"Weakest margin in portfolio ({nm:.1f}%)"

    def _s_highest_exp(exp_r, avg):
        if _safe_lang == "ar": return f"أعلى نسبة مصروف ({exp_r:.1f}٪) — فوق متوسط الشركة ({avg:.1f}٪)"
        if _safe_lang == "tr": return f"En yüksek gider oranı (%{exp_r:.1f}) — şirket ortalamasının üzerinde (%{avg:.1f})"
        return f"Highest expense ratio ({exp_r:.1f}%) — above company average ({avg:.1f}%)"

    def _s_lowest_rev(rev):
        if _safe_lang == "ar": return f"أقل مساهمة في الإيراد ({rev})"
        if _safe_lang == "tr": return f"En düşük gelir katkısı ({rev})"
        return f"Lowest revenue contribution ({rev})"

    def _s_loss(nm):
        if _safe_lang == "ar": return f"الفرع يعمل بخسارة — هامش الربح {nm:.1f}٪"
        if _safe_lang == "tr": return f"Şube zarar ediyor — net marj %{nm:.1f}"
        return f"Branch operating at a loss — net margin {nm:.1f}%"

    def _s_exp_critical(exp_r):
        if _safe_lang == "ar": return f"نسبة المصروف حرجة ({exp_r:.1f}٪) — تجاوزت حد 60٪"
        if _safe_lang == "tr": return f"Gider oranı kritik (%{exp_r:.1f}) — %60 eşiğini aştı"
        return f"Expense ratio critical ({exp_r:.1f}%) — exceeds 60% threshold"

    def _s_decline(n):
        if _safe_lang == "ar": return f"تراجع الإيراد لـ {n} فترات متتالية"
        if _safe_lang == "tr": return f"Gelir {n} ardışık dönem düştü"
        return f"Revenue declining for {n} consecutive periods"

    # CFO action details
    def _a_reduce_exp(exp_r):
        if _safe_lang == "ar": return f"نسبة المصروف {exp_r:.1f}٪ — مراجعة التكاليف التشغيلية فوراً"
        if _safe_lang == "tr": return f"Gider oranı %{exp_r:.1f} — işletme maliyetlerini hemen gözden geçirin"
        return f"Expense ratio at {exp_r:.1f}% — review operating costs immediately"

    def _a_loss(nm):
        if _safe_lang == "ar": return f"الفرع في منطقة الخسارة ({nm:.1f}٪) — تحليل جذري مطلوب"
        if _safe_lang == "tr": return f"Şube zarar bölgesinde (%{nm:.1f}) — kök neden analizi gerekli"
        return f"Branch in loss territory ({nm:.1f}% net margin) — root cause analysis required"

    def _a_decline(n):
        if _safe_lang == "ar": return f"تراجع الإيراد لـ {n} أشهر متتالية — مراجعة الوضع السوقي"
        if _safe_lang == "tr": return f"Gelir {n} ay art arda düştü — piyasa koşullarını gözden geçirin"
        return f"Revenue declining {n} consecutive months — review market conditions"

    def _a_margin(nm):
        if _safe_lang == "ar": return f"هامش الربح {nm:.1f}٪ دون 20٪ — مراجعة التسعير والتكاليف"
        if _safe_lang == "tr": return f"Net marj %{nm:.1f}, %20 hedefinin altında — fiyatlandırmayı gözden geçirin"
        return f"Net margin {nm:.1f}% below 20% target — review pricing and cost structure"

    def _a_scale(nm):
        if _safe_lang == "ar": return f"هامش قوي ({nm:.1f}٪) مع زخم نمو — فرصة للتوسع"
        if _safe_lang == "tr": return f"Güçlü marj (%{nm:.1f}) ve büyüme ivmesi — kapasite genişletmeyi düşünün"
        return f"Strong margin ({nm:.1f}%) with growth momentum — consider capacity expansion"

    def _a_maintain():
        if _safe_lang == "ar": return "الحفاظ على الانضباط في التكاليف ومسار النمو الحالي"
        if _safe_lang == "tr": return "Mevcut maliyet disiplinini ve büyüme yörüngesini koruyun"
        return "Maintain current cost discipline and growth trajectory"

    # Insight messages
    def _i_lead(rev, nm):
        if _safe_lang == "ar": return f"يتصدر في الإيراد ({rev}) مع هامش قوي ({nm:.1f}٪)"
        if _safe_lang == "tr": return f"Gelirde öncü ({rev}) ve güçlü marjını koruyor (%{nm:.1f})"
        return f"Leads in revenue ({rev}) and maintains strong margin ({nm:.1f}%)"

    def _i_improving(n, mom):
        if _safe_lang == "ar": return f"نمو متواصل لـ {n} فترات متتالية — آخر نمو ش/ش +{mom:.1f}٪"
        if _safe_lang == "tr": return f"{n} ardışık dönem büyüyor — son MoM +%{mom:.1f}"
        return f"Growing for {n} consecutive periods — latest MoM +{mom:.1f}%"

    def _i_decline(n):
        if _safe_lang == "ar": return f"الإيراد يتراجع لـ {n} فترات متتالية — يحتاج اهتماماً"
        if _safe_lang == "tr": return f"Gelir {n} ardışık dönem düşüyor — dikkat gerekiyor"
        return f"Revenue declining for {n} consecutive periods — needs attention"

    def _i_inefficient(exp_r):
        if _safe_lang == "ar": return f"أعلى نسبة مصروف ({exp_r:.1f}٪) — ضغط على الهامش"
        if _safe_lang == "tr": return f"En yüksek gider oranı (%{exp_r:.1f}) — marj baskısı riski"
        return f"Highest expense ratio ({exp_r:.1f}%) — margin pressure risk"

    def _i_loss(nm):
        if _safe_lang == "ar": return f"يعمل بخسارة — هامش الربح {nm:.1f}٪"
        if _safe_lang == "tr": return f"Zarar ediyor — net marj %{nm:.1f}"
        return f"Operating at a loss — net margin {nm:.1f}%"

    def _i_opportunity(nm):
        if _safe_lang == "ar": return f"أفضل هامش ({nm:.1f}٪) — فرصة لزيادة تخصيص الإيراد"
        if _safe_lang == "tr": return f"En iyi marj (%{nm:.1f}) — gelir tahsisini artırma fırsatı"
        return f"Best margin ({nm:.1f}%) — potential to increase revenue allocation"

    # ── Per-branch computation ─────────────────────────────────────────────────
    def _r2(v): return round(v, 2) if v is not None else None
    def _fmt(v):
        """Human-readable: 392000 → '392K', 1200000 → '1.2M'."""
        if v is None: return "—"
        a = abs(v)
        if a >= 1_000_000: return f"{v/1_000_000:.1f}M"
        if a >= 1_000:     return f"{v/1_000:.0f}K"
        return f"{v:.0f}"

    branch_profiles = []
    all_periods: set = set()

    for b in branches:
        financials = (
            db.query(BranchFinancial)
            .filter(BranchFinancial.branch_id == b.id)
            .order_by(BranchFinancial.period)
            .all()
        )
        if not financials:
            branch_profiles.append({
                "branch_id":   b.id,
                "branch_name": b.name,
                "name_ar":     b.name_ar,
                "branch_code": getattr(b, "code", None),
                "city":        b.city,
                "has_data":    False,
            })
            continue

        for f in financials:
            all_periods.add(f.period)

        # Reuse existing synthetic stmt builder + analysis engines
        stmts    = [_bf_to_stmt_dict(f) for f in financials]
        analysis = run_analysis(stmts)
        trends   = compute_trends(stmts)

        latest   = financials[-1]
        lat_is   = stmts[-1].get("income_statement", {})
        rev      = lat_is.get("revenue",  {}).get("total",  0) or 0
        exp      = lat_is.get("expenses", {}).get("total",  0) or 0
        gp       = lat_is.get("gross_profit",  0) or 0
        np_      = lat_is.get("net_profit",    0) or 0
        gm_pct   = lat_is.get("gross_margin_pct",     0) or 0
        nm_pct   = lat_is.get("net_margin_pct",       0) or 0
        om_pct   = lat_is.get("operating_margin_pct", 0) or 0
        exp_ratio = _r2(exp / rev * 100) if rev > 0 else None

        # Aggregates across all periods
        rev_series = [f.revenue    or 0 for f in financials]
        np_series  = [f.net_profit or 0 for f in financials]
        n          = len(financials)
        avg_rev    = _r2(sum(rev_series) / n)
        avg_np     = _r2(sum(np_series)  / n)
        nm_pts     = [
            f.net_profit / f.revenue * 100
            for f in financials
            if f.revenue and f.revenue > 0 and f.net_profit is not None
        ]
        avg_nm_pct = _r2(sum(nm_pts) / len(nm_pts)) if nm_pts else None

        # MoM growth from trends
        mom_rev = trends.get("revenue_mom_pct") or trends.get("revenue_mom") or []
        last_mom = next((x for x in reversed(mom_rev) if x is not None), None)

        # Consecutive positive/negative MoM (for insight rules)
        mom_vals = [x for x in mom_rev if x is not None]
        consec_positive = sum(1 for _ in __import__('itertools').takewhile(lambda x: x > 0, reversed(mom_vals)))
        consec_negative = sum(1 for _ in __import__('itertools').takewhile(lambda x: x < 0, reversed(mom_vals)))

        branch_profiles.append({
            "branch_id":    b.id,
            "branch_name":  b.name,
            "name_ar":      b.name_ar,
            "branch_code":  getattr(b, "code", None),
            "city":         b.city,
            "has_data":     True,
            "period_count": n,
            "latest_period": latest.period,
            "periods":      [f.period for f in financials],

            "kpis": {
                "revenue":              _r2(rev),
                "net_profit":           _r2(np_),
                "gross_profit":         _r2(gp),
                "gross_margin_pct":     _r2(gm_pct),
                "net_margin_pct":       _r2(nm_pct),
                "operating_margin_pct": _r2(om_pct),
                "expense_ratio":        exp_ratio,
            },

            "aggregates": {
                "avg_revenue":       avg_rev,
                "avg_net_profit":    avg_np,
                "avg_net_margin_pct": avg_nm_pct,
                "total_revenue":     _r2(sum(rev_series)),
                "total_net_profit":  _r2(sum(np_series)),
            },

            "trends": {
                "periods":             trends.get("periods", []),
                "revenue_series":      trends.get("revenue_series", []),
                "net_profit_series":   trends.get("net_profit_series", []),
                "revenue_mom_pct":     mom_rev,
                "last_mom_revenue":    _r2(last_mom),
                "consec_positive_mom": consec_positive,
                "consec_negative_mom": consec_negative,
            },

            # Populated below after cross-branch comparison
            "flags": {},
            "profile": {},
        })

    # ── Separate branches with data ───────────────────────────────────────────
    with_data = [b for b in branch_profiles if b.get("has_data")]
    no_data   = [b for b in branch_profiles if not b.get("has_data")]

    if not with_data:
        return {"has_data": False, "branch_count": len(branches),
                "branches": branch_profiles, "rankings": {}, "classifications": {},
                "company_insights": [], "cfo_actions": []}

    # ── Rankings (standardized 4 dimensions) ─────────────────────────────────
    def rank(key_fn, reverse=True):
        return sorted(
            [{"branch_id": b["branch_id"], "branch_name": b["branch_name"],
              "value": key_fn(b)} for b in with_data if key_fn(b) is not None],
            key=lambda x: x["value"], reverse=reverse
        )

    rankings = {
        "revenue":       rank(lambda b: b["kpis"]["revenue"]),
        "profitability": rank(lambda b: b["kpis"]["net_margin_pct"]),
        "efficiency":    rank(lambda b: b["kpis"]["expense_ratio"], reverse=False),  # lower = better
        "growth":        rank(lambda b: b["trends"]["last_mom_revenue"]),
    }

    # ── Classification helpers ────────────────────────────────────────────────
    rev_vals  = [b["kpis"]["revenue"]         for b in with_data if b["kpis"]["revenue"] is not None]
    nm_vals   = [b["kpis"]["net_margin_pct"]  for b in with_data if b["kpis"]["net_margin_pct"] is not None]
    exp_vals  = [b["kpis"]["expense_ratio"]   for b in with_data if b["kpis"]["expense_ratio"] is not None]
    mom_vals2 = [b["trends"]["last_mom_revenue"] for b in with_data if b["trends"]["last_mom_revenue"] is not None]

    avg_exp_ratio = sum(exp_vals) / len(exp_vals) if exp_vals else 50.0

    max_rev   = max(rev_vals)  if rev_vals  else None
    min_rev   = min(rev_vals)  if rev_vals  else None
    max_nm    = max(nm_vals)   if nm_vals   else None
    min_nm    = min(nm_vals)   if nm_vals   else None
    max_mom   = max(mom_vals2) if mom_vals2 else None
    min_mom   = min(mom_vals2) if mom_vals2 else None
    max_exp   = max(exp_vals)  if exp_vals  else None

    # ── Assign boolean flags to each branch ───────────────────────────────────
    classifications = {}
    for b in with_data:
        rev      = b["kpis"]["revenue"]         or 0
        nm       = b["kpis"]["net_margin_pct"]  or 0
        exp_r    = b["kpis"]["expense_ratio"]
        last_mom = b["trends"]["last_mom_revenue"]
        c_pos    = b["trends"]["consec_positive_mom"]
        c_neg    = b["trends"]["consec_negative_mom"]

        # strongest: high revenue AND positive margin AND expense_ratio < 50%
        is_strongest = (
            rev == max_rev and
            nm > 0 and
            (exp_r is None or exp_r < 50)
        )
        is_weakest         = rev == min_rev and nm <= (min_nm if min_nm else 0)
        is_best_margin     = nm == max_nm and max_nm is not None
        is_worst_margin    = nm == min_nm and min_nm is not None
        is_fastest_growing = last_mom == max_mom and max_mom is not None and max_mom > 0
        is_slowest         = last_mom == min_mom and min_mom is not None
        is_high_cost       = exp_r == max_exp and max_exp is not None and max_exp > avg_exp_ratio
        is_improving       = c_pos >= 2
        is_declining       = c_neg >= 2

        flags = {
            "is_strongest":      is_strongest,
            "is_weakest":        is_weakest,
            "is_best_margin":    is_best_margin,
            "is_worst_margin":   is_worst_margin,
            "is_fastest_growing": is_fastest_growing,
            "is_slowest":        is_slowest,
            "is_high_cost":      is_high_cost,
            "is_improving":      is_improving,
            "is_declining":      is_declining,
        }
        b["flags"] = flags

        # Classifications dict (first match per role)
        for flag, role in [
            ("is_strongest",       "strongest_branch"),
            ("is_weakest",         "weakest_branch"),
            ("is_best_margin",     "best_margin_branch"),
            ("is_worst_margin",    "worst_margin_branch"),
            ("is_fastest_growing", "fastest_growing"),
            ("is_slowest",         "slowest_branch"),
            ("is_high_cost",       "highest_cost_branch"),
        ]:
            if flags[flag] and role not in classifications:
                classifications[role] = {
                    "branch_id":   b["branch_id"],
                    "branch_name": b["branch_name"],
                    "value":       b["kpis"].get(
                        {"is_strongest":"revenue","is_weakest":"revenue",
                         "is_best_margin":"net_margin_pct","is_worst_margin":"net_margin_pct",
                         "is_fastest_growing":"none","is_slowest":"none",
                         "is_high_cost":"expense_ratio"}.get(flag,"revenue")
                    ),
                }

    # ── Per-branch profile: strengths / weaknesses / warnings / actions ───────
    for b in with_data:
        fl   = b["flags"]
        kpis = b["kpis"]
        nm   = kpis.get("net_margin_pct") or 0
        exp_r = kpis.get("expense_ratio")
        rev_v = kpis.get("revenue") or 0
        c_pos = b["trends"]["consec_positive_mom"]
        c_neg = b["trends"]["consec_negative_mom"]
        last_mom = b["trends"]["last_mom_revenue"]

        strengths  = []
        weaknesses = []
        warnings   = []
        actions    = []

        # Strengths
        if fl["is_strongest"]:
            strengths.append(_s_leads(_fmt(rev_v), nm))
        if fl["is_best_margin"]:
            strengths.append(_s_best_margin(nm))
        if fl["is_improving"] and last_mom is not None:
            strengths.append(_s_consec_growth(c_pos, last_mom))
        if fl["is_fastest_growing"] and not fl["is_improving"]:
            strengths.append(_s_fastest_growth(last_mom))
        if nm > 25:
            strengths.append(_s_strong_profit(nm))

        # Weaknesses
        if fl["is_worst_margin"] and nm < 15:
            weaknesses.append(_s_weakest_margin(nm))
        if fl["is_high_cost"] and exp_r is not None:
            weaknesses.append(_s_highest_exp(exp_r, avg_exp_ratio))
        if fl["is_weakest"]:
            weaknesses.append(_s_lowest_rev(_fmt(rev_v)))

        # Warnings
        if nm < 0:
            warnings.append(_s_loss(nm))
        if exp_r is not None and exp_r > 60:
            warnings.append(_s_exp_critical(exp_r))
        if fl["is_declining"]:
            warnings.append(_s_decline(c_neg))

        # CFO actions
        if exp_r is not None and exp_r > 60:
            actions.append({"priority": "high",   "action": "reduce_expenses",
                "detail": _a_reduce_exp(exp_r)})
        if nm < 0:
            actions.append({"priority": "high",   "action": "investigate_loss",
                "detail": _a_loss(nm)})
        if fl["is_declining"]:
            actions.append({"priority": "high",   "action": "investigate_decline",
                "detail": _a_decline(c_neg)})
        if nm < 20 and nm >= 0:
            actions.append({"priority": "medium", "action": "improve_margin",
                "detail": _a_margin(nm)})
        if fl["is_fastest_growing"] and nm > 20:
            actions.append({"priority": "medium", "action": "scale_revenue",
                "detail": _a_scale(nm)})
        if fl["is_improving"] and not actions:
            actions.append({"priority": "low",    "action": "maintain_growth",
                "detail": _a_maintain()})

        b["profile"] = {
            "strengths":  strengths,
            "weaknesses": weaknesses,
            "warnings":   warnings,
            "actions":    actions,
        }

    # ── Company-level insights (with numbers) ─────────────────────────────────
    company_insights = []
    for b in with_data:
        fl   = b["flags"]
        name = b["branch_name"]
        nm   = b["kpis"]["net_margin_pct"] or 0
        rev_v = b["kpis"]["revenue"] or 0
        exp_r = b["kpis"]["expense_ratio"]
        last_mom = b["trends"]["last_mom_revenue"]

        if fl["is_strongest"]:
            company_insights.append({
                "type": "lead", "branch": name,
                "message": _i_lead(_fmt(rev_v), nm)
            })
        if fl["is_improving"]:
            c_pos = b["trends"]["consec_positive_mom"]
            company_insights.append({
                "type": "improving", "branch": name,
                "message": _i_improving(c_pos, last_mom)
            })
        if fl["is_declining"]:
            c_neg = b["trends"]["consec_negative_mom"]
            company_insights.append({
                "type": "risk", "branch": name,
                "message": _i_decline(c_neg)
            })
        if fl["is_high_cost"] and exp_r is not None:
            company_insights.append({
                "type": "inefficient", "branch": name,
                "message": _i_inefficient(exp_r)
            })
        if nm < 0:
            company_insights.append({
                "type": "risk", "branch": name,
                "message": _i_loss(nm)
            })
        if fl["is_best_margin"] and not fl["is_strongest"]:
            company_insights.append({
                "type": "opportunity", "branch": name,
                "message": _i_opportunity(nm)
            })

    # ── Global CFO actions (de-duplicated, sorted by priority) ───────────────
    priority_order = {"high": 0, "medium": 1, "low": 2}
    all_actions = []
    for b in with_data:
        for act in b["profile"]["actions"]:
            all_actions.append({**act, "branch": b["branch_name"], "branch_id": b["branch_id"]})
    all_actions.sort(key=lambda x: priority_order.get(x["priority"], 9))

    return {
        "company_id":         company_id,
        "branch_count":       len(branches),
        "branches_with_data": len(with_data),
        "has_data":           len(with_data) > 0,
        "periods_available":  sorted(all_periods),
        "rankings":           rankings,
        "classifications":    classifications,
        "branches":           with_data + no_data,
        "company_insights":   company_insights,
        "cfo_actions":        all_actions,
    }



# ── Company Executive Summary ──────────────────────────────────────────────────

@router.get("/companies/{company_id}/executive")
def get_company_executive(
    lang:       str  = Query(default="en"),
    consolidate:bool = Query(default=False),
    db:         Session = Depends(get_db),
    company:    Company = Depends(get_current_company_access),
):
    """
    Executive layer — assembles from existing pipeline outputs.
    No new calculations. Pure aggregation and interpretation.

    Sources:
    - _build_period_statements + run_analysis → quick_metrics, health
    - _build_portfolio_insights + contributions → signals, priorities, risks, opportunities
    - alerts_engine → risk signals
    - expense_engine → cost signals
    """
    from app.services.analysis_engine   import run_analysis, _trend_direction
    from app.services.cashflow_engine   import build_cashflow
    from app.services.alerts_engine     import build_alerts
    from app.services.fin_intelligence  import build_intelligence
    from app.services.period_aggregation import build_annual_layer
    from app.services.expense_engine    import build_expense_intelligence
    from app.i18n                       import translate as _t
    import itertools

    safe_lang = lang if lang in ("en","ar","tr") else "en"
    ar = safe_lang == "ar"; tr_ = safe_lang == "tr"

    company_id = company.id

    # ── Statements ────────────────────────────────────────────────────────────
    if consolidate:
        all_stmts = _build_consolidated_statements(company_id, db)
        if not all_stmts:
            raise HTTPException(422, "No financial data uploaded yet (branch consolidation).")
        data_source = "branch_consolidation"
    else:
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(TrialBalanceUpload.company_id == company_id,
                    TrialBalanceUpload.status == "ok",
                    TrialBalanceUpload.branch_id.is_(None))
            .order_by(TrialBalanceUpload.uploaded_at.asc()).all()
        )
        if not uploads:
            raise HTTPException(422, "No financial data uploaded yet. Upload a Trial Balance first.")
        all_stmts = _build_period_statements(company_id, uploads)
        if not all_stmts:
            raise HTTPException(422, "Could not build statements.")
        data_source = "direct_uploads"

    # ── Core analysis (reuse existing engines) ────────────────────────────────
    analysis = run_analysis(all_stmts)
    trends   = analysis.get("trends", {})

    # ── Phase 43 intelligence (reuse — no recalculation) ──────────────────────
    _p43_narratives: list = []
    _p43_anomalies:  list = []
    _p43_rc2:        list = []
    try:
        _prof43  = (analysis.get("latest") or {}).get("profitability", {})
        _tr43    = analysis.get("trends") or {}
        def _lv(s): return next((x for x in reversed(s or []) if x is not None), None)
        _p43_metrics = {
            "net_margin_pct": _prof43.get("net_margin_pct"),
            "expense_ratio":  None,
            "cogs_ratio":     None,
        }
        _p43_trends = {
            "revenue_mom":       _lv(_tr43.get("revenue_mom_pct")),
            "net_profit_mom":    _lv(_tr43.get("net_profit_mom_pct")),
            "expense_ratio_mom": _lv(_tr43.get("expenses_mom_pct")),
            "cogs_ratio_mom":    None,
            "net_margin_mom":    None,
        }
        _p43_rc2        = build_root_causes(_p43_metrics, _p43_trends, lang=safe_lang)
        _p43_anomalies  = detect_anomalies(_p43_metrics, _p43_trends, lang=safe_lang)
        _p43_narratives = build_narratives(_p43_rc2, _p43_anomalies, lang=safe_lang)
    except Exception as _p43_exc:
        logger.warning("executive phase43 failed: %s", _p43_exc)
    latest_r = analysis.get("latest") or {}
    prof     = latest_r.get("profitability", {})
    liq      = latest_r.get("liquidity", {})

    last_is  = all_stmts[-1].get("income_statement", {})
    rev      = last_is.get("revenue", {}).get("total", 0) or 0
    np_      = last_is.get("net_profit", 0) or 0
    exp      = last_is.get("expenses", {}).get("total", 0) or 0
    nm       = prof.get("net_margin_pct") or 0
    gm       = prof.get("gross_margin_pct") or 0
    cr       = liq.get("current_ratio")
    exp_r    = round(exp / rev * 100, 2) if rev > 0 else None

    mom_rev  = trends.get("revenue_mom_pct", [])
    mom_np   = trends.get("net_profit_mom_pct", [])
    rev_dir  = _trend_direction(mom_rev)
    np_dir   = _trend_direction(mom_np)

    ocf = None
    try:
        cf = build_cashflow(all_stmts)
        if not cf.get("error"):
            ocf = cf.get("operating_cashflow")
    except Exception:
        pass

    # ── Health score (rule-based, same pattern as drill-down) ─────────────────
    mom_np_vals = [x for x in mom_np if x is not None]
    np_volatile = (len(mom_np_vals) >= 2 and
                   ((mom_np_vals[-2] > 0.5 and mom_np_vals[-1] < -0.5) or
                    (mom_np_vals[-2] < -0.5 and mom_np_vals[-1] > 0.5)))

    if np_ < 0:               health_score = 20
    elif exp_r and exp_r > 80:health_score = 35
    elif np_dir == "declining" and nm < 10: health_score = 40
    elif np_volatile:          health_score = 48
    elif rev_dir == "stable" and np_dir == "stable": health_score = 58
    elif rev_dir == "improving" and np_dir == "improving": health_score = 82
    elif rev_dir == "improving": health_score = 70
    else:                       health_score = 55

    HLABELS = [(0,31,"critical"),(31,51,"weak"),(51,66,"stable"),(66,81,"good"),(81,101,"strong")]
    health_label = next((l for lo,hi,l in HLABELS if lo<=health_score<hi), "stable")

    # ── Quick metrics (from analysis — no new calc) ───────────────────────────
    quick_metrics = {
        "revenue":             round(rev, 2),
        "net_profit":          round(np_, 2),
        "net_margin_pct":      nm,
        "gross_margin_pct":    gm,
        "expense_ratio":       exp_r,
        "current_ratio":       cr,
        "operating_cashflow":  ocf,
        "revenue_mom_pct":     (mom_rev[-1] if [x for x in mom_rev if x is not None] else None),
        "net_profit_mom_pct":  (mom_np[-1]  if [x for x in mom_np  if x is not None] else None),
        "latest_period":       (analysis.get("periods") or [""])[-1],
        "period_count":        analysis.get("period_count", 0),
    }

    # ── Alerts (existing engine — severity normalized in aggregation layer) ────
    raw_alerts: list = []
    try:
        annual = build_annual_layer(all_stmts)
        intel  = build_intelligence(analysis=analysis, annual_layer=annual, currency=company.currency or "")
        SEV_MAP = {"critical":"high","warning":"medium","info":"low","high":"high","medium":"medium","low":"low"}
        raw_alerts = [
            {"type": a.get("id", a.get("type","")),
             "severity": SEV_MAP.get(str(a.get("severity","medium")).lower(),"medium"),
             "message": a.get("title", a.get("message",""))}
            for a in build_alerts(intel, lang=safe_lang).get("alerts", [])
        ]
    except Exception as exc:
        logger.warning("executive alerts failed: %s", exc)

    # ── Expense signals (from expense_engine — no new calc) ───────────────────
    exp_insights: list = []
    try:
        ei = build_expense_intelligence(all_stmts, branch_financials=None, lang=safe_lang)
        exp_insights = [
            {"type": i["type"], "severity": i["severity"],
             "summary": i["what_happened"], "action": i["what_to_do"]}
            for i in ei.get("insights", [])
        ]
    except Exception as exc:
        logger.warning("executive expense_insights failed: %s", exc)

    # ── Portfolio branch signals (if branches exist) ───────────────────────────
    branch_signals: list = []
    try:
        branches = (db.query(Branch)
            .filter(Branch.company_id == company_id, Branch.is_active == True).all())  # noqa
        profiles = []
        for b in branches:
            fins = (db.query(BranchFinancial)
                .filter(BranchFinancial.branch_id == b.id)
                .order_by(BranchFinancial.period).all())
            p = _build_branch_profile_for_portfolio(b, fins)
            if p: profiles.append(p)

        if profiles:
            total_rev_b = sum(p["kpis"]["revenue"] or 0 for p in profiles)
            total_np_b  = sum(p["kpis"]["net_profit"] or 0 for p in profiles)
            for p in profiles:
                rs = round((p["kpis"]["revenue"] or 0)/total_rev_b*100,2) if total_rev_b else 0
                ps = round((p["kpis"]["net_profit"] or 0)/total_np_b*100,2) if total_np_b else 0
                p["revenue_share_pct"] = rs; p["profit_share_pct"] = ps
                p["role"] = _classify_role(p["kpis"]["net_margin_pct"] or 0, ps, p["trends"]["consec_positive_mom"])
            port_m_b = round(total_np_b/total_rev_b*100,2) if total_rev_b else 0
            for ins in _build_portfolio_insights(profiles, port_m_b, safe_lang)[:3]:
                branch_signals.append({
                    "type":     ins["type"],
                    "severity": ins["severity"],
                    "summary":  ins["what_happened"],
                    "branch":   next((c["branch_name"] for c in profiles if c["branch_id"]==ins.get("target_branch","")), None),
                })
    except Exception as exc:
        logger.warning("executive branch_signals failed: %s", exc)

    # ── Assemble top priorities, risks, opportunities ─────────────────────────
    all_signals = (
        [{"src":"alert",  **a} for a in raw_alerts] +
        [{"src":"expense", **e} for e in exp_insights] +
        [{"src":"branch",  **b} for b in branch_signals]
    )

    def _sev_rank(s): return {"high":3,"critical":3,"medium":2,"warning":2,"low":1,"info":1}.get(s,1)

    # ── Top 3 priorities: Phase 43 narratives + legacy signals, by priority ─────
    # Phase 43 narratives (already priority-sorted: high→medium→low)
    _p43_priority_signals = [
        {"src": "narrative", "type": n.get("type",""), "severity": n.get("priority","medium"),
         "summary": n.get("what_happened",""), "urgency": n.get("urgency","soon")}
        for n in _p43_narratives
        if n.get("priority") in ("high","medium")
    ]
    # Legacy signals
    _legacy_priority_signals = [
        {"src": s["src"], "type": s.get("type",""), "severity": s.get("severity","medium"),
         "summary": s.get("message") or s.get("summary",""), "urgency": "soon"}
        for s in all_signals if _sev_rank(s.get("severity","")) >= 2
    ]
    # Deduplicate by type — Phase 43 wins on same type
    seen_types: set = set()
    merged_priority: list = []
    for sig in _p43_priority_signals + _legacy_priority_signals:
        if sig["type"] not in seen_types:
            seen_types.add(sig["type"])
            merged_priority.append(sig)

    _PRI_RANK = {"high": 0, "critical": 0, "medium": 1, "warning": 1, "low": 2, "info": 3}
    merged_priority.sort(key=lambda x: _PRI_RANK.get(x.get("severity","medium"), 2))
    top3 = merged_priority[:3]
    priorities = [
        {"rank": i+1, "source": s["src"],
         "summary": s.get("summary",""),
         "severity": s.get("severity","medium"),
         "urgency": s.get("urgency","soon"),
         "type": s.get("type","")}
        for i, s in enumerate(top3)
    ]

    # ── Risks: Phase 43 anomalies (high/medium) + legacy high signals ─────────
    risks = []
    for a in _p43_anomalies:
        if a.get("severity") in ("high","medium"):
            risks.append({"type": a.get("type",""), "severity": a.get("severity",""),
                          "description": a.get("what_happened",""),
                          "why_it_matters": a.get("why_it_matters",""),
                          "source": "phase43_anomaly"})
    for s in all_signals:
        if _sev_rank(s.get("severity","")) >= 2:
            risks.append({"type": s.get("type",""), "severity": s.get("severity",""),
                          "description": s.get("message") or s.get("summary",""),
                          "source": s["src"]})
    risks = risks[:5]

    # ── Opportunities: Phase 43 positive narratives + trend signals ───────────
    opportunities = []
    for n in _p43_narratives:
        if n.get("priority") == "low" and n.get("type") in ("strong_profitability","profit_growth_quality_issue"):
            opportunities.append({"type": n.get("type",""), "description": n.get("what_happened",""),
                                   "source_metrics": list((n.get("source_metrics") or {}).keys()),
                                   "source": "phase43"})
    if rev_dir == "improving" and np_dir == "improving" and not any(o["type"]=="growth_momentum" for o in opportunities):
        if ar:   opp = "الإيرادات والأرباح في تحسن متسق — فرصة للتوسع أو زيادة الاستثمار"
        elif tr_:opp = "Gelir ve kâr istikrarlı biçimde iyileşiyor — genişleme veya yatırım fırsatı"
        else:    opp = "Revenue and profit both improving consistently — opportunity for expansion or increased investment"
        opportunities.append({"type":"growth_momentum","description":opp,"source_metrics":["revenue_mom_pct","net_profit_mom_pct"],"source":"trend"})
    if nm and nm > 25 and not any(o["type"] in ("strong_profitability","strong_margin") for o in opportunities):
        if ar:   opp = f"هامش صافٍ قوي ({nm:.1f}٪) — ميزة تنافسية تستحق الحماية والاستثمار"
        elif tr_:opp = f"Güçlü net marj ({nm:.1f}%) — koruma ve yatırım gerektiren rekabet avantajı"
        else:    opp = f"Strong net margin ({nm:.1f}%) — competitive advantage worth protecting and investing in"
        opportunities.append({"type":"strong_margin","description":opp,"source_metrics":["net_margin_pct"],"source":"trend"})

    return {
        "company_id":    company_id,
        "company_name":  company.name,
        "lang":          safe_lang,
        "data_source":   data_source,
        "latest_period": quick_metrics["latest_period"],
        "period_count":  quick_metrics["period_count"],

        "data_scope": {
            "company_metrics": data_source,
            "branch_signals":  "portfolio_intelligence" if branch_signals else "none",
            "note": "Company metrics derived from MAIN TB uploads; branch signals from independent branch TBs via portfolio layer.",
        },

        "health": {
            "score":        health_score,
            "label":        health_label,
            "score_method": "rule_based",
        },

        "quick_metrics": quick_metrics,
        "top_priorities": priorities,
        "risks":          risks,
        "opportunities":  opportunities,
        "signals": {
            "alerts":          raw_alerts[:5],
            "expense_insights":exp_insights[:3],
            "branch_signals":  branch_signals[:3],
            "phase43": {
                "anomalies_count":  len(_p43_anomalies),
                "narratives_count": len(_p43_narratives),
                "root_causes_count":len(_p43_rc2),
            },
        },
    }



# ── Portfolio Intelligence ──────────────────────────────────────────────────────

@router.get("/companies/{company_id}/portfolio-intelligence")
def get_portfolio_intelligence(
    lang:        str = Query(default="en"),
    db:          Session = Depends(get_db),
    company:     Company = Depends(get_current_company_access),
):
    """
    Portfolio-level intelligence: summary, contribution analysis, cross-branch
    insights, and portfolio decisions.

    Uses _build_branch_profile_for_portfolio() — an internal shared helper —
    NOT a call chain through get_branch_intelligence().

    Role precedence: value_destroyer > profit_driver > growth_engine > stable
    Overall rank: composite (profitability x2 + cost x1 + growth x1)
    All text is language-aware (lang=en|ar|tr).
    """
    from app.i18n import translate as _t

    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    company_id = company.id

    branches = (
        db.query(Branch)
        .filter(Branch.company_id == company_id, Branch.is_active == True)  # noqa
        .all()
    )
    if not branches:
        raise HTTPException(404, "No active branches found.")

    # ── Build branch profiles using internal shared helper ────────────────────
    profiles = []
    for b in branches:
        financials = (
            db.query(BranchFinancial)
            .filter(BranchFinancial.branch_id == b.id)
            .order_by(BranchFinancial.period)
            .all()
        )
        p = _build_branch_profile_for_portfolio(b, financials)
        if p:
            profiles.append(p)

    if not profiles:
        raise HTTPException(422, "No financial data uploaded yet (branch financials).")

    # ── Portfolio totals ──────────────────────────────────────────────────────
    total_revenue = sum(p["kpis"]["revenue"] or 0 for p in profiles)
    total_profit  = sum(p["kpis"]["net_profit"] or 0 for p in profiles)
    portfolio_margin = round(total_profit / total_revenue * 100, 2) if total_revenue > 0 else 0.0
    latest_period = max(p["latest_period"] for p in profiles)

    # ── Contribution analysis + role + share ──────────────────────────────────
    contributions = []
    for p in profiles:
        rev = p["kpis"]["revenue"] or 0
        np_ = p["kpis"]["net_profit"] or 0
        rev_share = round(rev / total_revenue * 100, 2) if total_revenue > 0 else 0.0
        profit_share = round(np_ / total_profit * 100, 2) if total_profit and total_profit != 0 else 0.0
        role = _classify_role(
            nm_pct       = p["kpis"]["net_margin_pct"] or 0,
            profit_share = profit_share,
            c_pos        = p["trends"]["consec_positive_mom"],
        )
        contributions.append({
            **p,
            "revenue_share_pct": rev_share,
            "profit_share_pct":  profit_share,
            "role":              role,
            "role_label":        _t(f"portfolio_role_{role}", safe_lang),
        })

    # ── Ranking dimensions ────────────────────────────────────────────────────
    def _rank(lst, key_fn, ascending=True):
        sorted_items = sorted(lst, key=key_fn, reverse=not ascending)
        return {c["branch_id"]: (i + 1) for i, c in enumerate(sorted_items)}

    p_ranks = _rank(contributions, lambda c: c["kpis"]["net_margin_pct"] or -999, ascending=False)
    c_ranks = _rank(contributions, lambda c: c["kpis"]["expense_ratio"] or 999, ascending=True)
    g_ranks = _rank(contributions, lambda c: (c["trends"]["consec_positive_mom"] or 0) * max(c["kpis"]["net_margin_pct"] or 0, 0), ascending=False)

    for c in contributions:
        bid = c["branch_id"]
        pr = p_ranks[bid]; cr = c_ranks[bid]; gr = g_ranks[bid]
        composite_score = pr * 2 + cr + gr   # lower = better
        c["profitability_rank"]     = pr
        c["cost_efficiency_rank"]   = cr
        c["growth_quality_rank"]    = gr
        c["overall_portfolio_rank"] = _portfolio_rank_overall(pr, cr, gr)

    contributions.sort(key=lambda c: c["overall_portfolio_rank"])

    # ── Portfolio summary ─────────────────────────────────────────────────────
    top_contributor    = max(contributions, key=lambda c: c["kpis"]["net_profit"] or -999)
    biggest_drag       = min(contributions, key=lambda c: c["kpis"]["net_profit"] or 999)
    most_efficient     = min(contributions, key=lambda c: c["kpis"]["expense_ratio"] or 999)
    highest_cost       = max(contributions, key=lambda c: c["kpis"]["expense_ratio"] or 0)

    portfolio_summary = {
        "total_revenue":        round(total_revenue, 2),
        "total_profit":         round(total_profit, 2),
        "portfolio_margin_pct": portfolio_margin,
        "branch_count":         len(profiles),
        "top_contributor":      {"branch_id": top_contributor["branch_id"], "branch_name": top_contributor["branch_name"], "net_profit": top_contributor["kpis"]["net_profit"], "profit_share_pct": top_contributor["profit_share_pct"]},
        "biggest_drag":         {"branch_id": biggest_drag["branch_id"],   "branch_name": biggest_drag["branch_name"],   "net_profit": biggest_drag["kpis"]["net_profit"],   "profit_share_pct": biggest_drag["profit_share_pct"]},
        "most_efficient":       {"branch_id": most_efficient["branch_id"], "branch_name": most_efficient["branch_name"], "net_margin_pct": most_efficient["kpis"]["net_margin_pct"]},
        "highest_cost_pressure":{"branch_id": highest_cost["branch_id"],   "branch_name": highest_cost["branch_name"],   "expense_ratio": highest_cost["kpis"]["expense_ratio"]},
    }

    # ── Insights + decisions ──────────────────────────────────────────────────
    insights  = _build_portfolio_insights(contributions, portfolio_margin, safe_lang)
    decisions = _build_portfolio_decisions(contributions, insights, safe_lang)

    # Strip internal fields not needed in final output
    output_contributions = [
        {k: v for k, v in c.items()
         if k not in ("aggregates","trends") or k == "trends"}
        for c in contributions
    ]
    # Slim down contributions for output — keep clean schema
    slim_contributions = [{
        "branch_id":            c["branch_id"],
        "branch_name":          c["branch_name"],
        "name_ar":              c.get("name_ar"),
        "city":                 c.get("city"),
        "revenue_share_pct":    c["revenue_share_pct"],
        "profit_share_pct":     c["profit_share_pct"],
        "net_margin_pct":       c["kpis"]["net_margin_pct"],
        "expense_ratio":        c["kpis"]["expense_ratio"],
        "role":                 c["role"],
        "role_label":           c["role_label"],
        "profitability_rank":   c["profitability_rank"],
        "cost_efficiency_rank": c["cost_efficiency_rank"],
        "growth_quality_rank":  c["growth_quality_rank"],
        "overall_portfolio_rank":c["overall_portfolio_rank"],
    } for c in contributions]

    return {
        "company_id":      company_id,
        "lang":            safe_lang,
        "latest_period":   latest_period,
        "portfolio_summary": portfolio_summary,
        "contributions":   slim_contributions,
        "insights":        insights,
        "portfolio_decisions": decisions,
    }



# ── Portfolio Intelligence helpers ─────────────────────────────────────────────

def _r2(x):
    """Round to 2 decimal places — safe for None and non-numeric input."""
    try:
        return round(float(x), 2)
    except Exception:
        return None

def _build_branch_profile_for_portfolio(b: "Branch", financials: list) -> dict | None:
    """
    Shared internal builder: produces a minimal branch profile dict
    for portfolio aggregation. Does NOT call get_branch_intelligence().
    Returns None if no financials.
    """
    from app.services.analysis_engine import run_analysis, compute_trends
    import itertools
    if not financials:
        return None
    stmts = [_bf_to_stmt_dict(f) for f in financials]
    analysis = run_analysis(stmts)
    trends   = compute_trends(stmts)

    latest = financials[-1]
    lat_is = stmts[-1].get("income_statement", {})
    rev    = lat_is.get("revenue",  {}).get("total", 0) or 0
    exp    = lat_is.get("expenses", {}).get("total", 0) or 0
    np_    = lat_is.get("net_profit", 0) or 0
    nm_pct = lat_is.get("net_margin_pct", 0) or 0
    gm_pct = lat_is.get("gross_margin_pct", 0) or 0
    exp_ratio = _r2(exp / rev * 100) if rev > 0 else None

    mom_rev  = trends.get("revenue_mom_pct") or []
    mom_vals = [x for x in mom_rev if x is not None]
    c_pos = sum(1 for _ in itertools.takewhile(lambda x: x > 0, reversed(mom_vals)))
    c_neg = sum(1 for _ in itertools.takewhile(lambda x: x < 0, reversed(mom_vals)))
    last_mom = mom_vals[-1] if mom_vals else None

    rev_series = [f.revenue    or 0 for f in financials]
    np_series  = [f.net_profit or 0 for f in financials]

    return {
        "branch_id":       b.id,
        "branch_name":     b.name,
        "name_ar":         b.name_ar,
        "city":            b.city,
        "is_active":       b.is_active,
        "period_count":    len(financials),
        "latest_period":   latest.period,
        "kpis": {
            "revenue":        _r2(rev),
            "net_profit":     _r2(np_),
            "net_margin_pct": _r2(nm_pct),
            "gross_margin_pct": _r2(gm_pct),
            "expense_ratio":  exp_ratio,
        },
        "aggregates": {
            "total_revenue":    _r2(sum(rev_series)),
            "total_net_profit": _r2(sum(np_series)),
        },
        "trends": {
            "consec_positive_mom": c_pos,
            "consec_negative_mom": c_neg,
            "last_mom_revenue":    _r2(last_mom),
        },
    }


def _classify_role(nm_pct: float, profit_share: float, c_pos: int) -> str:
    """
    Explicit precedence (per approval):
    1. value_destroyer → net_margin < 0
    2. profit_driver   → nm > 20% AND profit_share > 30%
    3. growth_engine   → nm > 10% AND c_pos >= 2
    4. stable          → fallback (always set)
    """
    if nm_pct < 0:
        return "value_destroyer"
    if nm_pct > 20 and profit_share > 30:
        return "profit_driver"
    if nm_pct > 10 and c_pos >= 2:
        return "growth_engine"
    return "stable"


def _portfolio_rank_overall(p_rank: int, c_rank: int, g_rank: int) -> int:
    """
    Composite overall rank — rule-based (per approval: not profit_share alone).
    Lower is better. Simple weighted sum: profitability x2, cost x1, growth x1.
    """
    return p_rank * 2 + c_rank + g_rank


def _build_portfolio_insights(contributions: list, portfolio_margin: float, lang: str) -> list:
    """
    Cross-branch insights derived from contribution data — no new calculations.
    All text is language-aware.
    """
    ar = lang == "ar"; tr_ = lang == "tr"
    insights = []

    # ── Profit concentration ──────────────────────────────────────────────────
    profit_driver = next((c for c in contributions if c["role"] == "profit_driver"), None)
    if profit_driver and profit_driver["profit_share_pct"] > 60:
        ps = profit_driver["profit_share_pct"]; bn = profit_driver["branch_name"]
        if ar:
            wh  = f"فرع {bn} يولّد {ps:.0f}٪ من إجمالي أرباح المحفظة"
            wim = "تركّز عالٍ للربح في فرع واحد — يُشكّل خطراً هيكلياً إذا تراجع أداء هذا الفرع"
            wtd = "تطوير هوامش الفروع الأخرى لتقليل الاعتماد على مصدر ربح وحيد"
        elif tr_:
            wh  = f"{bn} şubesi portföy kârının {ps:.0f}%'ini üretiyor"
            wim = "Tek şubede yüksek kâr yoğunluğu — bu şubenin performansı düşerse yapısal risk oluşur"
            wtd = "Tek bir kâr merkezine bağımlılığı azaltmak için diğer şubelerin marjlarını geliştirin"
        else:
            wh  = f"{bn} generates {ps:.0f}% of total portfolio profit"
            wim = "High profit concentration in one branch creates structural risk if that branch underperforms"
            wtd = "Develop other branches' margins to reduce dependency on a single profit center"
        insights.append({"type":"profit_concentration","severity":"warning","what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":"medium","urgency":"short_term","decision_hint":"rebalance_resources","source_metrics":["profit_share_pct","revenue_share_pct"],"target_branch":profit_driver["branch_id"]})

    # ── Loss branch drag ──────────────────────────────────────────────────────
    destroyers = [c for c in contributions if c["role"] == "value_destroyer"]
    for d in destroyers:
        nm = d["kpis"]["net_margin_pct"]; bn = d["branch_name"]
        if ar:
            wh  = f"فرع {bn} يعمل بخسارة ({nm:.1f}٪ هامش صافٍ) بينما المحفظة مربحة"
            wim = "الفروع المربحة تُموّل خسائر هذا الفرع — يُضعف الهامش الإجمالي للمحفظة"
            wtd = "مراجعة فورية لهيكل تكاليف هذا الفرع ووضع هدف تعافٍ واضح ومحدد بوقت"
        elif tr_:
            wh  = f"{bn} zarar ediyor ({nm:.1f}% net marj) — portföy kârlı olmaya devam ediyor"
            wim = "Kârlı şubeler bu şubenin zararını sübvanse ediyor — portföyün blended marjını zayıflatıyor"
            wtd = f"{bn} için maliyet yapısını acil gözden geçirin ve zaman sınırlı bir toparlanma hedefi belirleyin"
        else:
            wh  = f"{bn} is loss-making ({nm:.1f}% net margin) while the portfolio remains profitable"
            wim = "Profitable branches are cross-subsidizing this branch's losses, weakening portfolio blended margin"
            wtd = f"Immediate cost structure review for {bn}; set a time-bound recovery target"
        insights.append({"type":"loss_branch_drag","severity":"critical","what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":"high","urgency":"immediate","decision_hint":"fix_loss_branch","source_metrics":["net_margin_pct","expense_ratio"],"target_branch":d["branch_id"]})

    # ── High growth, low margin ───────────────────────────────────────────────
    for c in contributions:
        if c["trends"]["consec_positive_mom"] >= 2 and 0 < (c["kpis"]["net_margin_pct"] or 0) < 12 and c["role"] != "value_destroyer":
            nm = c["kpis"]["net_margin_pct"]; bn = c["branch_name"]
            if ar:
                wh  = f"فرع {bn} ينمو بشكل متسق لكن هامشه الصافي منخفض ({nm:.1f}٪)"
                wim = "النمو لا يترجم إلى ربحية — يشير إلى ضغط تكاليف أو ضعف في التسعير"
                wtd = "مراجعة هيكل التسعير وتحليل مكونات التكلفة لتحويل النمو إلى ربح فعلي"
            elif tr_:
                wh  = f"{bn} istikrarlı büyüyor ancak net marjı düşük ({nm:.1f}%)"
                wim = "Büyüme kârlılığa dönüşmüyor — maliyet baskısı veya fiyatlandırma zayıflığına işaret eder"
                wtd = "Büyümeyi gerçek kâra dönüştürmek için fiyatlandırma yapısını ve maliyet bileşenlerini gözden geçirin"
            else:
                wh  = f"{bn} is growing consistently but net margin is low ({nm:.1f}%)"
                wim = "Growth not translating into profitability — signals cost pressure or pricing weakness"
                wtd = "Review pricing structure and cost components to convert growth into actual profit"
            insights.append({"type":"high_growth_low_margin","severity":"warning","what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":"medium","urgency":"short_term","decision_hint":"margin_improvement","source_metrics":["net_margin_pct","revenue_mom_pct"],"target_branch":c["branch_id"]})

    # ── Margin leader (positive signal) ──────────────────────────────────────
    margin_leader = next((c for c in contributions if c["role"] == "profit_driver"), None)
    if margin_leader and (margin_leader["kpis"]["net_margin_pct"] or 0) > portfolio_margin * 1.5:
        nm = margin_leader["kpis"]["net_margin_pct"]; bn = margin_leader["branch_name"]
        if ar:
            wh  = f"فرع {bn} يتفوق على هامش المحفظة بأكثر من 50٪ ({nm:.1f}٪ مقابل {portfolio_margin:.1f}٪)"
            wim = "هذا الفرع يمثل نموذجاً قابلاً للتكرار في بقية المحفظة"
            wtd = "توثيق العوامل المؤدية إلى هذا الأداء وتطبيق دروسه على الفروع الأخرى"
        elif tr_:
            wh  = f"{bn} portföy marjını >50% aşıyor ({nm:.1f}% vs {portfolio_margin:.1f}%)"
            wim = "Bu şube portföyde çoğaltılabilir bir model sunuyor"
            wtd = "Bu performansı sağlayan faktörleri belgeleyin ve derslerini diğer şubelere uygulayın"
        else:
            wh  = f"{bn} outperforms portfolio margin by >50% ({nm:.1f}% vs {portfolio_margin:.1f}%)"
            wim = "This branch represents a replicable model for the rest of the portfolio"
            wtd = "Document the drivers of this performance and apply its lessons to other branches"
        insights.append({"type":"margin_leader","severity":"info","what_happened":wh,"why_it_matters":wim,"what_to_do":wtd,"priority":"low","urgency":"monitor","decision_hint":"protect_margin_driver","source_metrics":["net_margin_pct","profit_share_pct"],"target_branch":margin_leader["branch_id"]})

    return insights


def _build_portfolio_decisions(contributions: list, insights: list, lang: str) -> list:
    """
    Portfolio-level decisions derived from insight patterns.
    Conservative impact language (per approval: no precise numerical claims unless safe).
    """
    ar = lang == "ar"; tr_ = lang == "tr"
    decisions = []
    seen_types = set()

    for ins in insights:
        itype = ins["type"]
        if itype in seen_types: continue
        seen_types.add(itype)
        tb    = ins.get("target_branch","")
        tb_name = next((c["branch_name"] for c in contributions if c["branch_id"] == tb), tb)

        if itype == "loss_branch_drag":
            if ar:
                title  = f"معالجة خسائر فرع {tb_name} قبل تآكل هامش المحفظة"
                reason = f"هامش {tb_name} السالب يضغط على ربحية المحفظة الإجمالية"
                impact = "إعادة الفرع إلى نقطة التعادل ستُحسّن الهامش المدمج للمحفظة"
            elif tr_:
                title  = f"{tb_name} zararları portföy marjını aşındırmadan önce ele alın"
                reason = f"{tb_name}'ın negatif marjı genel portföy kârlılığını baskılıyor"
                impact = f"Şubeyi başabaş noktasına döndürmek portföyün blended marjını iyileştirir"
            else:
                title  = f"Address {tb_name} losses before they erode portfolio margin"
                reason = f"{tb_name}'s negative margin is suppressing overall portfolio profitability"
                impact = f"Returning {tb_name} to breakeven would improve the portfolio's blended margin"
            decisions.append({"title":title,"priority":"high","domain":"profitability","target_branch":tb_name,"reason":reason,"expected_impact":impact,"time_horizon":"immediate","owner_scope":"cfo","source_metrics":["net_margin_pct","profit_share_pct"]})

        elif itype == "profit_concentration":
            if ar:
                title  = f"تنويع مصادر الربح بعيداً عن الاعتماد على {tb_name}"
                reason = "تركّز مفرط للأرباح في فرع واحد يُشكّل خطراً هيكلياً"
                impact = "تقليل الاعتماد على مصدر ربح وحيد يُعزّز مرونة المحفظة"
            elif tr_:
                title  = f"Kâr kaynaklarını {tb_name}'a bağımlılıktan çeşitlendirin"
                reason = "Tek şubede aşırı kâr yoğunluğu yapısal risk oluşturuyor"
                impact = "Tek bir kâr merkezine bağımlılığın azaltılması portföy esnekliğini artırır"
            else:
                title  = f"Diversify profit sources away from over-reliance on {tb_name}"
                reason = "Excessive profit concentration in one branch creates structural portfolio risk"
                impact = "Reducing single-source dependency strengthens portfolio resilience"
            decisions.append({"title":title,"priority":"medium","domain":"revenue","target_branch":tb_name,"reason":reason,"expected_impact":impact,"time_horizon":"short","owner_scope":"cfo","source_metrics":["profit_share_pct","revenue_share_pct"]})

        elif itype == "margin_leader":
            if ar:
                title  = f"حماية ونمو فرع {tb_name} بوصفه المحرك الرئيسي للأرباح"
                reason = f"{tb_name} يتمتع بأعلى هامش في المحفظة ويمثل أصلاً استراتيجياً"
                impact = "الحفاظ على أداء هذا الفرع يصون الصحة المالية الإجمالية للمحفظة"
            elif tr_:
                title  = f"{tb_name}'ı birincil kâr motoru olarak koruyun ve büyütün"
                reason = f"{tb_name} portföydeki en yüksek marjla stratejik bir varlık"
                impact = "Bu şubenin performansının korunması portföyün genel finansal sağlığını güvence altına alır"
            else:
                title  = f"Protect and grow {tb_name} as the primary profit engine"
                reason = f"{tb_name} holds the highest margin in the portfolio and is a strategic asset"
                impact = "Sustaining this branch's performance safeguards the portfolio's overall financial health"
            decisions.append({"title":title,"priority":"low","domain":"revenue","target_branch":tb_name,"reason":reason,"expected_impact":impact,"time_horizon":"medium","owner_scope":"cfo","source_metrics":["net_margin_pct","profit_share_pct"]})

        elif itype == "high_growth_low_margin":
            if ar:
                title  = f"تحويل نمو فرع {tb_name} إلى ربحية فعلية"
                reason = f"{tb_name} ينمو باستمرار لكن هامشه لا يعكس هذا النمو"
                impact = "تحسين هامش هذا الفرع سيُعزّز جودة أرباح المحفظة الإجمالية"
            elif tr_:
                title  = f"{tb_name}'ın büyümesini gerçek kârlılığa dönüştürün"
                reason = f"{tb_name} tutarlı büyüyor ancak marjı bu büyümeyi yansıtmıyor"
                impact = "Bu şubenin marjının iyileştirilmesi portföyün genel kâr kalitesini artırır"
            else:
                title  = f"Convert {tb_name}'s growth into actual profitability"
                reason = f"{tb_name} is growing consistently but margin does not reflect this growth"
                impact = "Improving this branch's margin will enhance the portfolio's overall profit quality"
            decisions.append({"title":title,"priority":"medium","domain":"profitability","target_branch":tb_name,"reason":reason,"expected_impact":impact,"time_horizon":"short","owner_scope":"branch_manager","source_metrics":["net_margin_pct","expense_ratio"]})

    return decisions


# ── Internal helpers ──────────────────────────────────────────────────────────

def _safe_pct(current, previous):
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def _trend(pct):
    if pct is None:
        return "unknown"
    if pct > 0.5:
        return "up"
    if pct < -0.5:
        return "down"
    return "flat"


# ── Branch financial upsert (called from uploads.py) ─────────────────────────

def upsert_branch_financial(
    db:        Session,
    branch_id: str,
    company_id: str,
    period:    str,
    df:        pd.DataFrame,
    upload_id: str,
) -> None:
    """
    Extract financial totals from a classified DataFrame and upsert
    into branch_financials. Called after a successful upload with branch_id.

    Revenue and gross_profit are stored as absolute values because they are
    always presented as positive business metrics in comparison screens.
    Net profit is kept signed (negative = loss).
    """
    from app.services.financial_statements import build_statements, statements_to_dict

    fs = build_statements(df, company_id=company_id, period=period)
    d  = statements_to_dict(fs)
    is_ = d.get("income_statement", {})
    bs  = d.get("balance_sheet", {})

    def _absf(v):
        """Return abs(float(v)) or None — never propagate negative to comparison."""
        try:
            f = float(v)
            return abs(f) if f != 0 else 0.0
        except (TypeError, ValueError):
            return None

    def _floatf(v):
        """Return float(v) or None — for signed metrics like net_profit."""
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    revenue      = _absf(is_.get("revenue",    {}).get("total"))
    cogs         = _absf(is_.get("cogs",       {}).get("total"))
    gross_profit = _floatf(is_.get("gross_profit"))   # can be negative (negative margin)
    expenses     = _absf(is_.get("expenses",   {}).get("total"))
    net_profit   = _floatf(is_.get("net_profit"))     # can be negative (loss)
    total_assets = _absf(bs.get("assets",      {}).get("total"))

    # Delete existing record for this branch+period if any
    db.query(BranchFinancial).filter(
        BranchFinancial.branch_id == branch_id,
        BranchFinancial.period    == period,
    ).delete()

    record = BranchFinancial(
        branch_id    = branch_id,
        company_id   = company_id,
        period       = period,
        revenue      = revenue,
        cogs         = cogs,
        gross_profit = gross_profit,
        expenses     = expenses,
        net_profit   = net_profit,
        total_assets = total_assets,
        upload_id    = upload_id,
    )
    db.add(record)
    # commit handled by caller
