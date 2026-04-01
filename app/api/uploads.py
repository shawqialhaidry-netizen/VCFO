"""
uploads.py — Phase 2 (Hardened) + Phase 3 Classification
Supports:
  - monthly upload  (period = YYYY-MM)
  - annual upload   (year = YYYY, expands to 12 months)
"""
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.membership import Membership
from app.models.user import User
from app.models.company import Company
from app.models.trial_balance import TrialBalanceUpload
from app.services.tb_parser import parse_file
from app.services.account_classifier import classify_dataframe, build_classification_summary

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOADS_DIR       = Path("data/uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
MAX_FILE_SIZE      = 20 * 1024 * 1024   # 20 MB


def _safe(v):
    """Serialise numpy scalar types to native Python."""
    if isinstance(v, np.integer): return int(v)
    if isinstance(v, np.floating): return float(v)
    if isinstance(v, np.bool_): return bool(v)
    return v


logger = logging.getLogger("vcfo.uploads")


def _delete_period_data(
    db,
    company_id: str,
    periods_to_replace: list[str],
    branch_id: str | None = None,
) -> list[dict]:
    """
    Delete existing 'ok' upload records for a company whose period matches
    any value in periods_to_replace AND whose branch_id matches exactly.

    Duplicate identity = company_id + period + branch_id:
      - branch_id=None  → only replaces other company-level (null branch) uploads
      - branch_id=X     → only replaces uploads for that exact branch

    Does NOT touch records belonging to other periods, other branches, or
    records with status != 'ok' (errors stay for audit trail).
    Atomic: all deletions happen before the new record is committed.
    """
    replaced_log = []

    for period in periods_to_replace:
        q = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.period     == period,
                TrialBalanceUpload.status     == "ok",
            )
        )
        # Match branch_id exactly: NULL vs NULL, or value vs same value
        if branch_id is None:
            q = q.filter(TrialBalanceUpload.branch_id.is_(None))
        else:
            q = q.filter(TrialBalanceUpload.branch_id == branch_id)

        existing = q.all()

        for rec in existing:
            for path_attr in ("raw_path", "normalized_path"):
                fpath = getattr(rec, path_attr, None)
                if fpath and os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                    except OSError as e:
                        logger.warning(
                            "Could not delete file %s for upload %s: %s",
                            fpath, rec.id, e,
                        )

            replaced_log.append({
                "replaced_upload_id": rec.id,
                "period":             period,
                "filename":           rec.original_filename,
                "uploaded_at":        rec.uploaded_at.isoformat() if rec.uploaded_at else None,
            })

            db.delete(rec)
            logger.info(
                "Replaced existing data for period %s branch %s "
                "(company=%s, old_upload_id=%s, file=%s)",
                period, branch_id, company_id, rec.id, rec.original_filename,
            )

    return replaced_log


def _periods_for_branch_upsert(
    df,
    generated_periods: list | None,
    db_period: str | None,
) -> list[str]:
    """
    Periods to write into branch_financials. The TB parser sets generated_periods
    from the upload form (monthly/annual) but leaves it empty for auto_detect
    when the user does not pass period/year — even though the normalized df
    still has a real YYYY-MM column. Without this fallback, branch uploads
    commit TrialBalanceUpload but never call upsert_branch_financial.
    """
    if generated_periods:
        return [p for p in generated_periods if p]
    if db_period:
        return [db_period]
    if df is not None and "period" in getattr(df, "columns", []):
        seen: set[str] = set()
        for x in df["period"].dropna().astype(str).str.strip().unique():
            if x and re.match(r"^\d{4}-\d{2}$", x):
                seen.add(x)
        return sorted(seen)
    return []


# ── POST /uploads ─────────────────────────────────────────────────────────────

@router.post("")
async def upload_trial_balance(
    file:        UploadFile = File(...),
    company_id:  str        = Form(...),
    upload_mode: str        = Form(default="monthly"),  # "monthly" | "annual"
    period:      str        = Form(default=""),          # YYYY-MM  (monthly mode)
    year:        str        = Form(default=""),          # YYYY     (annual mode)
    branch_id:   str        = Form(default=""),          # optional — branch-level upload
    tb_type:     str        = Form(default=""),          # "pre_closing" | "post_closing" | "" (unknown)
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # ── Validate company ──────────────────────────────────────────────────────
    company = db.query(Company).filter(
        Company.id == company_id, Company.is_active == True  # noqa
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # ── Enforce membership + role (viewer cannot upload) ─────────────────────
    _membership = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == company_id,
        Membership.is_active  == True,  # noqa
    ).first()
    if not _membership:
        raise HTTPException(status_code=403, detail="Access denied")
    if _membership.role not in ("owner", "analyst"):
        raise HTTPException(status_code=403, detail="Viewer role cannot upload data")

    # ── Validate upload_mode ──────────────────────────────────────────────────
    if upload_mode not in {"monthly", "annual", "auto_detect"}:
        raise HTTPException(status_code=400,
            detail="upload_mode must be 'monthly', 'annual', or 'auto_detect'")

    # For period/year validation: auto_detect behaves like monthly until the
    # parser confirms the actual mode. We validate period only if mode is
    # explicitly monthly; year only if mode is explicitly annual.

    # ── Validate tb_type — FIX-2.1 ──────────────────────────────────────────
    _VALID_TB_TYPES = {"pre_closing", "post_closing", ""}
    if tb_type not in _VALID_TB_TYPES:
        raise HTTPException(status_code=400,
            detail="tb_type must be 'pre_closing', 'post_closing', or omitted")
    # Normalize: empty string → None (unknown)
    resolved_tb_type: str | None = tb_type.strip() if tb_type.strip() else None

    # ── Validate branch_id — optional, must belong to same company ───────────
    resolved_branch_id: str | None = branch_id.strip() if branch_id.strip() else None
    if resolved_branch_id:
        from app.models.branch import Branch as _Branch
        _branch = db.query(_Branch).filter(
            _Branch.id        == resolved_branch_id,
            _Branch.is_active == True,  # noqa
        ).first()
        if not _branch:
            raise HTTPException(status_code=404,
                detail=f"Branch '{resolved_branch_id}' not found or inactive")
        if _branch.company_id != company_id:
            raise HTTPException(status_code=403,
                detail="Branch does not belong to this company")

    # ── Validate period / year inputs ─────────────────────────────────────────
    parsed_year: int | None = None
    parsed_period: str | None = None

    if upload_mode == "monthly":
        if period:
            import re
            if not re.match(r"^\d{4}-\d{2}$", period.strip()):
                raise HTTPException(status_code=400, detail="period must be YYYY-MM format")
            parsed_period = period.strip()
    elif upload_mode == "annual":
        if year:
            try:
                parsed_year = int(year.strip())
                if not (2000 <= parsed_year <= 2100):
                    raise ValueError
            except ValueError:
                raise HTTPException(status_code=400, detail="year must be a valid 4-digit year")
        else:
            raise HTTPException(status_code=400, detail="year is required for annual upload mode")
    else:   # auto_detect — accept either period or year, neither required
        if period and period.strip():
            import re
            if re.match(r"^\d{4}-\d{2}$", period.strip()):
                parsed_period = period.strip()
        if year and year.strip():
            try:
                parsed_year = int(year.strip())
            except ValueError:
                pass

    # ── Validate file type ────────────────────────────────────────────────────
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # ── Read bytes ────────────────────────────────────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # ── Save raw file ─────────────────────────────────────────────────────────
    upload_id = str(uuid.uuid4())
    ts        = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{ts}_{upload_id[:8]}{ext}"
    raw_path  = UPLOADS_DIR / company_id / safe_name
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(file_bytes)

    # ── Parse ─────────────────────────────────────────────────────────────────
    parse_result = parse_file(
        file_bytes  = file_bytes,
        filename    = file.filename,
        period      = parsed_period,
        upload_mode = upload_mode,
        year        = parsed_year,
    )

    if not parse_result["ok"]:
        # For mode_conflict errors, return 409 Conflict with suggested_mode hint
        if parse_result.get("mode_conflict"):
            raise HTTPException(
                status_code=409,
                detail={
                    "error":          parse_result["error"],
                    "mode_conflict":  True,
                    "suggested_mode": parse_result.get("suggested_mode", "annual"),
                },
            )
        record = TrialBalanceUpload(
            id                = upload_id,
            company_id        = company_id,
            original_filename = file.filename,
            raw_path          = str(raw_path),
            period            = parsed_period or (str(parsed_year) if parsed_year else None),
            status            = "error",
            error_message     = parse_result["error"],
        )
        db.add(record); db.commit()
        raise HTTPException(status_code=422, detail=parse_result["error"])

    df                 = parse_result["df"]
    validation         = parse_result["validation"]
    generated_periods  = parse_result["generated_periods"]
    detected_format    = parse_result["format"]       # standard | long | annual_wide
    actual_upload_mode = parse_result["upload_mode"]  # monthly | annual

    # ── Phase 3: Classify ─────────────────────────────────────────────────────
    df = classify_dataframe(df)
    classification_summary = build_classification_summary(df)

    # ── Save normalised CSV ───────────────────────────────────────────────────
    norm_name = safe_name.replace(ext, "_normalized.csv")
    norm_path = UPLOADS_DIR / company_id / norm_name
    df.to_csv(norm_path, index=False, encoding="utf-8-sig")

    # ── Determine period label for DB ─────────────────────────────────────────
    # For annual: store the year as period so it's human-readable in the UI
    db_period = parsed_period or (str(parsed_year) if parsed_year else None)

    # ── Safe override: delete existing data for affected periods ──────────────
    # Build the exact list of periods this upload covers so we replace only those.
    # Monthly: [parsed_period]  |  Annual: generated_periods (e.g. 12 months)
    periods_this_upload: list[str] = []
    if generated_periods:
        periods_this_upload = [p for p in generated_periods if p]
    elif parsed_period:
        periods_this_upload = [parsed_period]

    replaced_log: list[dict] = []
    was_replaced = False

    if periods_this_upload:
        replaced_log = _delete_period_data(db, company_id, periods_this_upload, resolved_branch_id)
        was_replaced  = len(replaced_log) > 0
        if was_replaced:
            db.flush()   # flush deletes before inserting new record

    # ── Save DB record ────────────────────────────────────────────────────────
    record = TrialBalanceUpload(
        id                = upload_id,
        company_id        = company_id,
        original_filename = file.filename,
        raw_path          = str(raw_path),
        normalized_path   = str(norm_path),
        period            = db_period,
        format_detected   = f"{actual_upload_mode}/{detected_format}",
        record_count      = validation["record_count"],
        total_debit       = validation["total_debit"],
        total_credit      = validation["total_credit"],
        is_balanced       = str(validation["balanced"]).lower(),
        status            = "ok",
        tb_type           = resolved_tb_type,
        branch_id         = resolved_branch_id,  # NULL = company-level, value = branch-level
    )
    db.add(record); db.commit(); db.refresh(record)

    # ── Branch financial upsert (if branch_id provided) ───────────────────────
    branch_upsert_periods: list[str] = []
    if resolved_branch_id:
        branch_upsert_periods = _periods_for_branch_upsert(df, generated_periods, db_period)
        try:
            from app.api.branches import upsert_branch_financial

            if not branch_upsert_periods:
                logger.warning(
                    "Branch upload %s: no YYYY-MM period resolved for BranchFinancial "
                    "(branch_id=%s company_id=%s). Set period on the upload form or include "
                    "a period column in the file.",
                    upload_id,
                    resolved_branch_id,
                    company_id,
                )
            for gp in branch_upsert_periods:
                if "period" in df.columns:
                    gdf = df[df["period"].astype(str).str.strip() == str(gp).strip()].copy()
                    if gdf.empty:
                        gdf = df.copy()
                else:
                    gdf = df.copy()
                upsert_branch_financial(db, resolved_branch_id, company_id, gp, gdf, upload_id)
            db.commit()
        except Exception as _be:
            logger.warning("branch upsert failed for branch=%s: %s", resolved_branch_id, _be)

    # ── Build preview (first 10 rows) ─────────────────────────────────────────
    preview_rows = [
        {k: _safe(v) for k, v in row.items()}
        for row in df.head(10).to_dict(orient="records")
    ]

    # ── Period breakdown for annual uploads ───────────────────────────────────
    period_breakdown = validation.get("period_breakdown", {})

    return {
        "id":                   record.id,
        "company_id":           company_id,
        "filename":             file.filename,

        # ── Override metadata ─────────────────────────────────────────────────
        "replaced":             was_replaced,
        "replaced_periods":     [r["period"] for r in replaced_log],
        "replaced_log":         replaced_log,

        # ── Format / mode info ─────────────────────────────────────────────────
        "upload_mode":          actual_upload_mode,
        "detected_format":      detected_format,
        "generated_periods":    generated_periods,

        # ── Period ─────────────────────────────────────────────────────────────
        "period":               db_period,

        # ── Totals ─────────────────────────────────────────────────────────────
        "normalized_row_count": validation["record_count"],
        "total_debit":          float(validation["total_debit"]),
        "total_credit":         float(validation["total_credit"]),
        "diff":                 float(validation["diff"]),
        # tb_balanced: total_debit == total_credit (TB accounting identity)
        # This does NOT mean the Balance Sheet will balance.
        # BS balance depends on tb_type and net_profit injection.
        "balanced":             bool(validation["balanced"]),   # kept for compat
        "tb_balanced":          bool(validation["balanced"]),
        "tb_balance_note":      (
            "TB is balanced: total debits equal total credits. "
            "Balance Sheet balance depends on tb_type and net profit treatment."
            if validation["balanced"]
            else "TB is unbalanced: total debits do not equal total credits."
        ),
        "period_breakdown":     period_breakdown,

        "status": "ok",
        "branch_id":            resolved_branch_id,
        # Populated for branch uploads: periods written to branch_financials (verify pipeline)
        "branch_financial_periods_written": branch_upsert_periods,

        # ── Classification summary ─────────────────────────────────────────────
        "summary": {
            "classified_ratio": classification_summary["classified_ratio"],
            "unknown_accounts": classification_summary["unknown_accounts"],
            "type_breakdown":   classification_summary["type_breakdown"],
        },

        # ── Preview ───────────────────────────────────────────────────────────
        "preview": preview_rows,
    }


# ── GET /uploads ──────────────────────────────────────────────────────────────

@router.get("")
def list_uploads(
    company_id:  str     = None,
    db:          Session = Depends(get_db),
    current_user         = Depends(get_current_user),
):
    # Always filter by membership — no unauthenticated access
    allowed = [m.company_id for m in db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.is_active  == True,  # noqa
    ).all()]
    q = db.query(TrialBalanceUpload).filter(TrialBalanceUpload.company_id.in_(allowed))
    if company_id:
        q = q.filter(TrialBalanceUpload.company_id == company_id)
    uploads = q.order_by(TrialBalanceUpload.uploaded_at.desc()).limit(100).all()
    return [
        {
            "id":                u.id,
            "company_id":        u.company_id,
            "original_filename": u.original_filename,
            "period":            u.period,
            "format_detected":   u.format_detected,
            "record_count":      u.record_count,
            "total_debit":       u.total_debit,
            "total_credit":      u.total_credit,
            "is_balanced":       u.is_balanced,
            "tb_balanced":       u.is_balanced,
            "tb_type":           getattr(u, "tb_type",    None),
            "branch_id":         getattr(u, "branch_id",  None),
            "status":            u.status,
            "error_message":     u.error_message,
            "uploaded_at":       u.uploaded_at.isoformat() if u.uploaded_at else None,
        }
        for u in uploads
    ]


# ── GET /uploads/{upload_id}/preview ─────────────────────────────────────────

@router.get("/{upload_id}/preview")
def preview_upload(
    upload_id:   str,
    db:          Session = Depends(get_db),
    current_user         = Depends(get_current_user),
):
    import pandas as pd

    record = db.query(TrialBalanceUpload).filter(
        TrialBalanceUpload.id == upload_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Enforce membership for the upload's company (Task 5)
    _mem = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == record.company_id,
        Membership.is_active  == True,  # noqa
    ).first()
    if not _mem:
        raise HTTPException(status_code=403, detail="Access denied")

    if record.status != "ok" or not record.normalized_path:
        raise HTTPException(status_code=422, detail="No normalized data available")

    df = pd.read_csv(record.normalized_path)
    return {
        "upload_id":    upload_id,
        "record_count": len(df),
        "columns":      list(df.columns),
        "rows":         df.head(50).to_dict(orient="records"),
    }


# ── DELETE /uploads/{upload_id} — UPGRADE 1 ─────────────────────────────────

@router.delete("/{upload_id}")
def delete_upload(
    upload_id:    str,
    mode:         str = Query(default="single", description="single | period"),
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),  # FIX-S1: auth required
):
    """
    Delete an upload record, its files, and optionally all derived data.

    mode=single  — deletes this upload record + its raw/normalized files only.
    mode=period  — deletes ALL uploads for the same company+period, plus any
                   associated branch_financial rows for that period.

    Returns an audit log of what was deleted (never silent).
    """
    import os
    from app.models.branch import BranchFinancial

    record = db.query(TrialBalanceUpload).filter(
        TrialBalanceUpload.id == upload_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Enforce owner role (Task 6)
    _owner = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == record.company_id,
        Membership.role       == "owner",
        Membership.is_active  == True,  # noqa
    ).first()
    if not _owner:
        raise HTTPException(status_code=403, detail="Only owner can delete")

    company_id = record.company_id
    period     = record.period
    audit: dict = {
        "mode":          mode,
        "upload_id":     upload_id,
        "company_id":    company_id,
        "period":        period,
        "deleted_files": [],
        "deleted_uploads": [],
        "deleted_branch_financials": 0,
    }

    def _rm_files(rec):
        for attr in ("raw_path", "normalized_path"):
            fpath = getattr(rec, attr, None)
            if fpath and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    audit["deleted_files"].append(fpath)
                except OSError as e:
                    logger.warning("Could not delete file %s: %s", fpath, e)

    if mode == "period" and period:
        # Delete ALL uploads for this company+period
        all_recs = db.query(TrialBalanceUpload).filter(
            TrialBalanceUpload.company_id == company_id,
            TrialBalanceUpload.period     == period,
        ).all()
        for rec in all_recs:
            _rm_files(rec)
            audit["deleted_uploads"].append(rec.id)
            # Delete branch_financials linked to this specific upload
            bf_n = db.query(BranchFinancial).filter(
                BranchFinancial.upload_id == rec.id,
            ).delete(synchronize_session=False)
            audit["deleted_branch_financials"] += bf_n
            db.delete(rec)
    else:
        # Single-upload delete — also clean up its branch_financials
        _rm_files(record)
        audit["deleted_uploads"].append(record.id)
        bf_n = db.query(BranchFinancial).filter(
            BranchFinancial.upload_id == upload_id,
        ).delete(synchronize_session=False)
        audit["deleted_branch_financials"] = bf_n
        db.delete(record)

    db.commit()
    logger.info("[UPLOAD DELETE] %s", audit)
    return {"status": "deleted", "audit": audit}


@router.get("/check-period")
def check_period(
    company_id:  str,
    period:      str,
    branch_id:   str     = "",
    db:          Session = Depends(get_db),
    current_user         = Depends(get_current_user),
):
    """
    Check whether a period already has a successful upload for this company.
    Requires authentication and active membership for the company.
    """
    # Enforce membership before exposing any period info
    _mem = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == company_id,
        Membership.is_active  == True,  # noqa
    ).first()
    if not _mem:
        raise HTTPException(status_code=403, detail="Access denied")

    resolved_branch = branch_id.strip() or None

    q = (
        db.query(TrialBalanceUpload)
        .filter(
            TrialBalanceUpload.company_id == company_id,
            TrialBalanceUpload.period     == period,
            TrialBalanceUpload.status     == "ok",
        )
    )
    if resolved_branch is None:
        q = q.filter(TrialBalanceUpload.branch_id.is_(None))
    else:
        q = q.filter(TrialBalanceUpload.branch_id == resolved_branch)

    existing = q.order_by(TrialBalanceUpload.uploaded_at.desc()).first()
    return {
        "exists":    existing is not None,
        "upload_id": existing.id if existing else None,
        "filename":  existing.original_filename if existing else None,
    }
