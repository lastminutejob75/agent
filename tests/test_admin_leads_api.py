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


def test_admin_lead_create_manual_success(client, admin_headers, monkeypatch):
    import backend.leads_pg as leads_pg

    monkeypatch.setattr(leads_pg, "upsert_lead", lambda **kwargs: "lead_manual_1")
    monkeypatch.setattr(
        leads_pg,
        "get_lead",
        lambda lead_id: {"id": lead_id, "status": "new", "notes_log": "[]"},
    )
    captured = {}

    def fake_update_lead(lead_id, **kwargs):
        captured["lead_id"] = lead_id
        captured["kwargs"] = kwargs
        return True

    monkeypatch.setattr(leads_pg, "update_lead", fake_update_lead)

    res = client.post(
        "/api/admin/leads",
        headers=admin_headers,
        json={
            "cabinet_name": "Cabinet Demo",
            "contact_name": "Dr Test",
            "email": "lead@example.com",
            "status": "to_contact",
            "calls_per_day": "25-50",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["lead_id"] == "lead_manual_1"
    assert captured["lead_id"] == "lead_manual_1"
    # to_contact est normalisé en new côté backend
    assert captured["kwargs"]["status"] == "new"


def test_admin_leads_list_follow_up_today_flag(client, admin_headers, monkeypatch):
    import backend.leads_pg as leads_pg

    called = {}

    def fake_list_leads(**kwargs):
        called.update(kwargs)
        return {"items": [], "total": 0, "page": 1, "limit": 25, "pipeline": {}}

    monkeypatch.setattr(leads_pg, "list_leads", fake_list_leads)
    res = client.get("/api/admin/leads?follow_up=today", headers=admin_headers)
    assert res.status_code == 200
    assert called.get("follow_up_today") is True
