"""Tests RBAC owner vs member sur routes tenant sensibles."""
import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-tenant-rbac-32chars-min")


def _client_token(tenant_id: int, user_id: int, role: str) -> str:
    secret = os.environ["JWT_SECRET"]
    now = int(time.time())
    payload = {
        "typ": "client_session",
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


def test_billing_summary_forbidden_for_member(client, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.tenant.pg_get_tenant_user_by_id",
        lambda uid: {"user_id": uid, "tenant_id": 1, "role": "member", "email": "m@t.fr"},
    )
    token = _client_token(1, 99, "member")
    r = client.get(
        "/api/tenant/billing/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_billing_summary_allowed_for_owner(client, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.tenant.pg_get_tenant_user_by_id",
        lambda uid: {"user_id": uid, "tenant_id": 1, "role": "owner", "email": "o@t.fr"},
    )
    monkeypatch.setattr(
        "backend.routes.tenant.get_tenant_billing",
        lambda tid: {"billing_status": "active", "plan_key": "growth"},
    )
    monkeypatch.setattr(
        "backend.routes.tenant._get_tenant_me_detail",
        lambda tid: {"tenant_id": tid, "name": "Cabinet", "params": {}},
    )
    token = _client_token(1, 1, "owner")
    r = client.get(
        "/api/tenant/billing/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


def test_dashboard_team_note_allowed_for_member(client, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.tenant.pg_get_tenant_user_by_id",
        lambda uid: {"user_id": uid, "tenant_id": 1, "role": "member", "email": "m@t.fr"},
    )
    captured = {}

    def _update_params(tid, params):
        captured["tenant_id"] = tid
        captured["params"] = params
        return True

    monkeypatch.setattr("backend.routes.tenant.pg_update_tenant_params", _update_params)
    token = _client_token(1, 99, "member")
    r = client.patch(
        "/api/tenant/dashboard/team-note",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": "Note équipe"},
    )
    assert r.status_code == 200
    assert captured["tenant_id"] == 1
    assert captured["params"]["dashboard_team_note"] == "Note équipe"
    assert captured["params"]["dashboard_team_note_updated_at"].endswith("Z")
