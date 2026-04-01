import logging
import logging.config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.getLogger("sqlalchemy.engine").setLevel(
    logging.DEBUG if settings.DEBUG else logging.WARNING
)
_logger = logging.getLogger("vcfo.startup")

# ── FastAPI app ───────────────────────────────────────────────────────────────
# Disable docs in production — read from environment
import os as _os
_is_production = _os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod")
app = FastAPI(
    title   = settings.APP_NAME,
    version = settings.VERSION,
    docs_url    = None if _is_production else "/docs",
    redoc_url   = None if _is_production else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import companies, health, language, uploads, statements, analysis
from app.api import branches, auth, portfolio, ai as ai_router

app.include_router(health.router,     prefix="/api/v1")
app.include_router(companies.router,  prefix="/api/v1")
app.include_router(language.router,   prefix="/api/v1")
app.include_router(uploads.router,    prefix="/api/v1")
app.include_router(statements.router, prefix="/api/v1")
app.include_router(analysis.router,   prefix="/api/v1")
app.include_router(branches.router,   prefix="/api/v1")
app.include_router(auth.router,       prefix="/api/v1")
app.include_router(portfolio.router,  prefix="/api/v1")
app.include_router(ai_router.router,  prefix="/api/v1")


@app.get("/")
def root():
    return {"message": f"Welcome to {settings.APP_NAME}", "docs": "/docs"}


# ── Startup preflight ─────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    """
    6-step preflight on every startup.
    Steps 1–3 can block startup in PRODUCTION_MODE.
    Steps 4–6 are always informational (never block).
    """

    # ── Step 1: Security ──────────────────────────────────────────────────────
    if not settings.is_secure_secret:
        if settings.PRODUCTION_MODE:
            raise RuntimeError(
                "[BLOCKED] JWT_SECRET_KEY is insecure. "
                "Generate one: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        _logger.warning(
            "[SECURITY] JWT_SECRET_KEY is the default insecure value. "
            "Change it before production."
        )
    else:
        _logger.info("[SECURITY] JWT_SECRET_KEY ✓")

    # ── Step 2: Database connectivity ─────────────────────────────────────────
    from app.core.database import check_db_connection
    db_ok, db_msg = check_db_connection()
    if not db_ok:
        if settings.PRODUCTION_MODE:
            raise RuntimeError(f"[BLOCKED] Cannot connect to database: {db_msg}")
        _logger.error("[DB] Cannot connect: %s", db_msg)
    else:
        _logger.info("[DB] Connected (%s) ✓", settings.db_label)

    # ── Step 3: Create tables ─────────────────────────────────────────────────
    init_db()
    _logger.info("[DB] Tables initialised ✓")

    # ── Step 4: Schema completeness ───────────────────────────────────────────
    _missing = []
    try:
        from sqlalchemy import inspect as _insp
        from app.core.database import engine as _eng
        _i = _insp(_eng)
        _tables = _i.get_table_names()

        _required = {
            "tb_uploads":  ["tb_type"],
            "companies":   ["name_ar"],
            "users":       ["is_superuser"],
            "branches":    ["name_ar"],
        }
        for _tbl, _cols in _required.items():
            if _tbl in _tables:
                _existing = [c["name"] for c in _i.get_columns(_tbl)]
                for _col in _cols:
                    if _col not in _existing:
                        _missing.append(f"{_tbl}.{_col}")

        if _missing:
            _logger.warning(
                "[SCHEMA] Missing columns — run: alembic upgrade head\n"
                "  Missing: %s", ", ".join(_missing)
            )
        else:
            _logger.info("[SCHEMA] All required columns present ✓")
    except Exception as _e:
        _logger.warning("[SCHEMA] Check failed: %s", _e)

    # ── Step 5: Data integrity ────────────────────────────────────────────────
    if db_ok:
        try:
            from sqlalchemy import text as _text
            from app.core.database import SessionLocal as _SL
            _db = _SL()
            try:
                _co = _db.execute(_text("SELECT COUNT(*) FROM companies")).scalar() or 0
                _up = _db.execute(
                    _text("SELECT COUNT(*) FROM tb_uploads WHERE status='ok'")
                ).scalar() or 0
                _logger.info("[DATA] companies=%d  ok_uploads=%d", _co, _up)

                if _co == 0:
                    _logger.warning(
                        "[DATA] No companies found. "
                        "Run: python scripts/bootstrap_admin.py"
                    )
                elif _up == 0:
                    _logger.warning(
                        "[DATA] No successful uploads found. "
                        "Upload a Trial Balance via /upload to enable analysis."
                    )
            finally:
                _db.close()
        except Exception as _e:
            _logger.warning("[DATA] Integrity check failed: %s", _e)

    # ── Step 6: Environment summary ───────────────────────────────────────────
    _logger.info(
        "[ENV] production=%s  db=%s  enforce_membership=%s  debug=%s",
        settings.PRODUCTION_MODE,
        settings.db_label,
        settings.ENFORCE_MEMBERSHIP,
        settings.DEBUG,
    )
    _logger.info("[STARTUP] Application ready.")
