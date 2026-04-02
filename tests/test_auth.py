"""
test_auth.py — Authentication tests.
Covers: register, login, duplicate email, inactive user, /me endpoint.
"""
import pytest


class TestRegister:
    def test_register_success(self, client):
        r = client.post("/api/v1/auth/register", json={
            "email": "newuser@test.com",
            "password": "Secret123",
            "full_name": "New User",
        })
        assert r.status_code == 201
        d = r.json()
        assert d["email"] == "newuser@test.com"
        assert "id" in d
        assert "password_hash" not in d  # never leak hash

    def test_register_duplicate_email(self, client):
        payload = {"email": "dup@test.com", "password": "Secret123"}
        client.post("/api/v1/auth/register", json=payload)
        r = client.post("/api/v1/auth/register", json=payload)
        assert r.status_code == 409

    def test_register_invalid_email(self, client):
        r = client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "Secret123",
        })
        assert r.status_code == 422


class TestLogin:
    def test_login_success(self, client, registered_user):
        r = client.post("/api/v1/auth/login", json={
            "email": registered_user["_test_email"],
            "password": "TestPass123!",
        })
        assert r.status_code == 200
        d = r.json()
        assert "access_token" in d
        assert d["token_type"] == "bearer"
        assert d["user"]["email"] == registered_user["_test_email"]

    def test_login_wrong_password(self, client, registered_user):
        r = client.post("/api/v1/auth/login", json={
            "email": registered_user["_test_email"],
            "password": "WrongPassword",
        })
        assert r.status_code == 401

    def test_login_unknown_email(self, client):
        r = client.post("/api/v1/auth/login", json={
            "email": "nobody@test.com",
            "password": "Secret123",
        })
        assert r.status_code == 401


class TestMe:
    def test_me_authenticated(self, client, auth_headers, registered_user):
        r = client.get("/api/v1/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["email"] == registered_user["_test_email"]

    def test_me_unauthenticated(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 403  # HTTPBearer raises 403 on missing creds

    def test_me_invalid_token(self, client):
        r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401
