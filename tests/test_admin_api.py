# tests/test_admin_api.py
"""Tests API admin / onboarding (POST /public/onboarding, GET /admin/*)."""

import os
import pytest
from fastapi.testclient import TestClient

# Mock ADMIN_API_TOKEN pour les tests protégés
os.environ["ADMIN_API_TOKEN"] = "test-admin-token-123"


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": "Bearer test-admin-token-123"}


def test_public_onboarding_creates_tenant(client):
    """POST /api/public/onboarding crée un tenant."""
    r = client.post(
        "/api/public/onboarding",
        json={
            "company_name": "Test Cabinet",
            "email": "contact@test.fr",
            "calendar_provider": "none",
            "calendar_id": "",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "tenant_id" in data
    assert data["tenant_id"] >= 1
    assert "message" in data


def test_admin_tenants_requires_auth(client):
    """GET /api/admin/tenants sans token → 401."""
    r = client.get("/api/admin/tenants")
    assert r.status_code == 401


def test_admin_tenants_with_token(client, admin_headers):
    """GET /api/admin/tenants avec token → 200."""
    r = client.get("/api/admin/tenants", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "tenants" in data
    assert isinstance(data["tenants"], list)


def test_admin_tenant_detail(client, admin_headers):
    """GET /api/admin/tenants/1 → détail avec flags, params, routing."""
    r = client.get("/api/admin/tenants/1", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "tenant_id" in data
    assert "name" in data
    assert "flags" in data
    assert "params" in data
    assert "routing" in data


def test_admin_tenant_not_found(client, admin_headers):
    """GET /api/admin/tenants/999999 → 404."""
    r = client.get("/api/admin/tenants/999999", headers=admin_headers)
    assert r.status_code == 404


def test_admin_patch_flags(client, admin_headers):
    """PATCH /api/admin/tenants/1/flags → ok."""
    r = client.patch(
        "/api/admin/tenants/1/flags",
        headers=admin_headers,
        json={"flags": {"ENABLE_LLM_ASSIST_START": False}},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_patch_params(client, admin_headers):
    """PATCH /api/admin/tenants/1/params → ok."""
    r = client.patch(
        "/api/admin/tenants/1/params",
        headers=admin_headers,
        json={"params": {"calendar_provider": "google", "calendar_id": "test@group.calendar.google.com"}},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_add_routing(client, admin_headers):
    """POST /api/admin/routing → ok."""
    r = client.post(
        "/api/admin/routing",
        headers=admin_headers,
        json={"channel": "vocal", "key": "+33123456789", "tenant_id": 1},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_kpis_weekly(client, admin_headers):
    """GET /api/admin/kpis/weekly → digests."""
    r = client.get(
        "/api/admin/kpis/weekly",
        headers=admin_headers,
        params={"tenant_id": 1, "start": "2026-01-01", "end": "2026-01-08"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "tenant_id" in data
    assert "calls_total" in data
    assert "booking_confirmed" in data


def test_admin_rgpd(client, admin_headers):
    """GET /api/admin/rgpd → consent_rate."""
    r = client.get(
        "/api/admin/rgpd",
        headers=admin_headers,
        params={"tenant_id": 1, "start": "2026-01-01", "end": "2026-01-08"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "consent_obtained" in data
    assert "consent_rate" in data
