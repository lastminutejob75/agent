from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.test_tenant_rgpd import _make_jwt


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant.detect_patient_duplicate_conflicts")
def test_tenant_duplicate_check_endpoint(mock_detect, mock_get_user, client):
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_detect.return_value = {
        "has_conflict": True,
        "conflicts": [
            {
                "field": "email",
                "phone": "+33611111111",
                "display_name": "Paul Martin",
                "email": "paul@example.com",
            }
        ],
    }

    token = _make_jwt()
    r = client.get(
        "/api/tenant/patients/duplicate-check?email=paul%40example.com",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["has_conflict"] is True
    assert data["conflicts"][0]["field"] == "email"
    mock_detect.assert_called_once()


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant.update_patient_fields")
@patch("backend.routes.tenant.upsert_cabinet_client")
@patch("backend.routes.tenant.get_cabinet_client_by_phone")
@patch("backend.routes.tenant.detect_patient_duplicate_conflicts")
def test_tenant_register_patient_blocks_email_duplicate(
    mock_detect,
    mock_get_profile,
    mock_upsert,
    mock_update_fields,
    mock_get_user,
    client,
):
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_get_profile.return_value = None
    mock_detect.return_value = {
        "has_conflict": True,
        "conflicts": [
            {
                "field": "email",
                "phone": "+33611111111",
                "display_name": "Paul Martin",
                "email": "paul@example.com",
            }
        ],
    }

    token = _make_jwt()
    r = client.post(
        "/api/tenant/patients",
        json={
            "patient_phone": "+33622222222",
            "validated_name": "Nouveau Patient",
            "patient_email": "paul@example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "patient_duplicate"
    mock_upsert.assert_not_called()
    mock_update_fields.assert_not_called()
