"""
api/statements.py — Phase 4
Endpoints:
  GET /statements/{upload_id}
      → Build IS + BS from the normalized+classified CSV of a given upload

  GET /statements/company/{company_id}
      → List all uploads for a company (periods available)

  GET /statements/company/{company_id}/multi
      → Multi-period financial statements

FIX-S1: All endpoints protected with membership enforcement.
"""
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.deps import require_active_membership, require_company_access
from app.models.trial_balance import TrialBalanceUpload
from app.models.company import Company
from app.services.financial_statements import build_statements, statements_to_dict

router = APIRouter(prefix="/statements", tags=["statements"])


# ── FIX-S1: Auth helpers ───────────────────────────────────────────────────────

def _get_user_optional(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Extract current user from Bearer token; return None if absent/invalid.
    Used by /{upload_id} which has no company_id in the path.
    """
    auth: Optional[str] = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    try:
        from jose import JWTError, jwt
        from app.core.config import settings
        payload = jwt.decode(token, settings.JWT_SECRET_KEY,
                             algorithms=["HS256"])
        user_id = payload.get("sub")
    except Exception:
        return None
    from app.models.user import User
    return db.query(User).filter(
        User.id == user_id, User.is_active == True  # noqa
    ).first()


def _check_upload_access(company_id: str, current_user, db: Session):
    """
    Verify current_user has active membership for company_id.
    Raises 401 if no authenticated user and ENFORCE_MEMBERSHIP=True.
    Raises 403 if user has no membership for the company.
    In dev mode (ENFORCE_MEMBERSHIP=False) with no user → pass through.
    """
    from app.core.config import settings

    enforce = getattr(settings, "ENFORCE_MEMBERSHIP", False)
    if not current_user:
        if enforce:
            raise HTTPException(status_code=401,
                                detail="Authentication required")
        return  # dev mode pass-through

    require_active_membership(db, current_user.id, company_id)


# ── Helper ─────────────────────────────────────────────────────────────────────

def _load_classified_df(record: TrialBalanceUpload) -> pd.DataFrame:
    """Load the normalized+classified CSV saved during upload (Phase 2+3)."""
    if not record.normalized_path:
        raise HTTPException(status_code=422, detail="No normalized file found for this upload.")
    try:
        df = pd.read_csv(record.normalized_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Normalized file not found on disk.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read file: {e}")

    required = {"account_code", "account_name", "debit", "credit", "mapped_type", "confidence"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"File is missing Phase 3 classification columns: {missing}. Re-upload the file.",
        )
    return df


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/{upload_id}")
def get_statements_by_upload(
    upload_id:    str,
    db:           Session = Depends(get_db),
    current_user = Depends(_get_user_optional),  # FIX-S1: auth gate
):
    """
    Build Income Statement + Balance Sheet from a specific upload.
    FIX-S1: Verifies caller has membership for the upload's company.
    """
    record = db.query(TrialBalanceUpload).filter(
        TrialBalanceUpload.id == upload_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Upload not found.")
    if record.status != "ok":
        raise HTTPException(
            status_code=422,
            detail=f"Upload status is '{record.status}'. Only 'ok' uploads can generate statements.",
        )

    # FIX-S1: verify membership before returning financial data
    _check_upload_access(record.company_id, current_user, db)

    df = _load_classified_df(record)

    # FIX-S0: pass tb_type so equity injection is correct for pre_closing uploads
    fs = build_statements(
        df         = df,
        company_id = record.company_id,
        period     = record.period or "",
        tb_type    = getattr(record, "tb_type", None),
    )

    result = statements_to_dict(fs)
    result["upload_id"]       = upload_id
    result["original_file"]   = record.original_filename
    result["format_detected"] = record.format_detected
    result["record_count"]    = record.record_count

    return result


@router.get("/company/{company_id}")
def list_company_periods(
    company_id:   str,
    db:           Session = Depends(get_db),
    _access:      Company = Depends(require_company_access),  # FIX-S1: auth gate
):
    """
    List all successful uploads for a company.
    FIX-S1: require_company_access enforces membership.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    uploads = (
        db.query(TrialBalanceUpload)
        .filter(
            TrialBalanceUpload.company_id == company_id,
            TrialBalanceUpload.status == "ok",
            TrialBalanceUpload.branch_id.is_(None),  # company-level only
        )
        .order_by(TrialBalanceUpload.uploaded_at.desc())
        .all()
    )

    return {
        "company_id":   company_id,
        "company_name": company.name,
        "uploads": [
            {
                "upload_id":         u.id,
                "period":            u.period,
                "original_filename": u.original_filename,
                "record_count":      u.record_count,
                "uploaded_at":       u.uploaded_at.isoformat() if u.uploaded_at else None,
            }
            for u in uploads
        ],
    }


@router.get("/company/{company_id}/multi")
def get_multi_period_statements(
    company_id:   str,
    periods:      str = Query(default="", description="Comma-separated periods e.g. 2025-10,2025-11"),
    db:           Session = Depends(get_db),
    _access:      Company = Depends(require_company_access),  # FIX-S1: auth gate
):
    """
    Multi-period financial statements.
    FIX-S1: require_company_access enforces membership.
    FIX-S0: tb_type passed to build_statements for correct equity.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

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
        raise HTTPException(status_code=422, detail="No financial data uploaded yet. Upload a Trial Balance first.")

    period_dfs: dict[str, pd.DataFrame] = {}
    for record in uploads:
        try:
            df = _load_classified_df(record)
        except Exception:
            continue
        if "period" in df.columns:
            for p, grp in df.groupby("period"):
                period_dfs[str(p)] = grp.copy()
        elif record.period:
            period_dfs[record.period] = df.copy()

    if not period_dfs:
        raise HTTPException(status_code=422, detail="Could not build statements.")

    requested = [p.strip() for p in periods.split(",") if p.strip()] if periods else []
    target_periods = sorted(
        [p for p in period_dfs if p in requested] if requested
        else list(period_dfs.keys())
    )

    result = []
    for period in target_periods:
        # FIX-S0: resolve tb_type per period
        _tb = next((getattr(u, "tb_type", None) for u in uploads if u.period == period), None)
        # FIX-P4: use _mom helper (no local duplication)
        fs = build_statements(period_dfs[period], company_id=company_id,
                              period=period, tb_type=_tb)
        d = statements_to_dict(fs)
        result.append(d)

    for i, stmt in enumerate(result):
        if i == 0:
            stmt["mom"] = None
            continue
        prev = result[i - 1]
        is_curr = stmt["income_statement"]
        is_prev = prev["income_statement"]
        # FIX-P4: use _mom helper (renamed from _pct_change for clarity)
        def _mom(curr, prior):
            if prior and prior != 0:
                return round((curr - prior) / abs(prior) * 100, 2)
            return None
        stmt["mom"] = {
            "revenue_pct":      _mom(is_curr["revenue"]["total"],   is_prev["revenue"]["total"]),
            "gross_profit_pct": _mom(is_curr["gross_profit"],       is_prev["gross_profit"]),
            "op_profit_pct":    _mom(is_curr["operating_profit"],   is_prev["operating_profit"]),
            "net_profit_pct":   _mom(is_curr["net_profit"],         is_prev["net_profit"]),
            "cogs_pct_change":  _mom(is_curr["cogs"]["total"],      is_prev["cogs"]["total"]),
            "opex_pct_change":  _mom(is_curr["expenses"]["total"],  is_prev["expenses"]["total"]),
        }

    return {
        "company_id":   company_id,
        "company_name": company.name,
        "currency":     company.currency or "USD",
        "period_count": len(result),
        "periods":      target_periods,
        "statements":   result,
    }
