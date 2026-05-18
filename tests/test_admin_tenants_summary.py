# tests/test_admin_tenants_summary.py
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ADMIN_API_TOKEN", "test-admin-token-pytest")


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {os.environ.get('ADMIN_API_TOKEN')}"}


def test_tenants_summary_requires_auth(client):
    r = client.get("/api/admin/tenants/summary")
    assert r.status_code == 401


def test_tenants_summary_200_structure(client, admin_headers):
    r = client.get("/api/admin/tenants/summary?period=14", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("period_days") == 14
    assert "active_tenants_count" in data
    assert "onboarding_tenants_count" in data
    assert "alerts_count" in data
    assert "alert_tenant_ids" in data
    assert isinstance(data["alert_tenant_ids"], list)
    assert "total_voice_minutes_current_period" in data


def test_tenants_summary_route_not_shadowed(client, admin_headers):
    """`/admin/tenants/summary` doit rester résolu avant /admin/tenants/{id}."""
    r = client.get("/api/admin/tenants/summary", headers=admin_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)
