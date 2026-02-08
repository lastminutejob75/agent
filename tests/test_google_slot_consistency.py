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
    fake_slots = [
        {"source": "google", "label": "lundi 10h", "start_iso": "2026-02-03T10:00:00", "end_iso": "2026-02-03T10:15:00"},
        {"source": "google", "label": "mardi 14h", "start_iso": "2026-02-04T14:00:00", "end_iso": "2026-02-04T14:15:00"},
        {"source": "google", "label": "mercredi 9h", "start_iso": "2026-02-05T09:00:00", "end_iso": "2026-02-05T09:15:00"},
    ]

    booked = {}

    def _capture_google(session, start_iso, end_iso):
        booked["start"] = start_iso
        booked["end"] = end_iso
        return True

    monkeypatch.setattr(tools_booking, "_book_google_by_iso", _capture_google)

    engine = Engine(session_store=SessionStore(), faq_store=FaqStore(items=[]))
    conv_id = "tc_consistency"
    session = engine.session_store.get_or_create(conv_id)
    session.pending_slots_display = fake_slots
    session.pending_slot_choice = 2
    session.qualif_data.name = "Jean Dupont"
    session.qualif_data.contact = "jean@example.com"

    ok = tools_booking.book_slot_from_session(session, 2)
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
