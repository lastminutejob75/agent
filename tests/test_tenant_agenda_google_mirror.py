from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


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


def _google_detail():
    return {
        "tenant_id": 12,
        "name": "Cabinet Test",
        "timezone": "Europe/Paris",
        "params": {
            "timezone": "Europe/Paris",
            "calendar_provider": "google",
            "calendar_id": "cabinet@test.calendar.google.com",
            "mirror_google_bookings_to_internal": True,
        },
    }


def test_tenant_agenda_google_mirror_exposes_local_actions(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    start_dt = datetime.utcnow() + timedelta(hours=2)
    end_dt = start_dt + timedelta(minutes=15)
    with patch("backend.routes.tenant._get_tenant_detail", return_value=_google_detail()), patch(
        "backend.routes.tenant._find_local_appointment_for_google_event",
        return_value={"id": 321, "slot_id": 654},
    ), patch("backend.routes.tenant.get_cabinet_client_by_phone", return_value=None), patch(
        "backend.routes.tenant.GoogleCalendarService"
    ) as mock_google_service:
        mock_google_service.return_value.service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "evt_123",
                    "summary": "RDV - Claire Fontaine",
                    "description": "Patient: Claire Fontaine\nContact: +33612345678\nMotif: Consultation",
                    "start": {"dateTime": start_dt.isoformat() + "Z"},
                    "end": {"dateTime": end_dt.isoformat() + "Z"},
                }
            ]
        }
        try:
            response = client.get("/api/tenant/agenda")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["slots"][0]["event_id"] == "evt_123"
    assert data["slots"][0]["appointment_id"] == 321
    assert data["slots"][0]["slot_id"] == 654
    assert data["slots"][0]["can_cancel"] is True
    assert data["slots"][0]["can_reschedule"] is True


def test_tenant_agenda_cancel_google_mirror_cancels_both(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    with patch("backend.routes.tenant._get_tenant_detail", return_value=_google_detail()), patch(
        "backend.routes.tenant._get_local_appointment_by_id",
        return_value={"id": 321, "slot_id": 654},
    ), patch("backend.routes.tenant.cancel_booking_sqlite", return_value=True) as cancel_local, patch(
        "backend.routes.tenant.GoogleCalendarService"
    ) as mock_google_service:
        mock_google_service.return_value.cancel_appointment.return_value = True
        try:
            response = client.post(
                "/api/tenant/agenda/appointments/321/cancel",
                json={"source": "UWI", "external_event_id": "evt_123"},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["provider"] == "google+local"
    mock_google_service.return_value.cancel_appointment.assert_called_once_with("evt_123")
    cancel_local.assert_called_once_with({"id": 321, "slot_id": 654}, tenant_id=12)


def test_tenant_agenda_reschedule_google_mirror_moves_both(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    old_start = datetime(2026, 3, 12, 9, 0)
    old_end = old_start + timedelta(minutes=15)
    new_start = datetime(2026, 3, 12, 11, 0)
    new_end = new_start + timedelta(minutes=15)
    with patch("backend.routes.tenant._get_tenant_detail", return_value=_google_detail()), patch(
        "backend.routes.tenant._get_local_appointment_by_id",
        return_value={"id": 321, "slot_id": 654},
    ), patch("backend.routes.tenant.get_booking_rules", return_value={"duration_minutes": 15}), patch(
        "backend.routes.tenant._get_slot_window",
        side_effect=[(old_start, old_end), (new_start, new_end)],
    ), patch("backend.routes.tenant.reschedule_booking_atomic", return_value=True) as reschedule_local, patch(
        "backend.routes.tenant.GoogleCalendarService"
    ) as mock_google_service:
        mock_google_service.return_value.reschedule_appointment.return_value = True
        try:
            response = client.post(
                "/api/tenant/agenda/appointments/321/reschedule",
                json={"new_slot_id": 777, "external_event_id": "evt_123"},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["provider"] == "google+local"
    mock_google_service.return_value.reschedule_appointment.assert_called_once_with(
        "evt_123",
        new_start.isoformat(),
        new_end.isoformat(),
    )
    reschedule_local.assert_called_once_with(321, 777, tenant_id=12)
