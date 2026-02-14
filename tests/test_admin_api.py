# tests/test_admin_api.py
"""Tests API admin / onboarding (POST /public/onboarding, GET /admin/*)."""

import os
from unittest.mock import patch

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


def test_admin_technical_status(client, admin_headers):
    """GET /api/admin/tenants/1/technical-status → statut technique."""
    r = client.get("/api/admin/tenants/1/technical-status", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["tenant_id"] == 1
    assert "did" in data
    assert data["routing_status"] in ("active", "not_configured")
    assert data["calendar_status"] in ("connected", "incomplete", "not_configured")
    assert data["service_agent"] in ("online", "offline")
    assert "last_event_ago" in data


def test_admin_technical_status_404(client, admin_headers):
    """GET /api/admin/tenants/999999/technical-status → 404."""
    r = client.get("/api/admin/tenants/999999/technical-status", headers=admin_headers)
    assert r.status_code == 404


def test_admin_transfer_reasons(client, admin_headers):
    """GET /api/admin/tenants/1/transfer-reasons → top_transferred, top_prevented."""
    r = client.get("/api/admin/tenants/1/transfer-reasons", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "top_transferred" in data
    assert "top_prevented" in data
    assert "days" in data
    assert isinstance(data["top_transferred"], list)
    assert isinstance(data["top_prevented"], list)
    for item in data["top_transferred"]:
        assert "reason" in item
        assert "count" in item


def test_admin_transfer_reasons_404(client, admin_headers):
    """GET /api/admin/tenants/999999/transfer-reasons → 404."""
    r = client.get("/api/admin/tenants/999999/transfer-reasons", headers=admin_headers)
    assert r.status_code == 404


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_creates_row(mock_add, client, admin_headers):
    """POST /api/admin/tenants/1/users → crée tenant_user."""
    mock_add.return_value = {
        "ok": True,
        "tenant_id": 1,
        "email": "contact@client.com",
        "role": "owner",
        "created": True,
    }
    r = client.post(
        "/api/admin/tenants/1/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["tenant_id"] == 1
    assert data["email"] == "contact@client.com"
    assert data["role"] == "owner"
    assert data["created"] is True


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_idempotent_same_tenant(mock_add, client, admin_headers):
    """POST /api/admin/tenants/1/users avec email déjà sur ce tenant → 200 (no-op)."""
    mock_add.return_value = {
        "ok": True,
        "tenant_id": 1,
        "email": "contact@client.com",
        "role": "owner",
        "created": False,
    }
    r = client.post(
        "/api/admin/tenants/1/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 200
    assert r.json()["created"] is False


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_email_conflict_other_tenant_409(mock_add, client, admin_headers):
    """POST /api/admin/tenants/2/users avec email déjà sur tenant 1 → 409."""
    mock_add.side_effect = ValueError("Email déjà associé à un autre tenant")
    r = client.post(
        "/api/admin/tenants/2/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 409


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_creates_row(mock_add, client, admin_headers):
    """POST /api/admin/tenants/1/users → crée tenant_user."""
    mock_add.return_value = {
        "ok": True,
        "tenant_id": 1,
        "email": "contact@client.com",
        "role": "owner",
        "created": True,
    }
    r = client.post(
        "/api/admin/tenants/1/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["tenant_id"] == 1
    assert data["email"] == "contact@client.com"
    assert data["role"] == "owner"
    assert data["created"] is True
    mock_add.assert_called_once_with(1, "contact@client.com", "owner")


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_idempotent_same_tenant(mock_add, client, admin_headers):
    """POST /api/admin/tenants/1/users avec email déjà sur ce tenant → 200, created=False."""
    mock_add.return_value = {
        "ok": True,
        "tenant_id": 1,
        "email": "contact@client.com",
        "role": "owner",
        "created": False,
    }
    r = client.post(
        "/api/admin/tenants/1/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] is False


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_email_conflict_other_tenant_409(mock_add, client, admin_headers):
    """POST /api/admin/tenants/2/users avec email sur tenant 1 → 409."""
    mock_add.side_effect = ValueError("Email déjà associé à un autre tenant")
    r = client.post(
        "/api/admin/tenants/2/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 409
