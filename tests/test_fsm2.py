# tests/test_fsm2.py — P2.1 FSM explicite (states couverts, QUALIF_NAME, WAIT_CONFIRM)

import os
import uuid
import pytest
from unittest.mock import patch

from backend.engine import create_engine
from backend import prompts
from backend.fsm2 import States, dispatch_handle, InputEvent, InputKind, is_fsm2_handled
from backend.fsm2.dispatcher import states_covered


def _fake_slots_vendredi(*args, **kwargs):
    """Slots avec vendredi 14h pour test early commit par jour+heure. 2026-02-06 = vendredi."""
    return [
        prompts.SlotDisplay(idx=1, label="Vendredi 06/02 - 14:00", slot_id=1, start="2026-02-06T14:00:00", day="vendredi", hour=14),
        prompts.SlotDisplay(idx=2, label="Lundi 09/02 - 09:00", slot_id=2, start="2026-02-09T09:00:00", day="lundi", hour=9),
        prompts.SlotDisplay(idx=3, label="Mardi 10/02 - 16:00", slot_id=3, start="2026-02-10T16:00:00", day="mardi", hour=16),
    ]


def test_fsm2_states_covered():
    """Chaque état supporté par FSM2 (phase 1) a un handler dans le dispatcher."""
    covered = states_covered()
    assert States.QUALIF_NAME in covered
    assert States.WAIT_CONFIRM in covered
    assert is_fsm2_handled(States.QUALIF_NAME.value)
    assert is_fsm2_handled(States.WAIT_CONFIRM.value)
    assert not is_fsm2_handled("INTENT_ROUTER")
    assert not is_fsm2_handled("START")


@patch.dict(os.environ, {"USE_FSM2": "true"})
def test_fsm2_qualif_name_accepts_name():
    """Avec USE_FSM2=True, QUALIF_NAME + 'Martin Dupont' → passage à QUALIF_PREF."""
    with patch("backend.config.USE_FSM2", True):
        engine = create_engine()
        conv = f"conv_fsm2_name_{uuid.uuid4().hex[:8]}"
        engine.handle_message(conv, "Je veux un rdv")
        events = engine.handle_message(conv, "Martin Dupont")
        assert len(events) == 1
        assert events[0].conv_state == "QUALIF_PREF"
        session = engine.session_store.get(conv)
        assert session is not None
        assert session.qualif_data.name == "Martin Dupont"


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots_vendredi)
@patch.dict(os.environ, {"USE_FSM2": "true"})
def test_fsm2_wait_confirm_early_commit(mock_slots):
    """Avec USE_FSM2=True, WAIT_CONFIRM + 'oui 1' → confirmation créneau, reste WAIT_CONFIRM (avant contact)."""
    with patch("backend.config.USE_FSM2", True):
        engine = create_engine()
        conv = f"conv_fsm2_slot_{uuid.uuid4().hex[:8]}"
        engine.handle_message(conv, "Je veux un rdv")
        engine.handle_message(conv, "Martin Dupont")
        engine.handle_message(conv, "matin")
        engine.handle_message(conv, "oui")
        events = engine.handle_message(conv, "oui 1")
        assert len(events) >= 1
        assert events[0].conv_state == "WAIT_CONFIRM"
        session = engine.session_store.get(conv)
        assert session is not None
        assert session.pending_slot_choice == 1
        assert "confirmez" in events[0].text.lower() or "créneau" in events[0].text.lower()
