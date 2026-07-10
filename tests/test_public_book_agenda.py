"""Tests réservation publique : créneaux agenda confirmés (pas pending)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.routes.public_pages import PublicBookingRequest, _book_real_slot


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


def _payload(**overrides):
    base = {
        "slug": "cabinet-demo-uwi",
        "slotId": "1",
        "slotLabel": "aujourd'hui a 14:00",
        "motif": "Consultation",
        "patientName": "Jean Dupont",
        "patientPhone": "0612345678",
        "slotSource": "sqlite",
        "startIso": "2026-05-31T14:00:00",
        "endIso": "2026-05-31T14:15:00",
    }
    base.update(overrides)
    return PublicBookingRequest(**base)


def test_book_real_slot_uses_google_when_start_iso_and_default_sqlite_source():
    payload = _payload(slotSource="sqlite", slotId="1")
    with patch(
        "backend.routes.public_pages._book_google_iso_slot",
        return_value=(True, None, "evt-123"),
    ) as google_book:
        ok, reason, ge = _book_real_slot(2, payload, booking_code="AB12CD")
    assert ok is True
    assert reason is None
    assert ge == "evt-123"
    google_book.assert_called_once()


def test_book_real_slot_prefers_local_for_pg_source():
    payload = _payload(slotSource="pg", slotId="42", startIso="2026-05-31T14:00:00")
    with patch(
        "backend.routes.public_pages._book_local_slot",
        return_value=(True, None, None),
    ) as local_book, patch(
        "backend.routes.public_pages._book_google_iso_slot",
    ) as google_book:
        ok, reason, ge = _book_real_slot(2, payload)
    assert ok is True
    local_book.assert_called_once()
    google_book.assert_not_called()


def test_public_book_returns_502_when_agenda_booking_fails(client):
    body = {
        "slug": "cabinet-demo-uwi",
        "slotId": "1",
        "slotLabel": "aujourd'hui a 14:00",
        "motif": "Consultation",
        "patientName": "Jean Dupont",
        "patientPhone": "0612345678",
        "slotSource": "google",
        "startIso": "2026-05-31T14:00:00",
        "endIso": "2026-05-31T14:15:00",
    }
    with patch("backend.routes.public_pages._resolve_tenant_id", return_value="2"), patch(
        "backend.routes.public_pages._book_real_slot",
        return_value=(False, "technical", None),
    ), patch(
        "backend.public_bookings_pg.get_public_booking_by_idempotency_key",
        return_value=None,
    ), patch(
        "backend.booking_code.create_unique_booking_code_for_tenant",
        return_value="AB12CD",
    ), patch("backend.rate_limit.check_sliding_window"), patch(
        "backend.routes.public_pages._insert_booking"
    ) as insert, patch(
        "backend.routes.public_pages._dispatch_booking_notifications_for_slug"
    ) as notify:
        r = client.post("/api/public/book", json=body)
    assert r.status_code == 502
    assert "confirmer" in (r.json().get("detail") or "").lower()
    insert.assert_not_called()
    notify.assert_not_called()


def test_public_book_returns_409_when_slot_is_taken(client):
    body = {
        "slug": "cabinet-demo-uwi",
        "slotId": "1",
        "slotLabel": "demain a 14:00",
        "motif": "Consultation",
        "patientName": "Jean Dupont",
        "patientPhone": "0612345678",
        "slotSource": "google",
        "startIso": "2026-05-31T14:00:00",
        "endIso": "2026-05-31T14:15:00",
    }
    with patch("backend.routes.public_pages._resolve_tenant_id", return_value="2"), patch(
        "backend.routes.public_pages._book_real_slot",
        return_value=(False, "slot_taken", None),
    ), patch(
        "backend.public_bookings_pg.get_public_booking_by_idempotency_key",
        return_value=None,
    ), patch(
        "backend.booking_code.create_unique_booking_code_for_tenant",
        return_value="AB12CD",
    ), patch("backend.rate_limit.check_sliding_window"):
        r = client.post("/api/public/book", json=body)
    assert r.status_code == 409


def test_public_book_confirmed_when_agenda_booking_succeeds(client):
    body = {
        "slug": "cabinet-demo-uwi",
        "slotId": "1",
        "slotLabel": "aujourd'hui a 14:00",
        "motif": "Consultation",
        "patientName": "Jean Dupont",
        "patientPhone": "0612345678",
        "slotSource": "google",
        "startIso": "2026-05-31T14:00:00",
        "endIso": "2026-05-31T14:15:00",
    }
    with patch("backend.routes.public_pages._resolve_tenant_id", return_value="2"), patch(
        "backend.routes.public_pages._book_real_slot",
        return_value=(True, None, "evt-999"),
    ), patch(
        "backend.public_bookings_pg.get_public_booking_by_idempotency_key",
        return_value=None,
    ), patch(
        "backend.booking_code.create_unique_booking_code_for_tenant",
        return_value="AB12CD",
    ), patch(
        "backend.routes.public_pages._insert_booking",
        return_value={"id": "conf-1", "booking_code": "AB12CD", "created": True},
    ) as insert, patch("backend.rate_limit.check_sliding_window"):
        r = client.post("/api/public/book", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get("confirmed") is True
    assert data.get("status") == "confirmed"
    assert insert.call_args.kwargs["google_event_id"] == "evt-999"
    assert insert.call_args.kwargs["status"] == "confirmed"


def test_public_book_rejects_demo_slot_before_booking(client):
    body = {
        "slug": "cabinet-demo-uwi",
        "slotId": "s1",
        "slotLabel": "demain a 14:00",
        "motif": "Consultation",
        "patientName": "Jean Dupont",
        "patientPhone": "0612345678",
        "slotSource": "demo",
    }
    with patch("backend.rate_limit.check_sliding_window"), patch(
        "backend.routes.public_pages._book_real_slot"
    ) as book:
        r = client.post("/api/public/book", json=body)
    assert r.status_code == 422
    book.assert_not_called()


def test_public_book_double_submit_returns_existing_without_rebooking(client):
    body = {
        "slug": "cabinet-demo-uwi",
        "slotId": "1",
        "slotLabel": "demain a 14:00",
        "motif": "Consultation",
        "patientName": "Jean Dupont",
        "patientPhone": "0612345678",
        "slotSource": "google",
        "startIso": "2026-05-31T14:00:00",
        "endIso": "2026-05-31T14:15:00",
    }
    existing = {
        "id": "conf-existing",
        "booking_code": "AB12CD",
        "status": "confirmed",
        "slot_label": "demain a 14:00",
    }
    with patch("backend.routes.public_pages._resolve_tenant_id", return_value="2"), patch(
        "backend.public_bookings_pg.get_public_booking_by_idempotency_key",
        return_value=existing,
    ), patch("backend.rate_limit.check_sliding_window"), patch(
        "backend.routes.public_pages._book_real_slot"
    ) as book:
        r = client.post("/api/public/book", json=body)
    assert r.status_code == 200
    assert r.json()["confirmationId"] == "conf-existing"
    assert r.json()["idempotent"] is True
    book.assert_not_called()


def test_public_book_persistence_failure_is_not_silenced(client):
    body = {
        "slug": "cabinet-demo-uwi",
        "slotId": "1",
        "slotLabel": "demain a 14:00",
        "motif": "Consultation",
        "patientName": "Jean Dupont",
        "patientPhone": "0612345678",
        "slotSource": "google",
        "startIso": "2026-05-31T14:00:00",
        "endIso": "2026-05-31T14:15:00",
    }
    with patch("backend.routes.public_pages._resolve_tenant_id", return_value="2"), patch(
        "backend.public_bookings_pg.get_public_booking_by_idempotency_key",
        return_value=None,
    ), patch(
        "backend.booking_code.create_unique_booking_code_for_tenant",
        return_value="AB12CD",
    ), patch(
        "backend.routes.public_pages._book_real_slot",
        return_value=(True, None, "evt-999"),
    ), patch(
        "backend.routes.public_pages._insert_booking",
        side_effect=RuntimeError("db down"),
    ), patch(
        "backend.routes.public_pages._rollback_public_booking_reservation"
    ) as rollback, patch("backend.rate_limit.check_sliding_window"):
        r = client.post("/api/public/book", json=body)
    assert r.status_code == 502
    rollback.assert_called_once_with(2, "evt-999", "AB12CD")


def test_public_book_rate_limit_combines_ip_and_slug():
    from backend.routes.public_pages import _rate_limit_public_book

    class Client:
        host = "203.0.113.9"

    class Req:
        headers = {}
        client = Client()

    keys = []
    with patch(
        "backend.rate_limit.check_sliding_window",
        side_effect=lambda key, **kwargs: keys.append(key),
    ):
        _rate_limit_public_book(Req(), "Cabinet-Demo")
    assert "public_book_ip_slug:203.0.113.9:cabinet-demo" in keys
    assert "public_book_ip:203.0.113.9" in keys
    assert "public_book_slug:cabinet-demo" in keys
