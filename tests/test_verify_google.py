from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.google_calendar import GoogleCalendarNotFoundError, GoogleCalendarPermissionError

os.environ.setdefault("JWT_SECRET", "test-secret-verify-google")


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


def _auth_override():
    return {
        "tenant_id": 12,
        "email": "owner@test.fr",
        "role": "owner",
        "sub": "42",
    }


def test_verify_google_permission_returns_reason_permission(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    with patch("backend.routes.tenant._GoogleCalendarAdapter") as mock_adapter:
        mock_adapter.return_value.get_free_slots.side_effect = GoogleCalendarPermissionError(Exception("403"))
        try:
            r = client.post("/api/tenant/agenda/verify-google", json={"calendar_id": "cabinet@test"})
        finally:
            app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["reason"] == "permission"


def test_verify_google_not_found_returns_reason_not_found(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    with patch("backend.routes.tenant._GoogleCalendarAdapter") as mock_adapter:
        mock_adapter.return_value.get_free_slots.side_effect = GoogleCalendarNotFoundError(Exception("404"))
        try:
            r = client.post("/api/tenant/agenda/verify-google", json={"calendar_id": "missing@test"})
        finally:
            app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["reason"] == "not_found"


def test_verify_google_rejects_service_account_email(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    try:
        r = client.post(
            "/api/tenant/agenda/verify-google",
            json={"calendar_id": "uwi-calendar@lastminutejob-uwi.iam.gserviceaccount.com"},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["reason"] == "service_account_email"


def test_verify_google_valid_calendar_returns_ok_true(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    with patch("backend.routes.tenant._GoogleCalendarAdapter") as mock_adapter:
        mock_adapter.return_value.get_free_slots.return_value = [{"start": "2026-02-23T09:00:00", "end": "2026-02-23T09:15:00"}]
        with patch("backend.routes.tenant.pg_update_tenant_params", return_value=True) as mock_update:
            try:
                r = client.post("/api/tenant/agenda/verify-google", json={"calendar_id": "valid@test"})
            finally:
                app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    mock_update.assert_called_once_with(12, {"calendar_provider": "google", "calendar_id": "valid@test"})
