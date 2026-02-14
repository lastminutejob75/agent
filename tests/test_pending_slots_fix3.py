# tests/test_pending_slots_fix3.py
"""
Anti-régression Fix 3 : pending_slots format canonique unique.
- Replay après perte de session : pending_slots reconstruit → "oui" → booking OK.
- Legacy session : SlotDisplay / pending_slots_display_json → conversion canonique OK.
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.engine import create_engine
from backend.session import Session, QualifData
from backend import tools_booking
from backend.session_store_sqlite import SQLiteSessionStore, _pending_slots_to_jsonable
from backend import config


def test_legacy_session_display_json_converts_to_canonical():
    """
    Legacy session : pending_slots_json ou pending_slots_display_json au format ancien
    (idx, label, slot_id, start, day, hour, label_vocal, source) → to_canonical_slots
    produit des dicts avec id, start, label_vocal, source.
    """
    legacy_slots = [
        {"idx": 1, "label": "Lundi 9h00", "slot_id": 10, "start": "2026-02-10T09:00:00", "day": "lundi", "hour": 9, "label_vocal": "lundi à 9h", "source": "sqlite"},
        {"idx": 2, "label": "Lundi 14h00", "slot_id": 11, "start": "2026-02-10T14:00:00", "day": "lundi", "hour": 14, "label_vocal": "lundi à 14h", "source": "sqlite"},
    ]
    canonical = tools_booking.to_canonical_slots(legacy_slots)
    assert len(canonical) == 2
    for s in canonical:
        assert isinstance(s, dict)
        assert "id" in s or s.get("slot_id") is not None
        assert s.get("start") or s.get("start_iso")
        assert s.get("label_vocal") or s.get("label")
        assert s.get("source") in ("sqlite", "pg", "google")
    assert canonical[0].get("id") == 10 or canonical[0].get("slot_id") == 10
    assert canonical[0].get("label_vocal") == "lundi à 9h"


def test_replay_after_session_loss_pending_slots_canonical_booking_ok():
    """
    Replay après perte de session : session avec pending_slots (canonical) en CONTACT_CONFIRM,
    user dit "oui" → book_slot_from_session utilise pending_slots → pas d'erreur technique.
    """
    from backend.engine import Engine
    from backend.session import SessionStore
    from backend.tools_faq import FaqStore

    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv_id = "test_replay_fix3"

    # Slots au format canonique (comme après reconstruction depuis DB)
    canonical_slots = [
        {"id": 1, "slot_id": 1, "start": "2026-02-10T09:00:00", "start_iso": "2026-02-10T09:00:00", "end": "2026-02-10T09:15:00", "end_iso": "2026-02-10T09:15:00", "label": "Lundi 9h00", "label_vocal": "lundi à 9h", "day": "lundi", "source": "sqlite"},
        {"id": 2, "slot_id": 2, "start": "2026-02-10T14:00:00", "start_iso": "2026-02-10T14:00:00", "end": "2026-02-10T14:15:00", "end_iso": "2026-02-10T14:15:00", "label": "Lundi 14h00", "label_vocal": "lundi à 14h", "day": "lundi", "source": "sqlite"},
    ]

    session = store.get_or_create(conv_id)
    session.state = "CONTACT_CONFIRM"
    session.channel = "web"
    session.pending_slots = canonical_slots
    session.pending_slot_choice = 1
    session.qualif_data = QualifData(name="Test User", motif="Consultation", pref="matin", contact="test@example.com", contact_type="email")
    session.extracted_name = True
    session.extracted_motif = True
    session.extracted_pref = True
    # Pour que "oui" aille au booking (pas au yes_ambiguous disambiguation)
    session.awaiting_confirmation = "CONFIRM_CONTACT"
    session.last_question_asked = "Votre adresse est bien test@example.com ?"

    # Mock booking (module utilisé par l'engine)
    mock_book = pytest.importorskip("unittest.mock").MagicMock(return_value=(True, None))
    with patch("backend.tools_booking.book_slot_from_session", mock_book):
        events = engine.handle_message(conv_id, "oui")

    assert len(events) >= 1
    assert events[0].type == "final"
    assert mock_book.called, "book_slot_from_session should be called on 'oui' in CONTACT_CONFIRM with slot choice"
    assert mock_book.call_args[0][1] == 1  # choice_index_1based
    assert events[0].conv_state == "CONFIRMED"


def test_pending_slots_to_jsonable_accepts_slot_display():
    """_pending_slots_to_jsonable (session_store) accepte SlotDisplay → list de dicts JSON-serializable."""
    from backend.prompts import SlotDisplay

    slots = [
        SlotDisplay(idx=1, label="Lundi 9h", slot_id=1, start="2026-02-10T09:00:00", day="lundi", hour=9, label_vocal="lundi à 9h", source="sqlite"),
    ]
    out = _pending_slots_to_jsonable(slots)
    assert len(out) == 1
    assert isinstance(out[0], dict)
    assert out[0].get("id") == 1 or out[0].get("slot_id") == 1
    assert out[0].get("source") == "sqlite"
    # Sérialisable JSON
    import json
    json.dumps(out)
