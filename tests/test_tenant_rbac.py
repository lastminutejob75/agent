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
    assert isinstance(captured["params"]["dashboard_team_notes_json"], list)
    assert captured["params"]["dashboard_team_notes_json"][0]["text"] == "Note équipe"


def test_dashboard_team_note_persists_via_fallback_set_params(client, monkeypatch):
    from backend.tenant_config import get_params

    monkeypatch.setattr("backend.routes.tenant.config.USE_PG_TENANTS", False)
    monkeypatch.setattr(
        "backend.routes.tenant.pg_get_tenant_user_by_id",
        lambda uid: {"user_id": uid, "tenant_id": 1, "role": "member", "email": "m@t.fr"},
    )
    # Force le chemin fallback SQLite pour valider la persistance locale aussi.
    monkeypatch.setattr("backend.routes.tenant.pg_update_tenant_params", lambda tid, params: False)
    token = _client_token(1, 101, "member")
    note = "Note équipe persistée test"
    save = client.patch(
        "/api/tenant/dashboard/team-note",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": note},
    )
    assert save.status_code == 200
    params = get_params(1)
    assert params.get("dashboard_team_note") == note
    assert str(params.get("dashboard_team_note_updated_at") or "").endswith("Z")
    items = params.get("dashboard_team_notes_json") or []
    assert isinstance(items, list)
    assert items and items[0].get("text") == note


def test_dashboard_team_note_keeps_history_on_new_save(client, monkeypatch):
    from backend.tenant_config import get_params

    monkeypatch.setattr("backend.routes.tenant.config.USE_PG_TENANTS", False)
    monkeypatch.setattr(
        "backend.routes.tenant.pg_get_tenant_user_by_id",
        lambda uid: {"user_id": uid, "tenant_id": 1, "role": "member", "email": "m@t.fr"},
    )
    monkeypatch.setattr("backend.routes.tenant.pg_update_tenant_params", lambda tid, params: False)
    token = _client_token(1, 103, "member")
    first = client.patch(
        "/api/tenant/dashboard/team-note",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": "Première note"},
    )
    second = client.patch(
        "/api/tenant/dashboard/team-note",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": "Deuxième note"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    params = get_params(1)
    items = params.get("dashboard_team_notes_json") or []
    assert isinstance(items, list)
    assert len(items) >= 2
    assert items[0].get("text") == "Deuxième note"
    assert any(str(item.get("text") or "") == "Première note" for item in items[1:])


def test_dashboard_team_note_uses_bypass_params_for_history(client, monkeypatch):
    monkeypatch.setattr("backend.routes.tenant.config.USE_PG_TENANTS", True)
    monkeypatch.setattr(
        "backend.routes.tenant.pg_get_tenant_user_by_id",
        lambda uid: {"user_id": uid, "tenant_id": 1, "role": "member", "email": "m@t.fr"},
    )
    monkeypatch.setattr(
        "backend.tenants_pg.pg_load_tenant_params_bypass",
        lambda _tid: {
            "dashboard_team_notes_json": [
                {
                    "id": "old",
                    "text": "Note précédente",
                    "author": "Equipe",
                    "created_at": "2026-06-07T10:00:00Z",
                }
            ]
        },
    )
    monkeypatch.setattr("backend.tenants_pg.pg_get_tenant_params", lambda _tid: ({}, "pg"))
    captured = {}

    def _update_params(_tid, params):
        captured["params"] = params
        return True

    monkeypatch.setattr("backend.routes.tenant.pg_update_tenant_params", _update_params)
    token = _client_token(1, 104, "member")
    res = client.patch(
        "/api/tenant/dashboard/team-note",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": "Nouvelle note"},
    )
    assert res.status_code == 200
    items = (captured.get("params") or {}).get("dashboard_team_notes_json") or []
    assert len(items) >= 2
    assert items[0]["text"] == "Nouvelle note"
    assert any(item.get("text") == "Note précédente" for item in items[1:])


def test_dashboard_team_note_accepts_long_text(client, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.tenant.pg_get_tenant_user_by_id",
        lambda uid: {"user_id": uid, "tenant_id": 1, "role": "member", "email": "m@t.fr"},
    )
    captured = {}

    def _update_params(_tid, params):
        captured["params"] = params
        return True

    monkeypatch.setattr("backend.routes.tenant.pg_update_tenant_params", _update_params)
    token = _client_token(1, 107, "member")
    long_note = "A" * 12000
    res = client.patch(
        "/api/tenant/dashboard/team-note",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": long_note},
    )
    assert res.status_code == 200
    saved = ((captured.get("params") or {}).get("dashboard_team_notes_json") or [{}])[0]
    assert str(saved.get("text") or "") == long_note


def test_dashboard_team_note_returns_500_on_pg_write_failure(client, monkeypatch):
    monkeypatch.setattr("backend.routes.tenant.config.USE_PG_TENANTS", True)
    monkeypatch.setattr(
        "backend.routes.tenant.pg_get_tenant_user_by_id",
        lambda uid: {"user_id": uid, "tenant_id": 1, "role": "member", "email": "m@t.fr"},
    )
    monkeypatch.setattr("backend.routes.tenant.pg_update_tenant_params", lambda tid, params: False)
    token = _client_token(1, 102, "member")
    res = client.patch(
        "/api/tenant/dashboard/team-note",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": "note"},
    )
    assert res.status_code == 500


def test_dashboard_team_note_can_be_edited(client, monkeypatch):
    from backend.tenant_config import get_params

    monkeypatch.setattr("backend.routes.tenant.config.USE_PG_TENANTS", False)
    monkeypatch.setattr(
        "backend.routes.tenant.pg_get_tenant_user_by_id",
        lambda uid: {"user_id": uid, "tenant_id": 1, "role": "member", "email": "m@t.fr"},
    )
    monkeypatch.setattr("backend.routes.tenant.pg_update_tenant_params", lambda tid, params: False)
    token = _client_token(1, 105, "member")
    first = client.patch(
        "/api/tenant/dashboard/team-note",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": "Texte initial"},
    )
    assert first.status_code == 200
    note_id = (first.json().get("item") or {}).get("id")
    assert note_id
    edited = client.patch(
        f"/api/tenant/dashboard/team-note/{note_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": "Texte modifie"},
    )
    assert edited.status_code == 200
    params = get_params(1)
    items = params.get("dashboard_team_notes_json") or []
    assert items and items[0].get("id") == note_id
    assert items[0].get("text") == "Texte modifie"


def test_dashboard_team_note_can_be_deleted(client, monkeypatch):
    from backend.tenant_config import get_params

    monkeypatch.setattr("backend.routes.tenant.config.USE_PG_TENANTS", False)
    monkeypatch.setattr(
        "backend.routes.tenant.pg_get_tenant_user_by_id",
        lambda uid: {"user_id": uid, "tenant_id": 1, "role": "member", "email": "m@t.fr"},
    )
    monkeypatch.setattr("backend.routes.tenant.pg_update_tenant_params", lambda tid, params: False)
    token = _client_token(1, 106, "member")
    one = client.patch(
        "/api/tenant/dashboard/team-note",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": "Note a supprimer"},
    )
    two = client.patch(
        "/api/tenant/dashboard/team-note",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": "Note qui reste"},
    )
    assert one.status_code == 200
    assert two.status_code == 200
    note_id = (one.json().get("item") or {}).get("id")
    assert note_id
    deleted = client.delete(
        f"/api/tenant/dashboard/team-note/{note_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 200
    params = get_params(1)
    items = params.get("dashboard_team_notes_json") or []
    assert all(item.get("id") != note_id for item in items)
