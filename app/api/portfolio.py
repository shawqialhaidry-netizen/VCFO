"""
api/portfolio.py — Phase 28
Portfolio-level intelligence endpoint.
Supports Phase 22 universal scope.
"""
import logging

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.company import Company
from app.models.trial_balance import TrialBalanceUpload
from app.models.user import User
from app.models.membership import Membership
from app.services.financial_statements import build_statements, statements_to_dict
from app.services.analysis_engine import run_analysis
from app.services.time_intelligence import filter_periods
from app.services.time_scope import scope_from_params, filter_by_scope
from app.services.period_aggregation import build_annual_layer
from app.services.fin_intelligence import build_intelligence
from app.services.portfolio_engine import build_portfolio

logger = logging.getLogger("vcfo.portfolio")

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

VALID_WINDOWS = {"3M", "6M", "12M", "YTD", "ALL"}


def _load_df(record: TrialBalanceUpload):
    if not record.normalized_path:
        return None
    try:
        df = pd.read_csv(record.normalized_path)
    except Exception:
        return None
    required = {"account_code", "account_name", "debit", "credit", "mapped_type"}
    return df if required.issubset(set(df.columns)) else None


def _build_period_statements(company_id: str, uploads: list) -> list[dict]:
    period_dfs: dict[str, pd.DataFrame] = {}
    for record in uploads:
        df = _load_df(record)
        if df is None or df.empty:
            continue
        if "period" in df.columns:
            for period, grp in df.groupby("period"):
                period_dfs[str(period)] = grp.copy()
        elif record.period:
            period_dfs[record.period] = df.copy()
    if not period_dfs:
        return []
    stmts = []
    for period in sorted(period_dfs.keys()):
        fs = build_statements(period_dfs[period], company_id=company_id, period=period)
        d  = statements_to_dict(fs)
        d["period"] = period
        stmts.append(d)
    return stmts


def _build_company_intelligence(
    company:      Company,
    db:           Session,
    window:       str,
    scope22:      dict | None,
) -> dict | None:
    """Run intelligence pipeline for one company. Returns None if no data."""
    uploads = (
        db.query(TrialBalanceUpload)
        .filter(TrialBalanceUpload.company_id == company.id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None))  # company-level only
        .order_by(TrialBalanceUpload.uploaded_at.asc())
        .all()
    )
    if not uploads:
        return None

    all_stmts = _build_period_statements(company.id, uploads)
    if not all_stmts:
        return None

    # Apply Phase 22 scope if provided, else fall back to window
    if scope22 and not scope22.get("error"):
        windowed = filter_by_scope(all_stmts, scope22)
        if not windowed:
            windowed = all_stmts
    else:
        windowed = filter_periods(all_stmts, window)

    analysis = run_analysis(windowed)
    annual   = build_annual_layer(windowed)

    return build_intelligence(
        analysis     = analysis,
        annual_layer = annual,
        currency     = company.currency or "",
    )


@router.get("/overview")
def portfolio_overview(
    lang:        str = Query(default="en"),
    window:      str = Query(default="ALL", description="3M | 6M | 12M | YTD | ALL"),
    # Phase 22 scope
    basis_type:  str = Query(default="all"),
    period:      str = Query(default=""),
    year_scope:  str = Query(default="", alias="year"),
    from_period: str = Query(default=""),
    to_period:   str = Query(default=""),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Phase 28 Portfolio Intelligence.
    Compares and ranks all accessible companies.
    Supports Phase 22 universal scope.
    """
    safe_lang   = lang   if lang.lower()   in ("en", "ar", "tr")  else "en"
    safe_window = window.upper() if window.upper() in VALID_WINDOWS else "ALL"

    # ── Resolve accessible companies — auth always required ───────────────────
    allowed_ids = [
        m.company_id for m in
        db.query(Membership).filter(
            Membership.user_id   == current_user.id,
            Membership.is_active == True,  # noqa: E712
        ).all()
    ]
    companies = db.query(Company).filter(
        Company.id.in_(allowed_ids),
        Company.is_active == True,  # noqa: E712
    ).all()

    if not companies:
        return {
            "status": "success",
            "data":   {"available": False, "reason": "No companies found."},
            "meta":   {"n": 0, "window": safe_window, "lang": safe_lang, "scope": None},
        }

    # ── Build scope once (applied to all companies) ───────────────────────────
    # Use the first company's data to resolve the scope (same date range applies to all)
    scope22 = None
    if (basis_type or "").lower() not in ("all", ""):
        # Build a stub scope without company-specific data first
        # Per-company filter happens in _build_company_intelligence
        scope22 = scope_from_params(
            basis_type  = basis_type,
            period      = period      or None,
            year        = year_scope  or None,
            from_period = from_period or None,
            to_period   = to_period   or None,
            all_stmts   = [],  # period validation deferred to per-company
        )
        if scope22.get("error"):
            raise HTTPException(400, scope22["error"])

    # Build normalized scope for meta
    scope_meta = scope22 if scope22 else {
        "basis_type":  "all",
        "label":       f"window={safe_window}",
        "months":      [],
        "from_period": None,
        "to_period":   None,
        "error":       None,
    }

    # ── Per-company intelligence ──────────────────────────────────────────────
    company_data = []
    skipped = []
    for co in companies:
        try:
            intel = _build_company_intelligence(co, db, safe_window, scope22)
            if intel is None:
                skipped.append(co.name)
                continue
            company_data.append({
                "company_id":   co.id,
                "company_name": co.name,
                "currency":     co.currency or "",
                "intelligence": intel,
            })
        except Exception as exc:
            logger.warning("Portfolio: skipped %s — %s", co.name, exc)
            skipped.append(co.name)

    result = build_portfolio(company_data, lang=safe_lang)

    return {
        "status": "success",
        "data":   result,
        "meta": {
            "n":          len(company_data),
            "skipped":    skipped,
            "window":     safe_window,
            "lang":       safe_lang,
            "scope":      scope_meta,
        },
    }
