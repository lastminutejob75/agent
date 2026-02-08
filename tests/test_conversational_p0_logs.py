"""
Tests que le log conv_p0_start sort bien avec le bon reason (anti-régression silencieuse).
Option 1 : caplog (pytest) — pas de mock du logger.
"""
from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest

from backend.cabinet_data import CabinetData
from backend.conversational_engine import ConversationalEngine
from backend.engine import ENGINE
from backend.tools_faq import default_faq_store


class MockLLMConvClient:
    def __init__(self, fixed_response: str):
        self.fixed_response = fixed_response

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.fixed_response


def _conv_p0_start_records(caplog):
    """Records dont le message est exactement 'conv_p0_start' (extra contient reason, etc.)."""
    return [r for r in caplog.records if r.getMessage() == "conv_p0_start"]


@patch("backend.conversational_engine.config")
def test_conv_p0_start_emits_log_llm_ok(mock_config, caplog):
    """LLM valide → log conv_p0_start avec reason=LLM_OK, next_mode=FSM_BOOKING, llm_used=True."""
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75

    llm_json = json.dumps({
        "response_text": "Bonjour. Je peux vous aider à prendre rendez-vous. Quel est votre nom ?",
        "next_mode": "FSM_BOOKING",
        "extracted": {},
        "confidence": 0.90,
    }, ensure_ascii=False)

    conv_engine = ConversationalEngine(
        cabinet_data=CabinetData.default("Cabinet Dupont"),
        faq_store=default_faq_store(),
        llm_client=MockLLMConvClient(llm_json),
        fsm_engine=ENGINE,
    )

    conv_id = "log-llm-ok"
    s = ENGINE.session_store.get_or_create(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)

    with caplog.at_level(logging.INFO):
        conv_engine.handle_message(conv_id, "bonjour je voudrais un rdv")

    records = _conv_p0_start_records(caplog)
    assert records, "Expected conv_p0_start log not found"

    r = records[-1]
    assert getattr(r, "reason", None) == "LLM_OK"
    assert getattr(r, "next_mode", None) == "FSM_BOOKING"
    assert getattr(r, "llm_used", None) is True
    assert getattr(r, "confidence", None) is not None
    assert getattr(r, "confidence", 0) >= 0.75
    assert getattr(r, "conv_id", None) == conv_id
    assert getattr(r, "start_turn", None) >= 1  # 1 si session vierge, >1 si réutilisation


@patch("backend.conversational_engine.config")
def test_conv_p0_start_emits_log_validation_rejected(mock_config, caplog):
    """LLM renvoie un texte refusé par le validateur (chiffre) → reason=VALIDATION_REJECTED + fallback FSM."""
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75

    # Validateur rejette les chiffres → réponse avec "9h" sera refusée
    llm_json = json.dumps({
        "response_text": "Nous sommes ouverts à 9h. Souhaitez-vous prendre rendez-vous ?",
        "next_mode": "FSM_FALLBACK",
        "extracted": {},
        "confidence": 0.90,
    }, ensure_ascii=False)

    conv_engine = ConversationalEngine(
        cabinet_data=CabinetData.default("Cabinet Dupont"),
        faq_store=default_faq_store(),
        llm_client=MockLLMConvClient(llm_json),
        fsm_engine=ENGINE,
    )

    conv_id = "log-validation-rejected"
    s = ENGINE.session_store.get_or_create(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)

    with caplog.at_level(logging.INFO):
        events = conv_engine.handle_message(conv_id, "vous ouvrez à quelle heure ?")

    records = _conv_p0_start_records(caplog)
    assert records, "Expected conv_p0_start log not found"

    r = records[-1]
    assert getattr(r, "reason", None) == "VALIDATION_REJECTED"
    # C'est bien "appel LLM puis rejet", pas "LLM jamais appelé"
    assert getattr(r, "llm_used", None) is True

    # Fallback FSM : on doit avoir une réponse (FSM a pris la main)
    assert events
    assert events[0].text


@patch("backend.conversational_engine.config")
def test_conv_p0_start_emits_log_strong_intent(mock_config, caplog):
    """Intent forte (ex. annuler) → log avec reason=STRONG_INTENT, pas d'appel LLM."""
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75

    conv_engine = ConversationalEngine(
        cabinet_data=CabinetData.default("Cabinet Dupont"),
        faq_store=default_faq_store(),
        llm_client=MockLLMConvClient("{}"),  # ne sera pas appelé
        fsm_engine=ENGINE,
    )

    conv_id = "log-strong-intent"
    s = ENGINE.session_store.get_or_create(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)

    with caplog.at_level(logging.INFO):
        conv_engine.handle_message(conv_id, "je veux annuler mon rendez-vous")

    records = _conv_p0_start_records(caplog)
    assert records, "Expected conv_p0_start log not found"

    r = records[-1]
    assert getattr(r, "reason", None) == "STRONG_INTENT"
    # Pas de champs LLM : on n'a pas appelé le LLM
    assert getattr(r, "llm_used", None) in (False, None)
    assert getattr(r, "confidence", None) in (None, 0, 0.0)
    assert getattr(r, "next_mode", None) is None


@patch("backend.conversational_engine.config")
def test_conv_p0_start_emits_log_low_conf(mock_config, caplog):
    """Confiance LLM < seuil → reason=LOW_CONF + fallback FSM."""
    mock_config.CONVERSATIONAL_MODE_ENABLED = True
    mock_config.CONVERSATIONAL_CANARY_PERCENT = 100
    mock_config.CONVERSATIONAL_MIN_CONFIDENCE = 0.75

    # LLM répond avec confidence 0.2 → rejeté par seuil
    llm_json = json.dumps({
        "response_text": "Bonjour. Je peux vous aider pour un rendez-vous. Quel est votre nom ?",
        "next_mode": "FSM_BOOKING",
        "extracted": {},
        "confidence": 0.2,
    }, ensure_ascii=False)

    conv_engine = ConversationalEngine(
        cabinet_data=CabinetData.default("Cabinet Dupont"),
        faq_store=default_faq_store(),
        llm_client=MockLLMConvClient(llm_json),
        fsm_engine=ENGINE,
    )

    conv_id = "log-low-conf"
    s = ENGINE.session_store.get_or_create(conv_id)
    s.state = "START"
    ENGINE.session_store.save(s)

    with caplog.at_level(logging.INFO):
        events = conv_engine.handle_message(conv_id, "bonjour je voudrais un rdv")

    records = _conv_p0_start_records(caplog)
    assert records, "Expected conv_p0_start log not found"

    r = records[-1]
    assert getattr(r, "reason", None) == "LOW_CONF"
    assert getattr(r, "confidence", None) is not None
    assert getattr(r, "confidence", 1) < 0.75
    # Pas de next_mode (on n'a pas pris la décision LLM)
    assert getattr(r, "next_mode", None) is None
    # Fallback FSM
    assert events
    assert events[0].text
