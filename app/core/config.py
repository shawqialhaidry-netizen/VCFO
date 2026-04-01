"""
app/core/config.py — Application settings.

All values overrideable via environment variables or .env file.

``.env`` is loaded from the **repository root** (next to this package’s parent),
so ``DATABASE_URL`` works regardless of PowerShell / process current directory.

PRODUCTION CHECKLIST:
  JWT_SECRET_KEY  → generate: python -c "import secrets; print(secrets.token_hex(32))"
  DATABASE_URL    → postgresql://user:password@host:5432/vcfo_db  (PostgreSQL only — SQLite is not supported)
  PRODUCTION_MODE → true   (blocks startup with insecure defaults)
  ENFORCE_MEMBERSHIP → true
  DEBUG           → false
"""
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py → parents[2] = repository root (contains .env)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"


# Stable insecure default — detected and blocked in production mode
_INSECURE_DEFAULT = "vcfo-change-this-secret-in-production"


class Settings(BaseSettings):
    APP_NAME: str = "VCFO - Virtual CFO Platform"
    VERSION:  str = "1.0.0"
    DEBUG:    bool = False

    # ── Database (PostgreSQL only; SQLite is deprecated and rejected) ────────
    DATABASE_URL: str = Field(
        ...,
        description="SQLAlchemy URL for PostgreSQL only, e.g. postgresql+psycopg2://user:pass@host:5432/dbname",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Authentication ────────────────────────────────────────────────────────
    JWT_SECRET_KEY:              str = _INSECURE_DEFAULT
    # JWT_ALGORITHM removed — hardcoded to HS256 in security.py and deps.py
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60        # 1 hour

    # ── AI / Anthropic ────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: Optional[str] = None   # set in .env — NEVER expose to frontend

    # ── Access control ────────────────────────────────────────────────────────
    ENFORCE_MEMBERSHIP: bool = True

    # ── Production mode ───────────────────────────────────────────────────────
    # When True: startup RAISES if JWT secret is default/empty or DB unreachable.
    # Set PRODUCTION_MODE=true in .env before going live.
    PRODUCTION_MODE: bool = False

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def postgres_only(cls, v: str) -> str:
        if v is None or not str(v).strip():
            raise ValueError(
                "DATABASE_URL is required. Use a PostgreSQL URL, e.g. "
                "postgresql+psycopg2://user:password@127.0.0.1:5432/vcfo"
            )
        s = str(v).strip()
        low = s.lower()
        if low.startswith("sqlite"):
            raise ValueError(
                "SQLite is deprecated and disabled. Set DATABASE_URL to a PostgreSQL URL "
                "(postgresql://... or postgres://...)."
            )
        if not (low.startswith("postgresql") or low.startswith("postgres://")):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL URL (postgresql:// or postgres://)."
            )
        return s

    # ── Runtime helpers ───────────────────────────────────────────────────────

    @property
    def is_secure_secret(self) -> bool:
        s = self.JWT_SECRET_KEY
        return bool(s) and s != _INSECURE_DEFAULT and len(s) >= 32

    @property
    def db_label(self) -> str:
        """Backend is PostgreSQL-only (legacy SQLite removed)."""
        return "postgresql"


settings = Settings()
