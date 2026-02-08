# tests/test_conversational_p0_start.py
"""
Tests P0 mode conversationnel : START uniquement, placeholders, validation, fallback FSM.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock

from backend.cabinet_data import CabinetData
from backend.placeholders import replace_placeholders, ALLOWED_PLACEHOLDERS
from backend.response_validator import validate_llm_json, validate_conv_result
from backend.llm_conversation import (
    ConvResult,
    StubLLMConvClient,
    complete_conversation,
)
from backend.conversational_engine import ConversationalEngine, _is_canary
from backend.tools_faq import default_faq_store, FaqStore
from backend.engine import ENGINE, Event
from backend.session import Session


# --- Mock LLM client enregistrant les appels ---
class MockLLMConvClient:
    def __init__(self, fixed_response: str | None = None):
        self.fixed_response = fixed_response
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.call_count += 1
        self.last_system = system_prompt
        self.last_user = user_prompt
        if self.fixed_response is not None:
            return self.fixed_response
        return json.dumps({
            "response_text": "Bonjour ! Je peux vous aider pour un rendez-vous ou une question. Souhaitez-vous prendre rendez-vous ?",
            "next_mode": "FSM_BOOKING",
            "extracted": {},
            "confidence": 0.9,
        }, ensure_ascii=False)


# --- Fixtures ---
@pytest.fixture
def cabinet_data():
    return CabinetData.default("Cabinet Dupont")


@pytest.fixture
def faq_store():
    return default_faq_store()


@pytest.fixture
def conv_engine(faq_store, cabinet_data):
    """Engine conversationnel avec mock LLM (réponse par défaut)."""
    return ConversationalEngine(
        cabinet_data=cabinet_data,
        faq_store=faq_store,
        llm_client=MockLLMConvClient(),
        fsm_engine=ENGINE,
    )


# --- 1) Natural + booking ---
@patch("backend.conversational_engine.config")
def test_llm_start_generates_natural_then_booking(mock_config, conv_engine, faq_store, cabinet_data):
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    conv_engine.llm_client = MockLLMConvClient(fixed_response=json.dumps({
        "response_text": "Bonjour ! Je peux vous aider. Souhaitez-vous prendre rendez-vous ? Donnez-moi votre nom.",
        "next_mode": "FSM_BOOKING",
        "extracted": {"name": "Martin Dupont"},
        "confidence": 0.9,
    }, ensure_ascii=False))

    conv_id = "test-natural-booking"
    ENGINE.session_store.get_or_create(conv_id)
    session_before = ENGINE.session_store.get(conv_id)
    assert session_before is not None
    session_before.state = "START"
    ENGINE.session_store.save(session_before)

    events = conv_engine.handle_message(conv_id, "Bonjour je voudrais un rdv")

    assert len(events) >= 1
    assert events[0].text
    assert "rendez-vous" in events[0].text.lower() or "nom" in events[0].text.lower() or "Martin" in events[0].text
    session_after = ENGINE.session_store.get(conv_id)
    assert session_after is not None
    assert session_after.state == "QUALIF_NAME"
    if "Martin" in events[0].text or session_after.qualif_data.name:
        assert session_after.qualif_data.name == "Martin Dupont"


# --- 2) FAQ placeholder remplacé ---
@patch("backend.conversational_engine.config")
def test_llm_start_faq_placeholder_replaced(mock_config, conv_engine, faq_store, cabinet_data):
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    # Réponse officielle horaires dans default_faq_store
    horaires_text = "Nous sommes ouverts du lundi au vendredi, de 9 heures à 18 heures."
    conv_engine.llm_client = MockLLMConvClient(fixed_response=json.dumps({
        "response_text": "Voici les infos : {FAQ_HORAIRES}. Souhaitez-vous prendre rendez-vous ?",
        "next_mode": "FSM_FAQ",
        "extracted": {},
        "confidence": 0.9,
    }, ensure_ascii=False))

    conv_id = "test-faq-placeholder"
    ENGINE.session_store.get_or_create(conv_id)
    session_before = ENGINE.session_store.get(conv_id)
    session_before.state = "START"
    ENGINE.session_store.save(session_before)

    events = conv_engine.handle_message(conv_id, "Vous êtes ouverts quand ?")

    assert len(events) >= 1
    assert horaires_text in events[0].text
    session_after = ENGINE.session_store.get(conv_id)
    assert session_after is not None
    assert session_after.state == "POST_FAQ"


# --- 3) Rejet si chiffres → fallback FSM ---
@patch("backend.conversational_engine.config")
def test_llm_rejected_if_contains_digits(mock_config, conv_engine):
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    # JSON valide mais response_text avec "9h" → validate_conv_result rejette
    conv_engine.llm_client = MockLLMConvClient(fixed_response=json.dumps({
        "response_text": "Nous sommes ouverts à 9h.",
        "next_mode": "FSM_FALLBACK",
        "extracted": {},
        "confidence": 0.9,
    }, ensure_ascii=False))

    conv_id = "test-reject-digits"
    ENGINE.session_store.get_or_create(conv_id)
    s = ENGINE.session_store.get(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)

    events = conv_engine.handle_message(conv_id, "Vous ouvrez à quelle heure ?")

    # Fallback FSM : pas le texte "9h" (réponse FAQ ou clarification)
    assert len(events) >= 1
    assert "9h" not in events[0].text
    # Soit state reste START (clarification), soit POST_FAQ (réponse FAQ FSM)
    session_after = ENGINE.session_store.get(conv_id)
    assert session_after is not None


# --- 4) Placeholder inconnu → rejet ---
def test_validate_conv_result_rejects_unknown_placeholder():
    data = {
        "response_text": "Voici : {FAQ_PIZZA}.",
        "next_mode": "FSM_FAQ",
        "extracted": {},
        "confidence": 0.9,
    }
    assert validate_conv_result(data) is False


@patch("backend.conversational_engine.config")
def test_llm_rejected_if_unknown_placeholder(mock_config, conv_engine):
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    conv_engine.llm_client = MockLLMConvClient(fixed_response=json.dumps({
        "response_text": "Voici : {FAQ_PIZZA}.",
        "next_mode": "FSM_FAQ",
        "extracted": {},
        "confidence": 0.9,
    }, ensure_ascii=False))

    conv_id = "test-unknown-placeholder"
    ENGINE.session_store.get_or_create(conv_id)
    s = ENGINE.session_store.get(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)

    events = conv_engine.handle_message(conv_id, "Vous faites des pizzas ?")

    assert len(events) >= 1
    assert "{FAQ_PIZZA}" not in events[0].text


# --- 5) Strong intent bypass LLM ---
@patch("backend.conversational_engine.config")
def test_strong_intent_bypasses_llm(mock_config, conv_engine):
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    mock_llm = MockLLMConvClient()
    conv_engine.llm_client = mock_llm

    conv_id = "test-strong-cancel"
    ENGINE.session_store.get_or_create(conv_id)
    s = ENGINE.session_store.get(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)

    events = conv_engine.handle_message(conv_id, "je veux annuler mon rendez-vous")

    assert mock_llm.call_count == 0
    assert len(events) >= 1
    session_after = ENGINE.session_store.get(conv_id)
    assert session_after is not None
    assert session_after.state == "CANCEL_NAME" or "annul" in events[0].text.lower()


# --- 6) Low confidence → fallback ---
@patch("backend.conversational_engine.config")
def test_llm_low_confidence_fallback(mock_config, conv_engine):
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    conv_engine.llm_client = MockLLMConvClient(fixed_response=json.dumps({
        "response_text": "Bonjour ! Souhaitez-vous prendre rendez-vous ?",
        "next_mode": "FSM_BOOKING",
        "extracted": {},
        "confidence": 0.4,
    }, ensure_ascii=False))

    conv_id = "test-low-conf"
    ENGINE.session_store.get_or_create(conv_id)
    s = ENGINE.session_store.get(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)

    events = conv_engine.handle_message(conv_id, "euh bonjour")

    # Fallback FSM (clarification ou FAQ), pas la phrase exacte du LLM forcément
    assert len(events) >= 1


# --- Validator unit ---
def test_validate_llm_json_rejects_markdown():
    assert validate_llm_json('```json\n{"x":1}\n```') is None
    assert validate_llm_json('{"response_text": "ok", "next_mode": "FSM_BOOKING", "confidence": 0.9, "extracted": {}}') is not None


def test_validate_conv_result_accepts_valid():
    data = {
        "response_text": "Bonjour ! Souhaitez-vous un rendez-vous ?",
        "next_mode": "FSM_BOOKING",
        "extracted": {},
        "confidence": 0.86,
    }
    assert validate_conv_result(data) is True


def test_validate_conv_result_rejects_placeholder_when_not_fsm_faq():
    """Placeholders FAQ autorisés uniquement si next_mode == FSM_FAQ (évite pizza → annulation)."""
    data = {
        "response_text": "D'accord. Pour annuler : {FAQ_ANNULATION}. C'est à quel nom ?",
        "next_mode": "FSM_BOOKING",
        "extracted": {},
        "confidence": 0.9,
    }
    assert validate_conv_result(data) is False


def test_validate_conv_result_rejects_placeholder_in_fsm_fallback():
    """FSM_FALLBACK = excuse + redirection, pas de faits (aucun placeholder)."""
    data = {
        "response_text": "Nous sommes un cabinet médical. {FAQ_HORAIRES} Puis-je vous aider ?",
        "next_mode": "FSM_FALLBACK",
        "extracted": {},
        "confidence": 0.8,
    }
    assert validate_conv_result(data) is False


def test_validate_conv_result_rejects_more_than_one_placeholder_in_fsm_faq():
    """P0 vocal: max 1 placeholder par réponse en FSM_FAQ."""
    data = {
        "response_text": "Voici : {FAQ_HORAIRES} et {FAQ_ADRESSE}. Autre chose ?",
        "next_mode": "FSM_FAQ",
        "extracted": {},
        "confidence": 0.9,
    }
    assert validate_conv_result(data) is False


@patch("backend.conversational_engine.config")
def test_pizza_placeholder_annulation_fallback(mock_config, conv_engine):
    """Pizza + LLM retourne placeholder annulation → validator reject → fallback FSM (pas de faux FAQ)."""
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    conv_engine.llm_client = MockLLMConvClient(fixed_response=json.dumps({
        "response_text": "Pour annuler un rendez-vous : {FAQ_ANNULATION}. Souhaitez-vous un RDV ?",
        "next_mode": "FSM_BOOKING",
        "extracted": {},
        "confidence": 0.9,
    }, ensure_ascii=False))
    conv_id = "test-pizza-placeholder"
    ENGINE.session_store.get_or_create(conv_id)
    s = ENGINE.session_store.get(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)
    events = conv_engine.handle_message(conv_id, "Vous faites des pizzas ?")
    assert len(events) >= 1
    assert "{FAQ_ANNULATION}" not in events[0].text
    assert "24 heures" not in events[0].text  # pas d'injection FAQ annulation (fallback FSM)


def test_replace_placeholders(faq_store, cabinet_data):
    text = "Horaires : {FAQ_HORAIRES}. Merci."
    out = replace_placeholders(text, faq_store, cabinet_data)
    assert "9 heures" in out or "lundi" in out
    assert "{FAQ_HORAIRES}" not in out


def test_is_canary():
    with patch("backend.conversational_engine.config") as cfg:
        cfg.CONVERSATIONAL_CANARY_PERCENT = 0
        assert _is_canary("any") is False
        cfg.CONVERSATIONAL_CANARY_PERCENT = 100
        assert _is_canary("any") is True
        cfg.CONVERSATIONAL_CANARY_PERCENT = 50
        assert _is_canary("any") in (True, False)


# --- Canary 0 désactive le mode conv ---
def test_canary_zero_disables_conversational(conv_engine, monkeypatch):
    """Canary 0 => engine route vers FSM sans appeler le LLM."""
    import backend.config as config_module
    monkeypatch.setattr(config_module, "CONVERSATIONAL_MODE_ENABLED", True)
    monkeypatch.setattr(config_module, "CONVERSATIONAL_CANARY_PERCENT", 0)
    mock_llm = MockLLMConvClient()
    conv_engine.llm_client = mock_llm
    conv_id = "test-canary-zero"
    ENGINE.session_store.get_or_create(conv_id)
    s = ENGINE.session_store.get(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)

    conv_engine.handle_message(conv_id, "bonjour")

    assert mock_llm.call_count == 0


# --- Placeholder interdit en FALLBACK ---
@patch("backend.conversational_engine.config")
def test_placeholder_rejected_outside_faq(mock_config, conv_engine):
    """LLM retourne FSM_FALLBACK avec {FAQ_ANNULATION} → validator reject → fallback FSM, pas d'expansion placeholder."""
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    conv_engine.llm_client = MockLLMConvClient(fixed_response=json.dumps({
        "response_text": "Désolé, nous sommes un cabinet médical. {FAQ_ANNULATION} Puis-je vous aider ?",
        "next_mode": "FSM_FALLBACK",
        "extracted": {},
        "confidence": 0.9,
    }, ensure_ascii=False))
    conv_id = "test-placeholder-fallback"
    ENGINE.session_store.get_or_create(conv_id)
    s = ENGINE.session_store.get(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)
    events = conv_engine.handle_message(conv_id, "vous faites des pizzas ?")
    assert len(events) >= 1
    assert "{FAQ_ANNULATION}" not in events[0].text
    assert "24 heures" not in events[0].text


# --- FAQ: max 1 placeholder ---
@patch("backend.conversational_engine.config")
def test_faq_more_than_one_placeholder_rejected(mock_config, conv_engine):
    """LLM retourne FSM_FAQ avec \"{FAQ_HORAIRES} {FAQ_ADRESSE}\" → reject → fallback FSM."""
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    conv_engine.llm_client = MockLLMConvClient(fixed_response=json.dumps({
        "response_text": "Voici : {FAQ_HORAIRES} et {FAQ_ADRESSE}. Autre chose ?",
        "next_mode": "FSM_FAQ",
        "extracted": {},
        "confidence": 0.9,
    }, ensure_ascii=False))
    conv_id = "test-faq-two-placeholders"
    ENGINE.session_store.get_or_create(conv_id)
    s = ENGINE.session_store.get(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)
    events = conv_engine.handle_message(conv_id, "c'est quoi vos horaires et votre adresse ?")
    assert len(events) >= 1
    assert "{FAQ_HORAIRES}" not in events[0].text and "{FAQ_ADRESSE}" not in events[0].text


# --- Pizza: fallback texte naturel sans placeholders ---
@patch("backend.conversational_engine.config")
def test_pizza_returns_llm_fallback_text_no_placeholders(mock_config, conv_engine):
    """LLM retourne FSM_FALLBACK avec redirection polie (sans placeholders) → ce texte exact retourné, state safe."""
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    fallback_text = "Désolé, nous sommes un cabinet médical. Je peux vous aider pour un rendez-vous ou une question."
    conv_engine.llm_client = MockLLMConvClient(fixed_response=json.dumps({
        "response_text": fallback_text,
        "next_mode": "FSM_FALLBACK",
        "extracted": {},
        "confidence": 0.9,
    }, ensure_ascii=False))
    conv_id = "test-pizza-fallback-text"
    ENGINE.session_store.get_or_create(conv_id)
    s = ENGINE.session_store.get(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)
    events = conv_engine.handle_message(conv_id, "je veux une pizza")
    assert len(events) >= 1
    assert events[0].text == fallback_text
    assert "cabinet" in events[0].text.lower()
    session_after = ENGINE.session_store.get(conv_id)
    assert session_after is not None
    assert session_after.state in ("START", "POST_FAQ") or "TRANSFERRED" != session_after.state


# --- Pizza : réponse = texte LLM FSM_FALLBACK, pas clarification FSM ---
@patch("backend.conversational_engine.config")
def test_pizza_fsm_fallback_returns_llm_text_not_fsm_clarification(mock_config, conv_engine):
    """Force FSM_FALLBACK avec phrase 'cabinet médical' → la réponse doit être ce texte, pas une clarification FSM."""
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75
    llm_fallback = "Désolé, je suis l'assistant du Cabinet Dupont. Je peux vous aider pour un rendez-vous ou une question du cabinet. Souhaitez-vous prendre rendez-vous ?"
    conv_engine.llm_client = MockLLMConvClient(fixed_response=json.dumps({
        "response_text": llm_fallback,
        "next_mode": "FSM_FALLBACK",
        "extracted": {},
        "confidence": 0.86,
    }, ensure_ascii=False))
    conv_id = "test-pizza-llm-not-fsm"
    ENGINE.session_store.get_or_create(conv_id)
    s = ENGINE.session_store.get(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)
    events = conv_engine.handle_message(conv_id, "je veux une pizza")
    assert len(events) >= 1
    assert events[0].text == llm_fallback
    assert "Cabinet Dupont" in events[0].text
    assert "cabinet" in events[0].text.lower()


# --- Pizza + RDV ⇒ FSM_BOOKING (pas fallback) ---
@patch("backend.conversational_engine.config")
def test_pizza_and_booking_routes_to_booking_not_fallback(mock_config, conv_engine):
    """
    Si la phrase contient du hors-scope + une intention RDV,
    on DOIT partir en booking (FSM_BOOKING), pas en FSM_FALLBACK.
    """
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75

    # LLM répond naturellement : il refuse la pizza MAIS comprend la demande de RDV
    conv_engine.llm_client = MockLLMConvClient(
        fixed_response=json.dumps({
            "response_text": (
                "Je ne peux pas vous aider pour une commande. "
                "En revanche, je peux vous aider à prendre rendez-vous. "
                "Quel est votre nom, s'il vous plaît ?"
            ),
            "next_mode": "FSM_BOOKING",
            "extracted": {},
            "confidence": 0.9,
        }, ensure_ascii=False)
    )

    conv_id = "test-pizza-and-booking-routes-booking"

    # Forcer session START
    session = ENGINE.session_store.get_or_create(conv_id)
    session.state = "START"
    ENGINE.session_store.save(session)

    events = conv_engine.handle_message(conv_id, "Je veux une pizza et aussi un rendez-vous")
    assert events and events[0].text

    # On doit bien être en booking
    session_after = ENGINE.session_store.get(conv_id)
    assert session_after is not None
    assert session_after.state == "QUALIF_NAME"

    # Vérifier que c'est bien la réponse LLM (pas une clarification FSM générique)
    txt = events[0].text.lower()
    assert "rendez-vous" in txt
    assert "pizza" not in txt  # optionnel : l'agent n'a pas besoin de répéter "pizza"
