from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-tenant-agenda-slots")


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


def test_available_slots_exact_lookup_returns_slot_id(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    with patch("backend.routes.tenant._get_tenant_detail", return_value={"params": {"calendar_provider": "none"}}), patch(
        "backend.routes.tenant.config.USE_PG_SLOTS",
        False,
    ), patch("backend.routes.tenant.find_slot_id_by_datetime", return_value=321) as slot_mock:
        try:
            response = client.get("/api/tenant/agenda/available-slots?date=2026-03-05&time=10:00")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "slots": [
            {
                "slot_id": 321,
                "date": "2026-03-05",
                "time": "10:00",
                "label": "2026-03-05 à 10:00",
            }
        ],
        "total": 1,
        "slot_id": 321,
        "exact": True,
    }
    slot_mock.assert_called_once_with("2026-03-05", "10:00", tenant_id=12)


def test_available_slots_exact_lookup_returns_empty_when_missing(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    with patch("backend.routes.tenant._get_tenant_detail", return_value={"params": {"calendar_provider": "none"}}), patch(
        "backend.routes.tenant.config.USE_PG_SLOTS",
        False,
    ), patch("backend.routes.tenant.find_slot_id_by_datetime", return_value=None):
        try:
            response = client.get("/api/tenant/agenda/available-slots?date=2026-03-05&time=11:00")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"slots": [], "total": 0, "slot_id": None, "exact": True}
