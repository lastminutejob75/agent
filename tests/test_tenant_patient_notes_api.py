"""Tests API notes patient (liste, création, édition, suppression)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.test_tenant_rgpd import _make_jwt


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


@patch("backend.routes.tenant.update_patient_note")
@patch("backend.routes.tenant.get_cabinet_client_by_phone")
@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
def test_tenant_update_patient_note_success(
    mock_get_user,
    mock_get_profile,
    mock_update_note,
    client,
):
    mock_get_user.return_value = {"tenant_id": 2, "email": "test@example.com", "role": "owner"}
    mock_get_profile.return_value = {"phone": "+33612345678", "display_name": "Jean Dupont"}
    mock_update_note.return_value = {
        "id": 11,
        "note_text": "Note modifiée",
        "author": "Praticien",
        "created_at": "2026-06-07T11:00:00Z",
    }

    token = _make_jwt(tenant_id=2)
    r = client.patch(
        "/api/tenant/patients/%2B33612345678/notes/11",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "Note modifiée"},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["item"]["id"] == 11
    assert data["item"]["text"] == "Note modifiée"
    mock_update_note.assert_called_once_with(
        2,
        11,
        note_text="Note modifiée",
        patient_phone="+33612345678",
    )


@patch("backend.routes.tenant.update_patient_note")
@patch("backend.routes.tenant.get_cabinet_client_by_phone")
@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
def test_tenant_update_patient_note_not_found(
    mock_get_user,
    mock_get_profile,
    mock_update_note,
    client,
):
    mock_get_user.return_value = {"tenant_id": 2, "email": "test@example.com", "role": "owner"}
    mock_get_profile.return_value = {"phone": "+33612345678", "display_name": "Jean Dupont"}
    mock_update_note.return_value = {}

    token = _make_jwt(tenant_id=2)
    r = client.patch(
        "/api/tenant/patients/%2B33612345678/notes/999",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "X"},
    )

    assert r.status_code == 404
    assert "Note not found" in r.text

