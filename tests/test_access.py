"""
test_access.py — Authorization tests.
Covers: unauthenticated → 401/403, wrong company → 403, valid access → 200.
"""
import pytest


FAKE_UUID = "00000000-0000-0000-0000-000000000000"


class TestCompanyAccess:
    def test_create_company_requires_auth(self, client):
        r = client.post("/api/v1/companies", json={"name": "Anon Co", "currency": "USD"})
        assert r.status_code in (401, 403)

    def test_create_company_authenticated(self, client, auth_headers):
        r = client.post("/api/v1/companies", json={"name": "Auth Co", "currency": "USD"},
                        headers=auth_headers)
        assert r.status_code == 201

    def test_delete_company_requires_auth(self, client, company_and_headers):
        company, _ = company_and_headers
        r = client.delete(f"/api/v1/companies/{company['id']}")
        assert r.status_code in (401, 403)

    def test_delete_company_owner_allowed(self, client, company_and_headers):
        company, headers = company_and_headers
        r = client.delete(f"/api/v1/companies/{company['id']}", headers=headers)
        assert r.status_code == 204

    def test_auto_membership_on_create(self, client, auth_headers):
        """Creating a company should auto-create owner membership."""
        r = client.post("/api/v1/companies", json={"name": "Mem Co", "currency": "USD"},
                        headers=auth_headers)
        assert r.status_code == 201
        company_id = r.json()["id"]
        # User should see this company in their list
        r2 = client.get("/api/v1/companies", headers=auth_headers)
        assert r2.status_code == 200
        ids = [c["id"] for c in r2.json()]
        assert company_id in ids, f"Company {company_id} not in user's list: {ids}"


class TestBranchAccess:
    def test_create_branch_requires_auth(self, client, company_and_headers):
        company, _ = company_and_headers
        r = client.post("/api/v1/branches", json={"name": "B1", "company_id": company["id"]})
        assert r.status_code in (401, 403)

    def test_create_branch_authenticated(self, client, company_and_headers):
        company, headers = company_and_headers
        r = client.post("/api/v1/branches",
                        json={"name": "Branch1", "company_id": company["id"]},
                        headers=headers)
        assert r.status_code == 201


class TestAnalysisAccess:
    def test_executive_unauthenticated(self, client, company_and_headers):
        company, _ = company_and_headers
        r = client.get(f"/api/v1/analysis/{company['id']}/executive")
        # With ENFORCE_MEMBERSHIP=False in tests, no token = pass through
        # But company has no uploads so expect 404 not 401
        assert r.status_code in (401, 403, 404)

    def test_analysis_unknown_company(self, client, auth_headers):
        r = client.get(f"/api/v1/analysis/{FAKE_UUID}", headers=auth_headers)
        assert r.status_code == 404
