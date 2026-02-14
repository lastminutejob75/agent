# tests/test_fix7_single_final.py
"""
Fix 7 : un seul Event("final") par tour en vocal.
- Test A : pas de double final (handlers vocal).
- Test B : WAIT_CONFIRM list+help → 1 final dont le texte contient liste ET instruction.
"""

import pytest
from unittest.mock import patch
from backend.engine import create_engine
from backend.session import SessionStore
from backend.session import Session, QualifData
from backend import tools_booking, prompts


def _count_finals(events):
    return sum(1 for e in events if getattr(e, "type", None) == "final")


def test_vocal_wait_confirm_no_double_final():
    """
    En vocal, après proposition de créneaux (WAIT_CONFIRM), réponse sans choix clair
    (ex: "oui" ou bruit) → un seul Event final.
    """
    from backend.engine import Engine
    from backend.tools_faq import FaqStore

    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv_id = "test_fix7_single_conv"

    with patch.object(tools_booking, "get_slots_for_display") as mock_slots:
        mock_slots.return_value = [
            prompts.SlotDisplay(1, "Lundi 9h", 1, "2026-02-10T09:00:00", "lundi", 9, "lundi 9h", "sqlite"),
            prompts.SlotDisplay(2, "Lundi 14h", 2, "2026-02-10T14:00:00", "lundi", 14, "lundi 14h", "sqlite"),
            prompts.SlotDisplay(3, "Mardi 10h", 3, "2026-02-11T10:00:00", "mardi", 10, "mardi 10h", "sqlite"),
        ]
        engine.handle_message(conv_id, "je veux un rdv")
        engine.handle_message(conv_id, "Alice")
        engine.handle_message(conv_id, "consultation")
        engine.handle_message(conv_id, "matin")
        # Préférence confirmée → _propose_slots (WAIT_CONFIRM, 1 slot vocal)
        events = engine.handle_message(conv_id, "oui")
    assert _count_finals(events) == 1, "vocal: un seul Event final après proposition créneaux"


def test_vocal_wait_confirm_list_plus_help_single_final():
    """
    WAIT_CONFIRM : préface déjà envoyée, liste pas encore.
    User dit quelque chose qui n'est pas un choix (ex. "euh" ou "oui" ambigu).
    Attendu : 1 seul final, texte = liste + instruction (ex. "Dites 1, 2 ou 3.").
    """
    from backend.engine import Engine
    from backend.tools_faq import FaqStore

    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv_id = "test_fix7_list_help"

    canonical = [
        {"id": 1, "start": "2026-02-10T09:00:00", "label": "Lundi 9h", "label_vocal": "lundi à 9h", "source": "sqlite", "day": "lundi"},
        {"id": 2, "start": "2026-02-10T14:00:00", "label": "Lundi 14h", "label_vocal": "lundi à 14h", "source": "sqlite", "day": "lundi"},
        {"id": 3, "start": "2026-02-11T10:00:00", "label": "Mardi 10h", "label_vocal": "mardi à 10h", "source": "sqlite", "day": "mardi"},
    ]
    session = store.get_or_create(conv_id)
    session.state = "WAIT_CONFIRM"
    session.channel = "vocal"
    session.pending_slots = canonical
    session.slots_preface_sent = True
    session.slots_list_sent = False
    session.qualif_data = QualifData(name="Test", motif="Consultation", pref="matin", contact=None, contact_type=None)

    events = engine.handle_message(conv_id, "euh")
    assert _count_finals(events) == 1
    text = (events[0].text or "").strip().lower()
    assert "un" in text and "deux" in text and "trois" in text
    help_phrase = "1, 2 ou 3" in text or "un, deux ou trois" in text or "dites" in text
    assert help_phrase, "le message doit contenir la liste ET l'instruction (help)"


def test_safe_reply_vocal_collapse_multiple_finals():
    """
    Si un handler renvoie par erreur 2 finals, safe_reply (vocal) ne garde que le premier.
    """
    from backend.engine import safe_reply, Event

    session = Session(conv_id="test_safe")
    session.channel = "vocal"
    session.state = "WAIT_CONFIRM"
    two_events = [
        Event("final", "Premier message", conv_state=session.state),
        Event("final", "Second message", conv_state=session.state),
    ]
    out = safe_reply(two_events, session)
    assert len(out) == 1
    assert out[0].text == "Premier message"
