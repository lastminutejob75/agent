"""
Tests du flow ORDONNANCE (conversation naturelle : RDV ou message, pas menu 1/2).
"""

import pytest
from unittest.mock import patch
from backend.engine import detect_ordonnance_choice, detect_intent, Engine
from backend.session import SessionStore
from backend.tools_faq import FaqStore


def test_detect_ordonnance_choice_rdv():
    """Choix RDV en langage naturel."""
    assert detect_ordonnance_choice("je veux un rendez-vous") == "rdv"
    assert detect_ordonnance_choice("un rendez-vous s'il vous plaît") == "rdv"
    assert detect_ordonnance_choice("consultation") == "rdv"
    assert detect_ordonnance_choice("je préfère venir") == "rdv"


def test_detect_ordonnance_choice_message():
    """Choix message en langage naturel."""
    assert detect_ordonnance_choice("transmettez un message") == "message"
    assert detect_ordonnance_choice("laissez un message") == "message"
    assert detect_ordonnance_choice("vous me rappelez") == "message"
    assert detect_ordonnance_choice("contact") == "message"


def test_detect_ordonnance_choice_none():
    """Incompréhension → None."""
    assert detect_ordonnance_choice("euh...") is None
    assert detect_ordonnance_choice("") is None
    assert detect_ordonnance_choice("bof") is None


def test_detect_intent_ordonnance():
    """Intent ORDONNANCE détecté depuis START."""
    assert detect_intent("j'ai besoin d'une ordonnance") == "ORDONNANCE"
    assert detect_intent("ordonnance") == "ORDONNANCE"
    assert detect_intent("renouvellement de traitement") == "ORDONNANCE"


@pytest.fixture
def engine():
    """Engine avec store en mémoire pour tests."""
    store = SessionStore()
    faq = FaqStore(items=[])
    return Engine(session_store=store, faq_store=faq)


def test_ordonnance_flow_ask_choice(engine):
    """User dit 'ordonnance' → agent propose RDV ou message (pas de menu 1/2)."""
    events = engine.handle_message("conv1", "j'ai besoin d'une ordonnance")
    assert events
    text = events[0].text.lower()
    assert "rendez-vous" in text
    assert "message" in text
    # Pas de menu numéroté
    assert "un pour" not in text or "rendez-vous" in text
    session = engine.session_store.get("conv1")
    assert session.state == "ORDONNANCE_CHOICE"


def test_ordonnance_choice_rdv_then_booking(engine):
    """User dit ordonnance puis 'rendez-vous' → démarre booking (quel nom)."""
    engine.handle_message("conv2", "ordonnance")
    events = engine.handle_message("conv2", "je veux un rendez-vous")
    assert events
    text = events[0].text.lower()
    assert "nom" in text
    session = engine.session_store.get("conv2")
    assert session.state == "QUALIF_NAME"


def test_ordonnance_choice_message_then_name(engine):
    """User dit ordonnance puis 'transmettez' → demande le nom."""
    engine.handle_message("conv3", "ordonnance")
    events = engine.handle_message("conv3", "transmettez un message")
    assert events
    text = events[0].text.lower()
    assert "nom" in text
    session = engine.session_store.get("conv3")
    assert session.state == "ORDONNANCE_MESSAGE"


@patch("backend.services.email_service.send_ordonnance_notification")
def test_ordonnance_message_full_flow_notification_sent(mock_send, engine):
    """Flow complet ordonnance → message → nom → téléphone → notification envoyée au cabinet."""
    mock_send.return_value = True
    engine.handle_message("conv4", "ordonnance")
    engine.handle_message("conv4", "transmettez un message")
    engine.handle_message("conv4", "Jean Dupont")
    events = engine.handle_message("conv4", "06 12 34 56 78")
    assert events
    text = events[0].text.lower()
    assert "enregistrée" in text or "rappellerons" in text
    session = engine.session_store.get("conv4")
    assert session.state == "CONFIRMED"
    mock_send.assert_called_once()
    call_args = mock_send.call_args[0][0]
    assert call_args.get("type") == "ordonnance"
    assert call_args.get("name") == "Jean Dupont"
    assert "06" in call_args.get("phone", "") or "612345678" in call_args.get("phone", "")
    assert "timestamp" in call_args
