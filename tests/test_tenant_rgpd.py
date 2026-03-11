"""Tests GET /api/tenant/rgpd (protégé session client)."""

import os
import time
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient


def _make_jwt(tenant_id: int = 1, email: str = "test@example.com"):
    from backend.auth_pg import pg_create_tenant_user, pg_get_tenant_user_by_email

    pg_create_tenant_user(tenant_id, email, role="owner", password="testpass123")
    user = pg_get_tenant_user_by_email(email)
    if user is not None:
        _, user_id, role = user
    else:
        user_id = int(tenant_id) * 1000 + 1
        role = "owner"
    now = int(time.time())
    return jwt.encode(
        {
            "typ": "client_session",
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": role or "owner",
            "iat": now,
            "exp": now + 86400,
        },
        os.environ.get("JWT_SECRET"),
        algorithm="HS256",
    )


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


def test_tenant_rgpd_unauthorized(client):
    """GET /api/tenant/rgpd sans JWT → 401."""
    r = client.get("/api/tenant/rgpd")
    assert r.status_code == 401


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant._get_quota_used_minutes")
@patch("backend.routes.tenant._get_kpis_daily")
def test_tenant_kpis_ok(mock_kpis, mock_quota_minutes, mock_get_user, client):
    """GET /api/tenant/kpis avec JWT → days + trend."""
    mock_quota_minutes.return_value = 42
    mock_kpis.return_value = {
        "days": [
            {"date": "2026-02-01", "calls": 3, "bookings": 1, "transfers": 0},
            {"date": "2026-02-02", "calls": 5, "bookings": 2, "transfers": 1},
        ],
        "current": {"calls": 8, "bookings": 3, "transfers": 1},
        "previous": {"calls": 6, "bookings": 2, "transfers": 1},
        "trend": {"calls_pct": 33, "bookings_pct": 50, "transfers_pct": 0},
    }
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    token = _make_jwt()
    r = client.get("/api/tenant/kpis?days=7", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["days"]) == 2
    assert data["trend"]["calls_pct"] == 33
    assert data["minutes_month"] == 42


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant._get_rgpd_extended")
def test_tenant_rgpd_ok(mock_rgpd, mock_get_user, client):
    """GET /api/tenant/rgpd avec JWT → consent_rate + last_consents."""
    mock_rgpd.return_value = {
        "tenant_id": 1,
        "start": "2026-01-27 00:00:00",
        "end": "2026-02-03 12:00:00",
        "consent_obtained": 5,
        "calls_total": 10,
        "consent_rate": 0.5,
        "last_consents": [
            {"call_id": "call-1", "at": "2026-02-03T10:00:00", "version": "2026-02-12_v1"},
        ],
    }
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    token = _make_jwt()
    r = client.get("/api/tenant/rgpd", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["consent_rate"] == 0.5
    assert data["consent_obtained"] == 5
    assert data["calls_total"] == 10
    assert len(data["last_consents"]) == 1
    assert data["last_consents"][0]["call_id"] == "call-1"


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant._get_tenant_detail")
@patch("backend.routes.tenant._get_call_detail")
@patch("backend.routes.tenant._get_calls_list")
def test_tenant_calls_ok(mock_calls, mock_call_detail, mock_tenant_detail, mock_get_user, client):
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_tenant_detail.return_value = {
        "tenant_id": 1,
        "name": "Cabinet Test",
        "timezone": "Europe/Paris",
        "params": {"assistant_name": "sophie", "timezone": "Europe/Paris"},
    }
    mock_calls.return_value = {
        "items": [
            {
                "call_id": "call_123",
                "started_at": "2026-03-06T10:32:00Z",
                "last_event_at": "2026-03-06T10:34:00Z",
                "result": "transfer",
                "duration_min": 2,
            }
        ]
    }
    mock_call_detail.return_value = {
        "duration_min": 2,
        "events": [{"event": "transferred_human", "meta": {"reason": "medical_urgency"}}],
        "transcript": "Patient: douleurs thoraciques depuis 2h",
    }
    token = _make_jwt()
    r = client.get("/api/tenant/calls?limit=10&days=1", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["calls"][0]["call_id"] == "call_123"
    assert data["calls"][0]["status"] == "TRANSFERRED"
    assert data["calls"][0]["agent_name"] == "Sophie"


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant._get_tenant_detail")
@patch("backend.routes.tenant._get_call_detail")
@patch("backend.routes.tenant._get_calls_list")
def test_tenant_calls_keeps_items_when_call_detail_fails(mock_calls, mock_call_detail, mock_tenant_detail, mock_get_user, client):
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_tenant_detail.return_value = {
        "tenant_id": 1,
        "name": "Cabinet Test",
        "timezone": "Europe/Paris",
        "params": {"assistant_name": "sophie", "timezone": "Europe/Paris"},
    }
    mock_calls.return_value = {
        "items": [
            {
                "call_id": "call_broken",
                "started_at": "2026-03-06T10:32:00Z",
                "last_event_at": "2026-03-06T10:34:00Z",
                "result": "transfer",
                "duration_min": 2,
            }
        ]
    }
    from fastapi import HTTPException

    mock_call_detail.side_effect = HTTPException(404, "Call not found")
    token = _make_jwt()
    r = client.get("/api/tenant/calls?limit=10&days=1", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["calls"][0]["call_id"] == "call_broken"
    assert data["calls"][0]["status"] == "TRANSFERRED"
    assert data["calls"][0]["summary"] == "Transféré à un humain"


@patch("backend.routes.tenant.get_cabinet_client_by_phone", return_value=None)
@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant._get_tenant_detail")
@patch("backend.routes.tenant._get_call_detail")
@patch("backend.routes.tenant._get_calls_list")
def test_tenant_calls_prefers_detail_events_and_exposes_customer_number(mock_calls, mock_call_detail, mock_tenant_detail, mock_get_user, _mock_client_profile, client):
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_tenant_detail.return_value = {
        "tenant_id": 1,
        "name": "Cabinet Test",
        "timezone": "Europe/Paris",
        "params": {"assistant_name": "sophie", "timezone": "Europe/Paris"},
    }
    mock_calls.return_value = {
        "items": [
            {
                "call_id": "call_rdv",
                "started_at": "2026-03-06T10:32:00Z",
                "last_event_at": "2026-03-06T10:34:00Z",
                "result": "other",
                "duration_min": 2,
                "customer_number": "+33612345678",
            }
        ]
    }
    mock_call_detail.return_value = {
        "duration_min": 2,
        "result": "other",
        "customer_number": "+33612345678",
        "events": [{
            "event": "booking_confirmed",
            "meta": {
                "patient_name": "Claire Dupont",
                "motif": "Ordonnance",
                "start_iso": "2026-03-10T14:15:00+01:00",
                "end_iso": "2026-03-10T14:30:00+01:00",
                "slot_label": "Mardi 10 mars à 14h15",
            },
        }],
        "transcript": "Patient: Ordonnance.\n\nAssistant: Mardi 10 mars à 14 heures 15.",
    }
    token = _make_jwt()
    r = client.get("/api/tenant/calls?limit=10&days=1", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["calls"][0]["status"] == "CONFIRMED"
    assert data["calls"][0]["summary"] == "RDV confirmé — Ordonnance."
    assert data["calls"][0]["reason_label"] == "Demande de rendez-vous"
    assert data["calls"][0]["reason_category"] == "agenda"
    assert data["calls"][0]["customer_number"] == "+33612345678"
    assert data["calls"][0]["patient"]["raw_name"] == "Claire Dupont"
    assert data["calls"][0]["patient"]["display_name"] == "Claire Dupont"
    assert data["calls"][0]["booking"]["motif"] == "Ordonnance"
    assert data["calls"][0]["booking"]["start_iso"] == "2026-03-10T14:15:00+01:00"


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant._get_tenant_detail")
@patch("backend.routes.tenant.get_cabinet_client_by_phone")
@patch("backend.routes.tenant.upsert_cabinet_client")
@patch("backend.routes.tenant._get_call_detail")
def test_tenant_call_patient_update_validates_name(mock_call_detail, mock_upsert_profile, mock_get_profile, mock_tenant_detail, mock_get_user, client):
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_tenant_detail.return_value = {
        "tenant_id": 1,
        "name": "Cabinet Test",
        "timezone": "Europe/Paris",
        "params": {"assistant_name": "sophie", "timezone": "Europe/Paris"},
    }
    mock_call_detail.return_value = {
        "call_id": "call_patient",
        "customer_number": "+33612345678",
        "events": [{
            "event": "booking_confirmed",
            "meta": {
                "patient_name": "claire dupon",
                "motif": "Consultation",
                "start_iso": "2026-03-10T09:00:00+01:00",
                "end_iso": "2026-03-10T09:30:00+01:00",
            },
        }],
    }
    mock_get_profile.side_effect = [
        None,
        {
            "phone": "+33612345678",
            "raw_name": "claire dupon",
            "validated_name": "Claire Dupont",
            "display_name": "Claire Dupont",
            "validation_status": "validated",
            "source_call_id": "call_patient",
            "updated_at": "2026-03-06T10:35:00",
        },
    ]
    mock_upsert_profile.return_value = {
        "phone": "+33612345678",
        "raw_name": "claire dupon",
        "validated_name": "Claire Dupont",
        "display_name": "Claire Dupont",
        "validation_status": "validated",
    }

    token = _make_jwt()
    r = client.patch(
        "/api/tenant/calls/call_patient/patient",
        json={"validated_name": "Claire Dupont", "raw_name": "claire dupon"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["patient"]["display_name"] == "Claire Dupont"
    assert data["patient"]["is_validated"] is True
    mock_upsert_profile.assert_called_once()


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant._get_tenant_detail")
@patch("backend.routes.tenant.get_cabinet_client_by_phone")
@patch("backend.routes.tenant.upsert_cabinet_client")
@patch("backend.routes.tenant._get_call_detail")
def test_tenant_call_patient_update_uses_booking_contact_when_customer_number_missing(
    mock_call_detail,
    mock_upsert_profile,
    mock_get_profile,
    mock_tenant_detail,
    mock_get_user,
    client,
):
    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_tenant_detail.return_value = {
        "tenant_id": 1,
        "name": "Cabinet Test",
        "timezone": "Europe/Paris",
        "params": {"assistant_name": "sophie", "timezone": "Europe/Paris"},
    }
    mock_call_detail.return_value = {
        "call_id": "call_patient",
        "customer_number": "",
        "events": [{
            "event": "booking_confirmed",
            "meta": {
                "patient_name": "claire dupon",
                "patient_contact": "06 12 34 56 78",
                "motif": "Consultation",
                "start_iso": "2026-03-10T09:00:00+01:00",
                "end_iso": "2026-03-10T09:30:00+01:00",
            },
        }],
    }
    mock_get_profile.side_effect = [
        None,
        {
            "phone": "+33612345678",
            "raw_name": "claire dupon",
            "validated_name": "Claire Dupont",
            "display_name": "Claire Dupont",
            "validation_status": "validated",
            "source_call_id": "call_patient",
            "updated_at": "2026-03-06T10:35:00",
        },
    ]
    mock_upsert_profile.return_value = {
        "phone": "+33612345678",
        "raw_name": "claire dupon",
        "validated_name": "Claire Dupont",
        "display_name": "Claire Dupont",
        "validation_status": "validated",
    }

    token = _make_jwt()
    r = client.patch(
        "/api/tenant/calls/call_patient/patient",
        json={"validated_name": "Claire Dupont", "raw_name": "claire dupon"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["patient"]["phone"] == "+33612345678"
    mock_upsert_profile.assert_called_once_with(
        1,
        "+33612345678",
        raw_name="claire dupon",
        validated_name="Claire Dupont",
        source_call_id="call_patient",
        last_call_id="call_patient",
        last_booking_start="2026-03-10T09:00:00+01:00",
        last_booking_end="2026-03-10T09:30:00+01:00",
        last_booking_motif="Consultation",
    )


@patch("backend.routes.tenant.get_cabinet_client_by_phone", return_value=None)
@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant.GoogleCalendarService")
@patch("backend.routes.tenant._get_tenant_detail")
def test_tenant_agenda_google_ok(mock_tenant_detail, mock_google_service, mock_get_user, _mock_client_profile, client):
    from datetime import datetime, timedelta

    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_tenant_detail.return_value = {
        "tenant_id": 1,
        "name": "Cabinet Test",
        "timezone": "Europe/Paris",
        "params": {
            "timezone": "Europe/Paris",
            "calendar_provider": "google",
            "calendar_id": "cabinet@test.calendar.google.com",
        },
    }
    start_dt = datetime.utcnow() + timedelta(hours=2)
    end_dt = start_dt + timedelta(minutes=30)
    mock_google_service.return_value.service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "evt_1",
                "summary": "RDV - Claire Fontaine",
                "description": "Patient: Claire Fontaine\nMotif: Consultation",
                "start": {"dateTime": start_dt.isoformat() + "Z"},
                "end": {"dateTime": end_dt.isoformat() + "Z"},
            }
        ]
    }
    token = _make_jwt()
    r = client.get("/api/tenant/agenda", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["slots"][0]["patient"] == "Claire Fontaine"
    assert data["slots"][0]["source"] == "UWI"


@patch(
    "backend.routes.tenant.get_cabinet_client_by_phone",
    return_value={
        "phone": "+33612345678",
        "display_name": "Claire Dupont",
        "validated_name": "Claire Dupont",
        "validation_status": "validated",
    },
)
@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant.GoogleCalendarService")
@patch("backend.routes.tenant._get_tenant_detail")
def test_tenant_agenda_google_prefers_validated_patient_name(mock_tenant_detail, mock_google_service, mock_get_user, _mock_client_profile, client):
    from datetime import datetime, timedelta

    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_tenant_detail.return_value = {
        "tenant_id": 1,
        "name": "Cabinet Test",
        "timezone": "Europe/Paris",
        "params": {
            "timezone": "Europe/Paris",
            "calendar_provider": "google",
            "calendar_id": "cabinet@test.calendar.google.com",
        },
    }
    start_dt = datetime.utcnow() + timedelta(hours=2)
    end_dt = start_dt + timedelta(minutes=30)
    mock_google_service.return_value.service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "evt_1",
                "summary": "RDV - Nom Brut",
                "description": "Patient: Nom Brut\nContact: +33612345678\nMotif: Consultation",
                "start": {"dateTime": start_dt.isoformat() + "Z"},
                "end": {"dateTime": end_dt.isoformat() + "Z"},
            }
        ]
    }
    token = _make_jwt()
    r = client.get("/api/tenant/agenda", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["slots"][0]["patient"] == "Claire Dupont"
    assert data["slots"][0]["patient_phone"] == "+33612345678"


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant.GoogleCalendarService")
@patch("backend.routes.tenant._get_tenant_detail")
def test_tenant_agenda_upcoming_days_includes_future_slots(mock_tenant_detail, mock_google_service, mock_get_user, client):
    from datetime import datetime, timedelta

    mock_get_user.return_value = {"tenant_id": 1, "email": "test@example.com", "role": "owner"}
    mock_tenant_detail.return_value = {
        "tenant_id": 1,
        "name": "Cabinet Test",
        "timezone": "Europe/Paris",
        "params": {
            "timezone": "Europe/Paris",
            "calendar_provider": "google",
            "calendar_id": "cabinet@test.calendar.google.com",
        },
    }
    start_dt = datetime.utcnow() + timedelta(days=2)
    end_dt = start_dt + timedelta(minutes=30)
    mock_google_service.return_value.service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "evt_2",
                "summary": "RDV - Henri",
                "description": "Patient: Henri\nMotif: Ordonnance",
                "start": {"dateTime": start_dt.isoformat() + "Z"},
                "end": {"dateTime": end_dt.isoformat() + "Z"},
            }
        ]
    }
    token = _make_jwt()
    r = client.get("/api/tenant/agenda?upcoming_days=7", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["slots"][0]["patient"] == "Henri"
    assert data["slots"][0]["source"] == "UWI"
