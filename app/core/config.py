"""
app/core/config.py — Application settings.

All values overrideable via environment variables or .env file.

PRODUCTION CHECKLIST:
  JWT_SECRET_KEY  → generate: python -c "import secrets; print(secrets.token_hex(32))"
  DATABASE_URL    → postgresql://user:password@host:5432/vcfo_db
  PRODUCTION_MODE → true   (blocks startup with insecure defaults)
  ENFORCE_MEMBERSHIP → true
  DEBUG           → false
"""
import secrets
from typing import Optional
from pydantic_settings import BaseSettings


# Stable insecure default — detected and blocked in production mode
_INSECURE_DEFAULT = "vcfo-change-this-secret-in-production"


class Settings(BaseSettings):
    APP_NAME: str = "VCFO - Virtual CFO Platform"
    VERSION:  str = "1.0.0"
    DEBUG:    bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./data/vcfo.db"

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

    class Config:
        env_file = ".env"

    # ── Runtime helpers ───────────────────────────────────────────────────────

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_secure_secret(self) -> bool:
        s = self.JWT_SECRET_KEY
        return bool(s) and s != _INSECURE_DEFAULT and len(s) >= 32

    @property
    def db_label(self) -> str:
        return "sqlite" if self.is_sqlite else "postgresql"


settings = Settings()
