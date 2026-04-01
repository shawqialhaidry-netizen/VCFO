"""
tests/conftest.py — shared fixtures for VCFO backend tests.
Uses an in-memory SQLite DB so tests never touch real data.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.config import settings
from app.main import app

# ── In-memory test database ───────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables once for the test session."""
    from app.models import company, trial_balance, branch, user, membership  # noqa
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(autouse=True)
def patch_secret(monkeypatch):
    """Ensure JWT secret is set during tests."""
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-secret-key-for-testing-only")
    monkeypatch.setattr(settings, "ENFORCE_MEMBERSHIP", False)


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
