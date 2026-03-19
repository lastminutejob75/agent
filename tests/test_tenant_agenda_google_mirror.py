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


def _handoff_item():
    return {
        "id": 11,
        "tenant_id": 12,
        "call_id": "call_handoff",
        "channel": "vocal",
        "reason": "explicit_human_request",
        "target": "assistant",
        "mode": "callback_only",
        "priority": "normal",
        "status": "callback_created",
        "patient_phone": "+33612345678",
        "raw_name": "Claire",
        "validated_name": "",
        "display_name": "Claire",
        "summary": "Le patient souhaite parler à un humain.",
        "transcript_excerpt": "Patient: Je veux parler à quelqu'un",
        "booking_start_iso": "",
        "booking_end_iso": "",
        "booking_motif": "",
        "notes": "",
        "created_at": "2026-03-12T08:00:00Z",
        "updated_at": "2026-03-12T08:00:00Z",
        "processed_at": "",
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


def test_google_mirror_enabled_by_default_when_provider_google_and_flag_missing(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    start_dt = datetime.utcnow() + timedelta(hours=2)
    end_dt = start_dt + timedelta(minutes=15)
    detail = _google_detail()
    detail["params"] = {
        "timezone": "Europe/Paris",
        "calendar_provider": "google",
        "calendar_id": "cabinet@test.calendar.google.com",
    }
    with patch("backend.routes.tenant._get_tenant_detail", return_value=detail), patch(
        "backend.routes.tenant._find_local_appointment_for_google_event",
        return_value={"id": 654, "slot_id": 987},
    ), patch("backend.routes.tenant.get_cabinet_client_by_phone", return_value=None), patch(
        "backend.routes.tenant.GoogleCalendarService"
    ) as mock_google_service:
        mock_google_service.return_value.service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "evt_default",
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
    assert data["slots"][0]["appointment_id"] == 654
    assert data["slots"][0]["slot_id"] == 987
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


def test_tenant_handoffs_list_and_patch(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    item = _handoff_item()
    with patch("backend.routes.tenant.list_handoffs", return_value=[item]) as mock_list, patch(
        "backend.routes.tenant.update_handoff_status",
        return_value={**item, "status": "processed", "processed_at": "2026-03-12T09:00:00Z"},
    ) as mock_update:
        try:
            response = client.get("/api/tenant/handoffs?limit=10")
            patched = client.patch("/api/tenant/handoffs/11", json={"status": "processed", "notes": "Rappel fait"})
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["call_id"] == "call_handoff"
    mock_list.assert_called_once_with(12, status=None, target=None, limit=10)

    assert patched.status_code == 200
    assert patched.json()["ok"] is True
    assert patched.json()["item"]["status"] == "processed"
    mock_update.assert_called_once_with(12, 11, status="processed", notes="Rappel fait")


def test_tenant_handoffs_support_open_filter_and_notes_only_patch(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    item = _handoff_item()
    with patch("backend.routes.tenant.list_handoffs", return_value=[item]) as mock_list, patch(
        "backend.routes.tenant.update_handoff_status",
        return_value={**item, "notes": "À rappeler après 17h"},
    ) as mock_update:
        try:
            response = client.get("/api/tenant/handoffs?status=open&target=assistant&limit=5")
            patched = client.patch("/api/tenant/handoffs/11", json={"notes": "À rappeler après 17h"})
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_list.assert_called_once_with(12, status="open", target="assistant", limit=5)

    assert patched.status_code == 200
    assert patched.json()["item"]["notes"] == "À rappeler après 17h"
    mock_update.assert_called_once_with(12, 11, status=None, notes="À rappeler après 17h")


def test_tenant_handoff_patch_notes_only(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    item = _handoff_item()
    with patch(
        "backend.routes.tenant.update_handoff_status",
        return_value={**item, "notes": "Patient à rappeler après 17h"},
    ) as mock_update:
        try:
            patched = client.patch("/api/tenant/handoffs/11", json={"notes": "Patient à rappeler après 17h"})
        finally:
            app.dependency_overrides.clear()

    assert patched.status_code == 200
    assert patched.json()["ok"] is True
    assert patched.json()["item"]["notes"] == "Patient à rappeler après 17h"
    mock_update.assert_called_once_with(12, 11, status=None, notes="Patient à rappeler après 17h")
