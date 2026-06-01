from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.test_tenant_rgpd import _make_jwt


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant._collect_patient_upcoming_appointment_slots")
@patch("backend.routes.tenant.get_cabinet_client_by_phone")
def test_tenant_patient_appointments_endpoint(
    mock_get_profile,
    mock_collect,
    mock_get_user,
    client,
):
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_get_profile.return_value = {"phone": "+33612345678", "display_name": "Jean Dupont"}
    mock_collect.return_value = [
        {
            "date": "2026-06-01",
            "hour": "10h",
            "start_iso": "2026-06-01T10:00:00+02:00",
            "patient": "Jean Dupont",
            "patient_phone": "+33612345678",
            "motif": "Consultation",
        }
    ]

    token = _make_jwt()
    r = client.get(
        "/api/tenant/patients/%2B33612345678/appointments?upcoming_days=14",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["upcoming_days"] == 14
    assert len(data["slots"]) == 1
    assert data["slots"][0]["patient_phone"] == "+33612345678"
    mock_collect.assert_called_once_with(1, "+33612345678", upcoming_days=14)


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant.get_cabinet_client_by_phone")
def test_tenant_patient_appointments_not_found(mock_get_profile, mock_get_user, client):
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_get_profile.return_value = None

    token = _make_jwt()
    r = client.get(
        "/api/tenant/patients/%2B33699999999/appointments",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 404
