"""
P0: Garantir que le slot affiché (index 1/2/3) = slot réservé (pending_slots_display, pas re-fetch).
"""

import pytest

from backend.engine import Engine
from backend.session import SessionStore
from backend.tools_faq import FaqStore
import backend.tools_booking as tools_booking


@pytest.fixture
def engine():
    store = SessionStore()
    faq = FaqStore(items=[])
    return Engine(session_store=store, faq_store=faq)


def test_pending_slots_display_matches_booking(monkeypatch):
    """Choix 2 (mardi 14h) → book_slot_from_session réserve bien le 2e slot (start/end ISO)."""
    from backend.tools_booking import to_canonical_slots

    fake_slots = [
        {"source": "google", "label": "lundi 10h", "start_iso": "2026-02-03T10:00:00", "end_iso": "2026-02-03T10:15:00"},
        {"source": "google", "label": "mardi 14h", "start_iso": "2026-02-04T14:00:00", "end_iso": "2026-02-04T14:15:00"},
        {"source": "google", "label": "mercredi 9h", "start_iso": "2026-02-05T09:00:00", "end_iso": "2026-02-05T09:15:00"},
    ]

    booked = {}

    def _capture_google(session, start_iso, end_iso):
        booked["start"] = start_iso
        booked["end"] = end_iso
        return True, None

    monkeypatch.setattr(tools_booking, "_book_google_by_iso", _capture_google)

    engine = Engine(session_store=SessionStore(), faq_store=FaqStore(items=[]))
    conv_id = "tc_consistency"
    session = engine.session_store.get_or_create(conv_id)
    session.pending_slots = to_canonical_slots(fake_slots)
    session.pending_slot_choice = 2
    session.qualif_data.name = "Jean Dupont"
    session.qualif_data.contact = "jean@example.com"

    ok, _ = tools_booking.book_slot_from_session(session, 2)
    assert ok is True
    assert booked.get("start") == "2026-02-04T14:00:00"
    assert booked.get("end") == "2026-02-04T14:15:00"


def test_serialize_slots_for_session_adds_source():
    """serialize_slots_for_session(slots, source='sqlite') met source sur chaque entrée."""
    from backend.prompts import SlotDisplay
    slots = [
        SlotDisplay(idx=1, label="lundi 10h", slot_id=42, start="2026-02-03T10:00:00", day="lundi", hour=10, label_vocal="lundi à 10h"),
    ]
    out = tools_booking.serialize_slots_for_session(slots, source="sqlite")
    assert len(out) == 1
    assert out[0]["source"] == "sqlite"
    assert out[0]["label"] == "lundi 10h"
    assert out[0]["slot_id"] == 42
    assert out[0]["start_iso"] == "2026-02-03T10:00:00"
    assert out[0]["end_iso"] is not None  # déduit start + 15 min


def test_book_google_by_iso_mirrors_internal_when_enabled(monkeypatch):
    """Si le miroir Google est activé, un booking Google réussi crée aussi un RDV interne UWI."""

    class FakeCalendar:
        def can_propose_slots(self):
            return True

        def book_appointment(self, **kwargs):
            return "evt_google_123"

    class Qualif:
        name = "Jean Dupont"
        contact = "jean@example.com"
        motif = "Consultation"

    class Session:
        tenant_id = 7
        conv_id = "conv-google-mirror"
        qualif_data = Qualif()
        google_event_id = None

    mirrored = {}

    monkeypatch.setattr("backend.calendar_adapter.get_calendar_adapter", lambda session: FakeCalendar())
    monkeypatch.setattr("backend.tenant_config.get_params", lambda tenant_id: {"mirror_google_bookings_to_internal": "true"})
    monkeypatch.setattr(tools_booking, "_ensure_local_slot_id_from_start_iso", lambda start_iso, tenant_id=1: 55)

    def fake_book_local(session, slot_id, source="sqlite"):
        mirrored["slot_id"] = slot_id
        mirrored["source"] = source
        return True

    monkeypatch.setattr(tools_booking, "_book_local_by_slot_id", fake_book_local)

    ok, reason = tools_booking._book_google_by_iso(Session(), "2026-02-04T14:00:00", "2026-02-04T14:15:00")

    assert ok is True
    assert reason is None
    assert mirrored == {"slot_id": 55, "source": "pg" if tools_booking.config.USE_PG_SLOTS else "sqlite"}


def test_book_google_by_iso_mirrors_internal_by_default_for_google_provider(monkeypatch):
    """provider=google sans flag explicite doit quand même créer le miroir UWI par défaut."""

    class FakeCalendar:
        def can_propose_slots(self):
            return True

        def book_appointment(self, **kwargs):
            return "evt_google_default"

    class Qualif:
        name = "Julie Dupont"
        contact = "julie@example.com"
        motif = "Controle"

    class Session:
        tenant_id = 17
        conv_id = "conv-google-default-mirror"
        qualif_data = Qualif()
        google_event_id = None

    mirrored = {}

    monkeypatch.setattr("backend.calendar_adapter.get_calendar_adapter", lambda session: FakeCalendar())
    monkeypatch.setattr("backend.tenant_config.get_params", lambda tenant_id: {"calendar_provider": "google", "calendar_id": "cabinet@test"})
    monkeypatch.setattr(tools_booking, "_ensure_local_slot_id_from_start_iso", lambda start_iso, tenant_id=1: 77)

    def fake_book_local(session, slot_id, source="sqlite"):
        mirrored["slot_id"] = slot_id
        mirrored["source"] = source
        return True

    monkeypatch.setattr(tools_booking, "_book_local_by_slot_id", fake_book_local)

    ok, reason = tools_booking._book_google_by_iso(Session(), "2026-02-06T11:00:00", "2026-02-06T11:15:00")

    assert ok is True
    assert reason is None
    assert mirrored == {"slot_id": 77, "source": "pg" if tools_booking.config.USE_PG_SLOTS else "sqlite"}


def test_book_google_by_iso_does_not_mirror_when_disabled(monkeypatch):
    """Sans flag activé, le booking Google ne crée pas de RDV interne miroir."""

    class FakeCalendar:
        def can_propose_slots(self):
            return True

        def book_appointment(self, **kwargs):
            return "evt_google_456"

    class Qualif:
        name = "Marie Dupont"
        contact = "marie@example.com"
        motif = "Suivi"

    class Session:
        tenant_id = 8
        conv_id = "conv-google-no-mirror"
        qualif_data = Qualif()
        google_event_id = None

    monkeypatch.setattr("backend.calendar_adapter.get_calendar_adapter", lambda session: FakeCalendar())
    monkeypatch.setattr("backend.tenant_config.get_params", lambda tenant_id: {"mirror_google_bookings_to_internal": "false"})

    called = []

    def fake_book_local(*args, **kwargs):
        called.append(True)
        return True

    monkeypatch.setattr(tools_booking, "_book_local_by_slot_id", fake_book_local)

    ok, reason = tools_booking._book_google_by_iso(Session(), "2026-02-05T10:00:00", "2026-02-05T10:15:00")

    assert ok is True
    assert reason is None
    assert called == []
