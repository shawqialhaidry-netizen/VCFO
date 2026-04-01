"""
app/core/database.py — Database engine, session factory, connectivity check.
"""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

logger = logging.getLogger("vcfo.db")

# ── Engine — PostgreSQL only (SQLite is not supported) ────────────────────────
_kwargs: dict = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
    "pool_size": 5,
    "max_overflow": 10,
    "pool_recycle": 300,
}

engine       = create_engine(settings.DATABASE_URL, **_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> tuple[bool, str]:
    """Test DB connectivity. Returns (ok: bool, message: str)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def init_db() -> None:
    """Create all tables (idempotent — safe on every restart)."""
    from app.models import company, group, trial_balance, branch, user, membership  # noqa: F401
    Base.metadata.create_all(bind=engine)
