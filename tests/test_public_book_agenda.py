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
    practitioner = {"tenantId": 2, "slug": "cabinet-demo-uwi", "name": "Demo"}
    with patch("backend.routes.public_pages._try_fetch_practitioner", return_value=practitioner), patch(
        "backend.routes.public_pages._book_real_slot",
        return_value=(False, "technical", None),
    ), patch("backend.booking_code.create_unique_booking_code_for_tenant", return_value="AB12CD"), patch(
        "backend.rate_limit.check_sliding_window"
    ):
        r = client.post("/api/public/book", json=body)
    assert r.status_code == 502
    assert "confirmer" in (r.json().get("detail") or "").lower()


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
    practitioner = {"tenantId": 2, "slug": "cabinet-demo-uwi", "name": "Demo"}
    with patch("backend.routes.public_pages._try_fetch_practitioner", return_value=practitioner), patch(
        "backend.routes.public_pages._book_real_slot",
        return_value=(True, None, "evt-999"),
    ), patch("backend.booking_code.create_unique_booking_code_for_tenant", return_value="AB12CD"), patch(
        "backend.routes.public_pages._insert_booking",
        return_value={"id": "conf-1", "booking_code": "AB12CD"},
    ), patch("backend.rate_limit.check_sliding_window"):
        r = client.post("/api/public/book", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get("confirmed") is True
    assert data.get("status") == "confirmed"
