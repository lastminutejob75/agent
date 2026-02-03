"""
Tests flow CANCEL : P0 (pas de faux positif annulé), P1 (anti-boucle CANCEL_CONFIRM).
"""

import pytest

from backend.engine import Engine
from backend.session import SessionStore
from backend.tools_faq import FaqStore


@pytest.fixture
def engine():
    store = SessionStore()
    faq = FaqStore(items=[])
    return Engine(session_store=store, faq_store=faq)


def _last_text(events):
    for ev in reversed(events or []):
        txt = getattr(ev, "text", "") or ""
        if txt.strip():
            return txt
    return ""


def test_cancel_confirm_unclear_escalates_to_router(engine):
    """3 réponses floues en CANCEL_CONFIRM => INTENT_ROUTER au 3e."""
    conv_id = "tc_unclear"
    session = engine.session_store.get_or_create(conv_id)
    session.state = "CANCEL_CONFIRM"
    session.pending_cancel_slot = {"event_id": "evt_123", "label": "mardi 14h"}
    session.channel = "vocal"

    e1 = engine.handle_message(conv_id, "bof")
    session = engine.session_store.get(conv_id)
    assert session.state == "CANCEL_CONFIRM"

    e2 = engine.handle_message(conv_id, "mouais")
    session = engine.session_store.get(conv_id)
    assert session.state == "CANCEL_CONFIRM"

    e3 = engine.handle_message(conv_id, "je sais pas")
    session = engine.session_store.get(conv_id)
    assert session.state == "INTENT_ROUTER"
    txt = _last_text(e3).lower()
    assert "dites" in txt and ("un" in txt or "1" in txt)


def test_cancel_yes_without_event_id_transfers(engine):
    """Slot sans event_id (SQLite) => TRANSFERRED, pas message 'annulé'."""
    conv_id = "tc_no_event_id"
    session = engine.session_store.get_or_create(conv_id)
    session.state = "CANCEL_CONFIRM"
    session.pending_cancel_slot = {"event_id": None, "label": "lundi 10h"}
    session.channel = "vocal"

    e = engine.handle_message(conv_id, "oui")
    session = engine.session_store.get(conv_id)
    assert session.state == "TRANSFERRED"
    txt = _last_text(e).lower()
    assert "relation" in txt or "instant" in txt


def test_cancel_yes_tool_fail_transfers(engine, monkeypatch):
    """cancel_booking retourne False => TRANSFERRED."""
    import backend.tools_booking as tools_booking
    monkeypatch.setattr(tools_booking, "cancel_booking", lambda *args, **kwargs: False)

    conv_id = "tc_tool_fail"
    session = engine.session_store.get_or_create(conv_id)
    session.state = "CANCEL_CONFIRM"
    session.pending_cancel_slot = {"event_id": "evt_999", "label": "mercredi 9h"}
    session.channel = "vocal"

    e = engine.handle_message(conv_id, "oui")
    session = engine.session_store.get(conv_id)
    assert session.state == "TRANSFERRED"
    txt = _last_text(e).lower()
    assert "relation" in txt or "instant" in txt


def test_cancel_yes_tool_success_confirms(engine, monkeypatch):
    """cancel_booking retourne True => CONFIRMED + message annulé."""
    import backend.tools_booking as tools_booking
    monkeypatch.setattr(tools_booking, "cancel_booking", lambda *args, **kwargs: True)

    conv_id = "tc_success"
    session = engine.session_store.get_or_create(conv_id)
    session.state = "CANCEL_CONFIRM"
    session.pending_cancel_slot = {"event_id": "evt_ok", "label": "jeudi 11h"}
    session.channel = "vocal"

    e = engine.handle_message(conv_id, "oui")
    session = engine.session_store.get(conv_id)
    assert session.state == "CONFIRMED"
    txt = _last_text(e).lower()
    assert "annul" in txt or "c'est fait" in txt


def test_cancel_yes_sqlite_slot_id_success(engine, monkeypatch):
    """Slot SQLite (slot_id, pas event_id) + cancel_booking True => CONFIRMED + message annulé."""
    import backend.tools_booking as tools_booking
    monkeypatch.setattr(tools_booking, "cancel_booking", lambda *args, **kwargs: True)

    conv_id = "tc_sqlite_ok"
    session = engine.session_store.get_or_create(conv_id)
    session.state = "CANCEL_CONFIRM"
    session.pending_cancel_slot = {"event_id": None, "slot_id": 42, "label": "lundi 10h"}
    session.channel = "vocal"

    e = engine.handle_message(conv_id, "oui")
    session = engine.session_store.get(conv_id)
    assert session.state == "CONFIRMED"
    txt = _last_text(e).lower()
    assert "annul" in txt or "c'est fait" in txt
