# tests/test_admin_cockpit_dashboard.py
"""Tests GET /api/admin/dashboard/* (cockpit agrégé)."""

import os
from datetime import datetime, timezone

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


def test_cockpit_summary_requires_auth(client):
    r = client.get("/api/admin/dashboard/summary")
    assert r.status_code == 401


def test_cockpit_new_leads_requires_auth(client):
    r = client.get("/api/admin/dashboard/new-leads")
    assert r.status_code == 401


def test_cockpit_summary_200_structure(client, admin_headers):
    r = client.get("/api/admin/dashboard/summary?period=7d", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("period") == "7d"
    assert "kpis" in data
    assert "leads" in data
    assert data["leads"].get("period") == "7d"
    for k in (
        "new_leads_count",
        "to_qualify_today_count",
        "latest",
    ):
        assert k in data["leads"]
    assert isinstance(data["leads"]["latest"], list)
    assert "hints" in data
    assert "tenant_totals_hint" in data


def test_cockpit_summary_invalid_period_normalized(client, admin_headers):
    r = client.get("/api/admin/dashboard/summary?period=not-real", headers=admin_headers)
    assert r.status_code == 200
    assert r.json().get("period") == "30d"


def test_cockpit_new_leads_period_echo(client, admin_headers):
    r = client.get("/api/admin/dashboard/new-leads?period=month", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body.get("period") == "month"
    assert "new_leads_count" in body
    assert "latest" in body


def test_cockpit_action_items_200(client, admin_headers):
    r = client.get("/api/admin/dashboard/action-items", headers=admin_headers)
    assert r.status_code == 200
    assert isinstance(r.json().get("items"), list)


def test_cockpit_action_items_critical_only_severities(client, admin_headers):
    r = client.get("/api/admin/dashboard/action-items?severity=critical", headers=admin_headers)
    assert r.status_code == 200
    items = r.json().get("items") or []
    assert all(it.get("severity") == "critical" for it in items)


def test_cockpit_watchlist_200(client, admin_headers):
    r = client.get("/api/admin/dashboard/tenant-watchlist?period=30d", headers=admin_headers)
    assert r.status_code == 200
    assert isinstance(r.json().get("items"), list)


def test_dash_leads_cutoff_shapes():
    from backend.dashboard_cockpit import dash_leads_cutoff_utc

    now = datetime.now(timezone.utc)
    c_month = dash_leads_cutoff_utc("month")
    assert c_month.day == 1
    assert c_month.tzinfo == timezone.utc
    assert c_month <= now

    c24 = dash_leads_cutoff_utc("24h")
    secs = (now - c24).total_seconds()
    assert 23 * 3600 <= secs <= 25 * 3600
