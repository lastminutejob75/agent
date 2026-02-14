# tests/test_fix6_transfer_policy.py
"""
Fix #6: politique TRANSFER — "humain" seul → clarify, phrase explicite → transfert direct.
"""
import pytest
from backend.transfer_policy import classify_transfer_request


def test_classify_short_keywords():
    """Mots seuls ou très courts → SHORT."""
    assert classify_transfer_request("humain") == "SHORT"
    assert classify_transfer_request("transfert") == "SHORT"
    assert classify_transfer_request("conseiller") == "SHORT"
    assert classify_transfer_request("humain svp") == "SHORT"
    assert classify_transfer_request("  opérateur  ") == "SHORT"


def test_classify_explicit_phrase():
    """Phrase avec verbe/action → EXPLICIT."""
    assert classify_transfer_request("je veux parler à un conseiller") == "EXPLICIT"
    assert classify_transfer_request("mettez-moi en relation avec quelqu'un") == "EXPLICIT"
    assert classify_transfer_request("Je voudrais parler à une personne") == "EXPLICIT"
    assert classify_transfer_request("transférer moi au standard") == "EXPLICIT"


def test_classify_none():
    """Texte vide ou sans demande transfert → NONE."""
    assert classify_transfer_request("") == "NONE"
    assert classify_transfer_request("   ") == "NONE"
    assert classify_transfer_request("je veux un rendez-vous") == "NONE"


def test_humain_seul_clarify_no_transfer():
    """START + 'humain' seul → message clarify, pas de transfert (state CLARIFY ou message = VOCAL_CLARIFY)."""
    from backend.engine import Engine
    from backend.session import SessionStore
    from backend.tools_faq import FaqStore
    from unittest.mock import patch

    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv_id = "fix6-humain"
    # Forcer intent TRANSFER via route_start / strong (START state)
    with patch.object(engine, "_trigger_transfer") as mock_transfer:
        events = engine.handle_message(conv_id, "humain")
        mock_transfer.assert_not_called()
    assert len(events) >= 1
    assert events[0].type == "final"
    # Message = clarify (prendre rdv / question)
    msg = events[0].text or ""
    assert "rendez-vous" in msg.lower() or "question" in msg.lower() or "souci" in msg.lower()
    session = store.get(conv_id)
    assert session is not None
    assert session.state != "TRANSFERRED"


def test_phrase_explicite_transfer_direct():
    """'je veux parler à un conseiller' → TRANSFERRED (transfert direct)."""
    from backend.engine import Engine
    from backend.session import SessionStore
    from backend.tools_faq import FaqStore

    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv_id = "fix6-explicit"
    events = engine.handle_message(conv_id, "je veux parler à un conseiller")
    session = store.get(conv_id)
    assert session is not None
    assert session.state == "TRANSFERRED"
    assert len(events) >= 1
    assert getattr(events[0], "conv_state", None) == "TRANSFERRED"


def test_wait_confirm_transfert_court_clarify():
    """WAIT_CONFIRM + 'transfert' (court) → clarify/help, pas de reset slots destructif, pas de transfert."""
    from backend.engine import Engine
    from backend.session import SessionStore
    from backend.tools_faq import FaqStore
    from unittest.mock import patch

    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv_id = "fix6-waitconfirm"
    session = store.get_or_create(conv_id)
    session.state = "WAIT_CONFIRM"
    session.channel = "vocal"
    # Pending slots (format canonique)
    session.pending_slots = [
        {"id": 1, "start": "2026-02-16T10:00:00", "end": "2026-02-16T10:15:00", "label": "Lundi 10h", "label_vocal": "Lundi 10h", "day": "lundi", "source": "sqlite"},
    ]
    session.is_reading_slots = True

    with patch.object(engine, "_trigger_transfer") as mock_transfer:
        events = engine.handle_message(conv_id, "transfert")
        mock_transfer.assert_not_called()
    assert len(events) >= 1
    assert events[0].type == "final"
    session_after = store.get(conv_id)
    assert session_after.state != "TRANSFERRED"
    # Pending slots pas vidés (pas destructif)
    assert len(session_after.pending_slots or []) == 1
