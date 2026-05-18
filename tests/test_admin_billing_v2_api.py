import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {os.environ.get('ADMIN_API_TOKEN')}"}


def test_billing_summary_requires_auth(client):
    res = client.get("/api/admin/billing/summary")
    assert res.status_code == 401


def test_billing_summary_computes_aggregates(client, admin_headers, monkeypatch):
    from backend.routes import admin as admin_routes

    monkeypatch.setattr(
        admin_routes,
        "_get_billing_overview",
        lambda month: {
            "month": month,
            "summary": {},
            "tenants": [
                {
                    "tenant_id": 1,
                    "name": "Cabinet A",
                    "plan_key": "starter",
                    "stripe_status": "active",
                    "mrr_eur": 99,
                    "usage": {"minutes": 420, "cost_usd": 40.0},
                    "quota": {"included": 400, "used": 420},
                },
                {
                    "tenant_id": 2,
                    "name": "Cabinet B",
                    "plan_key": "growth",
                    "stripe_status": "active",
                    "mrr_eur": 149,
                    "usage": {"minutes": 700, "cost_usd": 90.0},
                    "quota": {"included": 800, "used": 700},
                },
            ],
        },
    )
    res = client.get("/api/admin/billing/summary?period=2026-05", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["mrr"] == 248
    assert data["voice_minutes_used"] == 1120.0
    assert data["estimated_revenue"] >= 248
    assert "billing_alerts_count" in data


def test_billing_tenants_filter_quota_high(client, admin_headers, monkeypatch):
    from backend.routes import admin as admin_routes

    monkeypatch.setattr(
        admin_routes,
        "_get_billing_overview",
        lambda month: {
            "month": month,
            "summary": {},
            "tenants": [
                {
                    "tenant_id": 1,
                    "name": "Cabinet Haut",
                    "plan_key": "starter",
                    "stripe_status": "active",
                    "mrr_eur": 99,
                    "usage": {"minutes": 390, "cost_usd": 42.0},
                    "quota": {"included": 400, "used": 390},
                },
                {
                    "tenant_id": 2,
                    "name": "Cabinet Bas",
                    "plan_key": "growth",
                    "stripe_status": "active",
                    "mrr_eur": 149,
                    "usage": {"minutes": 200, "cost_usd": 30.0},
                    "quota": {"included": 800, "used": 200},
                },
            ],
        },
    )
    res = client.get("/api/admin/billing/tenants?filter=quota_high", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["tenant_id"] == 1


def test_billing_push_usage_tenant_calls_helper(client, admin_headers, monkeypatch):
    from backend.routes import admin as admin_routes

    called = {}

    def fake_push(tenant_id, date_utc):
        called["tenant_id"] = tenant_id
        called["date"] = str(date_utc)
        return {"ok": True, "tenant_id": tenant_id, "status": "sent"}

    monkeypatch.setattr(admin_routes, "_push_usage_for_single_tenant", fake_push)
    res = client.post("/api/admin/billing/tenants/12/push-usage?target_date=2026-05-10", headers=admin_headers)
    assert res.status_code == 200
    assert called["tenant_id"] == 12
    assert called["date"] == "2026-05-10"
