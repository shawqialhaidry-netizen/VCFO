"""
tests/conftest.py — shared fixtures for VCFO backend tests.

PostgreSQL only (same as the application). SQLite is not supported.

Connection resolution order:
  1) os.environ["TEST_DATABASE_URL"] (export or CI)
  2) Optional repo-root ``.env.test`` (not committed; use for disposable test DB)
  3) settings.DATABASE_URL

The engine is created lazily on first use so ``TEST_DATABASE_URL`` / ``.env.test``
are visible even when set after ``settings`` was imported.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENV_TEST = _REPO_ROOT / ".env.test"
try:
    from dotenv import load_dotenv

    if _ENV_TEST.is_file():
        load_dotenv(_ENV_TEST, override=False)
except ImportError:
    pass

_engine_kwargs = {
    "pool_pre_ping": True,
    "pool_size": 5,
    "max_overflow": 10,
    "pool_recycle": 300,
}

_engine_test = None
_testing_sessionmaker = None


def _resolve_test_database_url() -> str:
    return (os.environ.get("TEST_DATABASE_URL") or settings.DATABASE_URL).strip()


def get_engine_test():
    """
    Session-scoped test engine. Prefer this over a module-level engine so
    ``TEST_DATABASE_URL`` and ``.env.test`` are honored.
    """
    global _engine_test, _testing_sessionmaker
    if _engine_test is None:
        url = _resolve_test_database_url()
        _engine_test = create_engine(url, **_engine_kwargs)
        _testing_sessionmaker = sessionmaker(
            autocommit=False, autoflush=False, bind=_engine_test
        )
    return _engine_test


def get_testing_sessionmaker():
    get_engine_test()
    return _testing_sessionmaker


def override_get_db():
    SessionLocal = get_testing_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def setup_test_db():
    """Create all tables once for the test session (PostgreSQL)."""
    from app.models import company, trial_balance, branch, user, membership  # noqa
    import app.models.group  # noqa: F401 — registers groups / group_memberships
    engine = get_engine_test()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def patch_secret(monkeypatch):
    """Ensure JWT secret is set during tests."""
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-secret-key-for-testing-only")
    monkeypatch.setattr(settings, "ENFORCE_MEMBERSHIP", False)


@pytest.fixture()
def db_session(setup_test_db):
    """Raw SQLAlchemy session for unit tests (same engine as TestClient)."""
    SessionLocal = get_testing_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(setup_test_db):
    """Test client with DB override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def registered_user(client):
    """Create and return a registered test user."""
    r = client.post("/api/v1/auth/register", json={
        "email": "test@vcfo.com",
        "password": "TestPass123!",
        "full_name": "Test User",
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def auth_headers(client, registered_user):
    """Return Authorization headers for an authenticated user."""
    r = client.post("/api/v1/auth/login", json={
        "email": "test@vcfo.com",
        "password": "TestPass123!",
    })
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def company_and_headers(client, auth_headers):
    """Create a company and return (company_dict, auth_headers)."""
    r = client.post("/api/v1/companies", json={
        "name": "Test Co",
        "currency": "USD",
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json(), auth_headers
