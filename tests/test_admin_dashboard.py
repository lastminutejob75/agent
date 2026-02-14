# tests/test_admin_dashboard.py
"""Tests GET /api/admin/tenants/{id}/dashboard."""

import os
import pytest
from fastapi.testclient import TestClient

os.environ["ADMIN_API_TOKEN"] = "test-admin-token-123"


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": "Bearer test-admin-token-123"}


def test_dashboard_tenant_not_found_404(client, admin_headers):
    """GET /api/admin/tenants/999999/dashboard → 404."""
    r = client.get("/api/admin/tenants/999999/dashboard", headers=admin_headers)
    assert r.status_code == 404


def test_dashboard_returns_200_with_empty_data(client, admin_headers):
    """Returns 200 with empty/null data when no events."""
    r = client.get("/api/admin/tenants/1/dashboard", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "tenant_id" in data
    assert "tenant_name" in data
    assert "service_status" in data
    assert "last_call" in data
    assert "last_booking" in data
    assert "counters_7d" in data
    assert data["service_status"]["status"] in ("online", "offline")
    assert data["counters_7d"]["calls_total"] >= 0
    assert data["counters_7d"]["bookings_confirmed"] >= 0
    assert data["counters_7d"]["transfers"] >= 0
    assert data["counters_7d"]["abandons"] >= 0


def test_dashboard_requires_auth(client):
    """Without token → 401."""
    r = client.get("/api/admin/tenants/1/dashboard")
    assert r.status_code == 401


def test_dashboard_structure(client, admin_headers):
    """Response has expected structure."""
    r = client.get("/api/admin/tenants/1/dashboard", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "tenant_id" in data
    assert "tenant_name" in data
    assert data["service_status"]["status"] in ("online", "offline")
    assert "checked_at" in data["service_status"]
    assert isinstance(data["counters_7d"], dict)
    for k in ("calls_total", "bookings_confirmed", "transfers", "abandons"):
        assert k in data["counters_7d"]
        assert isinstance(data["counters_7d"][k], (int, float))
    assert "transfer_reasons" in data
    assert "top_transferred" in data["transfer_reasons"]
    assert "top_prevented" in data["transfer_reasons"]


def test_dashboard_last_call_structure(client, admin_headers):
    """If last_call present, has call_id, outcome, created_at."""
    r = client.get("/api/admin/tenants/1/dashboard", headers=admin_headers)
    data = r.json()
    if data.get("last_call"):
        assert "call_id" in data["last_call"]
        assert "outcome" in data["last_call"]
        assert "created_at" in data["last_call"]
        assert data["last_call"]["outcome"] in ("booking_confirmed", "transferred_human", "user_abandon", "unknown")


def test_dashboard_last_booking_structure(client, admin_headers):
    """If last_booking present, has created_at, name, source."""
    r = client.get("/api/admin/tenants/1/dashboard", headers=admin_headers)
    data = r.json()
    if data.get("last_booking"):
        assert "created_at" in data["last_booking"]
        assert "source" in data["last_booking"]
