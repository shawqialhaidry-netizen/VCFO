"""
test_api_contracts.py — API contract tests.
Verifies response shapes of critical endpoints.
"""
import pytest


class TestAuthContracts:
    def test_register_response_shape(self, client):
        r = client.post("/api/v1/auth/register", json={
            "email": "contract@test.com",
            "password": "Pass123!",
        })
        assert r.status_code == 201
        d = r.json()
        required = {"id", "email", "is_active", "is_superuser"}
        missing = required - set(d.keys())
        assert not missing, f"Register response missing fields: {missing}"
        assert "password_hash" not in d

    def test_login_response_shape(self, client):
        client.post("/api/v1/auth/register", json={"email": "ct2@test.com", "password": "Pass123!"})
        r = client.post("/api/v1/auth/login", json={"email": "ct2@test.com", "password": "Pass123!"})
        assert r.status_code == 200
        d = r.json()
        assert "access_token" in d
        assert "token_type" in d
        assert "user" in d
        assert d["token_type"] == "bearer"


class TestCompanyContracts:
    def test_create_company_response_shape(self, client, auth_headers):
        r = client.post("/api/v1/companies", json={"name": "ContractCo", "currency": "USD"},
                        headers=auth_headers)
        assert r.status_code == 201
        d = r.json()
        for field in ("id", "name", "currency", "is_active", "created_at"):
            assert field in d, f"Company response missing: {field}"

    def test_list_companies_returns_list(self, client, auth_headers):
        r = client.get("/api/v1/companies", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestHealthEndpoint:
    def test_health_ok(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"
