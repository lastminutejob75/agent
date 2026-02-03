"""
Tests RÈGLE 3 (silence : 2 messages distincts + 3e => INTENT_ROUTER)
et RÈGLE 7 (contrainte horaire vs fermeture cabinet).
"""

import pytest

from backend.engine import Engine
from backend.session import SessionStore
from backend.tools_faq import FaqStore
from backend import config


@pytest.fixture
def engine():
    store = SessionStore()
    faq = FaqStore(items=[])
    return Engine(session_store=store, faq_store=faq)


def _last_text(events):
    """Prend le dernier texte final dans la liste d'events."""
    for ev in reversed(events or []):
        txt = getattr(ev, "text", "") or ""
        if txt.strip():
            return txt
    return ""


def test_silence_1_then_2_then_router(engine):
    """RÈGLE 3 : 1er silence -> MSG_SILENCE_1, 2e -> MSG_SILENCE_2, 3e -> INTENT_ROUTER."""
    eng = engine
    conv_id = "test-silence-1"
    session = eng.session_store.get_or_create(conv_id)
    session.state = "START"
    session.empty_message_count = 0

    ev1 = eng.handle_message(conv_id, "")
    assert "rien entendu" in _last_text(ev1).lower()

    ev2 = eng.handle_message(conv_id, "")
    assert "toujours là" in _last_text(ev2).lower()

    ev3 = eng.handle_message(conv_id, "")
    txt3 = _last_text(ev3).lower()
    # Menu INTENT_ROUTER : "Dites un", "1", etc.
    assert "dites" in txt3 and ("un" in txt3 or "1" in txt3)


def test_time_constraint_impossible_triggers_router(engine):
    """RÈGLE 7 : 'je finis à 19h' avec fermeture 19h => message impossible + INTENT_ROUTER."""
    if not getattr(config, "TIME_CONSTRAINT_ENABLED", True):
        pytest.skip("TIME_CONSTRAINT_ENABLED désactivé")

    eng = engine
    conv_id = "test-time-constraint-impossible"
    session = eng.session_store.get_or_create(conv_id)
    session.state = "QUALIF_PREF"
    session.qualif_step = "pref"

    events = eng.handle_message(conv_id, "je finis à 19h")
    all_txt = " ".join(getattr(ev, "text", "") or "" for ev in (events or [])).lower()
    assert "ferm" in all_txt
    assert "parler" in all_txt or "créneau" in all_txt or "quelqu'un" in all_txt
