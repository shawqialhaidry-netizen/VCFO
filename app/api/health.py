"""
app/api/health.py — System health and status endpoints.

GET /api/v1/health        — Basic liveness check (load balancer ping)
GET /api/v1/health/full   — Detailed system status for ops/monitoring
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, check_db_connection
from app.core.security import get_current_user

router = APIRouter(tags=["health"])


# ── Basic liveness ─────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    """Minimal liveness endpoint — always returns 200 if server is up."""
    return {
        "status":    "ok",
        "app":       settings.APP_NAME,
        "version":   settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Full system status ─────────────────────────────────────────────────────────

@router.get("/health/full")
def health_full(
    db:           Session = Depends(get_db),
    current_user          = Depends(get_current_user),
):
    """
    Detailed system health check — restricted to authenticated users only.
    Returns database state, migration status, and data counts.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    now = datetime.now(timezone.utc).isoformat()

    # ── Database connectivity ──────────────────────────────────────────────────
    db_ok, db_msg = check_db_connection()

    # ── Schema completeness ────────────────────────────────────────────────────
    schema_ok     = False
    missing_cols  = []
    alembic_head  = None

    try:
        from sqlalchemy import inspect as _insp
        from app.core.database import engine as _eng
        insp   = _insp(_eng)
        tables = insp.get_table_names()

        required = {
            "tb_uploads": ["tb_type"],
            "companies":  ["name_ar"],
            "users":      ["is_superuser"],
            "branches":   ["name_ar"],
        }
        for tbl, cols in required.items():
            if tbl in tables:
                existing = [c["name"] for c in insp.get_columns(tbl)]
                for col in cols:
                    if col not in existing:
                        missing_cols.append(f"{tbl}.{col}")

        schema_ok = len(missing_cols) == 0

        # Check Alembic version
        try:
            row = db.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            alembic_head = row[0] if row else None
        except Exception:
            # Alembic table may not exist on SQLite
            alembic_head = "n/a"

    except Exception as exc:
        missing_cols = ["schema check error"]

    # ── Data counts ────────────────────────────────────────────────────────────
    companies_count  = 0
    uploads_count    = 0
    ok_uploads_count = 0
    last_upload_at   = None

    if db_ok:
        try:
            companies_count = db.execute(
                text("SELECT COUNT(*) FROM companies WHERE is_active = true")
            ).scalar() or 0

            uploads_count = db.execute(
                text("SELECT COUNT(*) FROM tb_uploads")
            ).scalar() or 0

            ok_uploads_count = db.execute(
                text("SELECT COUNT(*) FROM tb_uploads WHERE status = 'ok'")
            ).scalar() or 0

            row = db.execute(
                text("SELECT MAX(uploaded_at) FROM tb_uploads WHERE status = 'ok'")
            ).fetchone()
            last_upload_at = str(row[0]) if row and row[0] else None

        except Exception as exc:
            companies_count = -1
            uploads_count   = "error"

    # ── Path validation ────────────────────────────────────────────────────────
    paths_ok      = True
    paths_checked = 0
    paths_missing = []

    if db_ok and ok_uploads_count > 0:
        try:
            import os
            from pathlib import Path as _Path

            rows = db.execute(
                text("SELECT id, normalized_path FROM tb_uploads WHERE status='ok' LIMIT 20")
            ).fetchall()

            for row in rows:
                norm = row[1]
                if not norm:
                    continue
                paths_checked += 1
                # Normalise separators for current OS
                norm_os = norm.replace("\\", os.sep).replace("/", os.sep)
                p = _Path(norm_os)
                if not p.is_absolute():
                    # Try relative to CWD
                    p = _Path.cwd() / norm_os
                if not p.exists():
                    paths_ok = False
                    paths_missing.append(norm[:60])

        except Exception as exc:
            paths_ok = False
            paths_missing = ["check error"]

    # ── Overall status ─────────────────────────────────────────────────────────
    warnings = []
    if not db_ok:
        warnings.append("database unreachable")
    if missing_cols:
        warnings.append(f"schema gaps: {missing_cols} — run: alembic upgrade head")
    if companies_count == 0:
        warnings.append("no active companies — run: python scripts/bootstrap_admin.py")
    if ok_uploads_count == 0:
        warnings.append("no successful uploads — upload a Trial Balance to enable analysis")
    if not paths_ok and paths_missing:
        warnings.append(f"missing files: {paths_missing[:3]}")
    if not settings.is_secure_secret:
        warnings.append("JWT_SECRET_KEY is the insecure default — change before production")

    overall = "ok" if not warnings else ("degraded" if db_ok else "down")

    return {
        "status":          overall,
        "timestamp":       now,
        "app":             settings.APP_NAME,
        "version":         settings.VERSION,
        "environment": {
            "db":                settings.db_label,
            "production_mode":   settings.PRODUCTION_MODE,
            "enforce_membership":settings.ENFORCE_MEMBERSHIP,
            "debug":             settings.DEBUG,
            "secure_secret":     settings.is_secure_secret,
        },
        "database": {
            "connected":         db_ok,
            "message":           db_msg,
            "alembic_version":   alembic_head,
        },
        "schema": {
            "ok":                schema_ok,
            "missing_columns":   missing_cols,
            "migrations_hint":   "alembic upgrade head" if missing_cols else None,
        },
        "data": {
            "companies_count":   companies_count,
            "uploads_total":     uploads_count,
            "uploads_ok":        ok_uploads_count,
            "last_upload_at":    last_upload_at,
        },
        "files": {
            "paths_checked":     paths_checked,
            "paths_ok":          paths_ok,
            "missing_examples":  paths_missing[:3] if paths_missing else [],
        },
        "warnings": warnings,
    }
