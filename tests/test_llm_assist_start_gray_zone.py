# tests/test_llm_assist_start_gray_zone.py
"""
LLM Assist Option A : zone grise START, JSON strict, FSM garde la main.
Tests validation (FAQ sans bucket, BOOKING avec bucket, non-JSON, markdown)
et intégration engine (conv_id, BOOKING/FAQ/fallback, timeout).
"""
from __future__ import annotations

import uuid
from unittest.mock import patch, MagicMock

import pytest

from backend.llm_assist import (
    llm_assist_classify,
    _validate_assist_result,
    _looks_like_pure_json,
)
from backend.engine import create_engine


# --- Mock client (retourne JSON strict) ---
class MockLLMClient:
    def __init__(self, response: str):
        self.response = response

    def complete(self, system: str, user: str, timeout_ms: int) -> str:
        return self.response


# --- Spy client (compte les appels, verrouille "LLM NOT called") ---
class SpyLLMClient:
    def __init__(self):
        self.calls = 0

    def complete(self, system: str, user: str, timeout_ms: int) -> str:
        self.calls += 1
        return '{"intent":"UNCLEAR","confidence":0.2,"faq_bucket":null,"should_clarify":true,"rationale":"unexpected call"}'


# --- Validation : FAQ sans bucket => invalide ---
def test_validate_faq_without_bucket_invalid():
    data = {
        "intent": "FAQ",
        "confidence": 0.9,
        "faq_bucket": None,
        "should_clarify": False,
        "rationale": "user asked hours",
    }
    assert _validate_assist_result(data) is False


def test_validate_faq_with_null_bucket_invalid():
    data = {
        "intent": "FAQ",
        "confidence": 0.9,
        "faq_bucket": "null",
        "should_clarify": False,
        "rationale": "user asked hours",
    }
    assert _validate_assist_result(data) is False


# --- Validation : BOOKING avec bucket => invalide ---
def test_validate_booking_with_bucket_invalid():
    data = {
        "intent": "BOOKING",
        "confidence": 0.85,
        "faq_bucket": "HORAIRES",
        "should_clarify": False,
        "rationale": "wants rdv",
    }
    assert _validate_assist_result(data) is False


# --- Validation : output non JSON => rejet ---
def test_looks_like_pure_json_rejects_markdown():
    assert _looks_like_pure_json("```json\n{}\n```") is False
    assert _looks_like_pure_json("Here is the result:\n{}") is False


def test_looks_like_pure_json_accepts_pure():
    assert _looks_like_pure_json('{"intent":"BOOKING","confidence":0.8,"faq_bucket":null,"should_clarify":false,"rationale":""}') is True


def test_looks_like_pure_json_rejects_newline_or_tab():
    assert _looks_like_pure_json('{"intent":"BOOKING"}\n') is False
    assert _looks_like_pure_json('{"intent":"BOOKING"}\r\n') is False
    assert _looks_like_pure_json('{"intent":\t"BOOKING"}') is False


# --- llm_assist_classify : output contient ``` => fallback ---
def test_llm_assist_rejects_markdown_output():
    client = MockLLMClient("```json\n{\"intent\":\"BOOKING\",\"confidence\":0.9,\"faq_bucket\":null,\"should_clarify\":false,\"rationale\":\"\"}\n```")
    with patch("backend.llm_assist.LLM_ASSIST_ENABLED", True):
        result = llm_assist_classify("je voudrais prendre rendez-vous", "START", "vocal", client=client)
    assert result is None


# --- Intégration engine : BOOKING conf 0.85 => state booking (QUALIF_NAME) ---
def test_llm_assist_booking_high_confidence_routes_to_booking():
    json_booking = '{"intent":"BOOKING","confidence":0.85,"faq_bucket":null,"should_clarify":false,"rationale":"wants appointment"}'
    client = MockLLMClient(json_booking)
    engine = create_engine(llm_client=client)
    conv = f"conv_llm_booking_{uuid.uuid4().hex[:8]}"
    with patch("backend.llm_assist.LLM_ASSIST_ENABLED", True), \
         patch("backend.engine.detect_intent", return_value="UNCLEAR"):
        events = engine.handle_message(conv, "euh en fait je voudrais venir la semaine prochaine")
    assert len(events) >= 1
    session = engine.session_store.get_or_create(conv)
    assert session.state == "QUALIF_NAME"


# --- Intégration : FAQ ADRESSE conf 0.9 => state POST_FAQ ---
def test_llm_assist_faq_adresse_high_confidence_routes_to_post_faq():
    json_faq = '{"intent":"FAQ","confidence":0.9,"faq_bucket":"ADRESSE","should_clarify":false,"rationale":"asking location"}'
    client = MockLLMClient(json_faq)
    engine = create_engine(llm_client=client)
    conv = f"conv_llm_faq_{uuid.uuid4().hex[:8]}"
    with patch("backend.llm_assist.LLM_ASSIST_ENABLED", True), \
         patch("backend.engine.detect_intent", return_value="UNCLEAR"):
        events = engine.handle_message(conv, "vous etes ou exactement")
    assert len(events) >= 1
    session = engine.session_store.get_or_create(conv)
    assert session.state == "POST_FAQ"
    assert "Rue" in events[0].text or "adresse" in events[0].text.lower() or "14" in events[0].text or "Paris" in events[0].text


# --- Intégration : confidence faible => fallback clarify/guidance ---
def test_llm_assist_low_confidence_fallback():
    json_low = '{"intent":"BOOKING","confidence":0.5,"faq_bucket":null,"should_clarify":true,"rationale":"uncertain"}'
    client = MockLLMClient(json_low)
    engine = create_engine(llm_client=client)
    conv = f"conv_llm_low_{uuid.uuid4().hex[:8]}"
    with patch("backend.llm_assist.LLM_ASSIST_ENABLED", True), \
         patch("backend.engine.detect_intent", return_value="UNCLEAR"):
        events = engine.handle_message(conv, "bizarre phrase pas claire")
    assert len(events) >= 1
    session = engine.session_store.get_or_create(conv)
    assert session.state == "START"
    text = events[0].text.lower()
    assert "rendez-vous" in text or "question" in text or "aide" in text


# --- Intégration : JSON invalide => fallback ---
def test_llm_assist_invalid_json_fallback():
    client = MockLLMClient("not valid json at all")
    engine = create_engine(llm_client=client)
    conv = f"conv_llm_invalid_{uuid.uuid4().hex[:8]}"
    with patch("backend.llm_assist.LLM_ASSIST_ENABLED", True), \
         patch("backend.engine.detect_intent", return_value="UNCLEAR"):
        events = engine.handle_message(conv, "une phrase un peu vague")
    assert len(events) >= 1
    session = engine.session_store.get_or_create(conv)
    assert session.state == "START"


# --- Intégration : timeout => fallback ---
def test_llm_assist_timeout_fallback():
    def timeout_complete(*args, **kwargs):
        raise TimeoutError("timeout")
    client = MagicMock()
    client.complete = timeout_complete
    engine = create_engine(llm_client=client)
    conv = f"conv_llm_to_{uuid.uuid4().hex[:8]}"
    with patch("backend.llm_assist.LLM_ASSIST_ENABLED", True), \
         patch("backend.engine.detect_intent", return_value="UNCLEAR"):
        events = engine.handle_message(conv, "phrase ambiguë")
    assert len(events) >= 1
    session = engine.session_store.get_or_create(conv)
    assert session.state == "START"


# --- LLM désactivé par défaut ---
def test_llm_assist_disabled_by_default_returns_none():
    client = MockLLMClient('{"intent":"BOOKING","confidence":0.9,"faq_bucket":null,"should_clarify":false,"rationale":""}')
    with patch("backend.llm_assist.LLM_ASSIST_ENABLED", False):
        result = llm_assist_classify("je veux un rdv", "START", "web", client=client)
    assert result is None


# --- LLM jamais appelé pour oui / d'accord / ok (spy) ---
@pytest.mark.parametrize("utterance", [
    "oui",
    "ok",
    "okay",
    "d'accord",
    "d accord",
    "ouais",
])
def test_llm_not_called_for_yes_tokens_in_start(utterance):
    """
    START : même si detect_intent retourne UNCLEAR, on ne doit pas appeler le LLM
    pour les tokens type oui/d'accord (yes_safe_refuse).
    """
    with patch("backend.llm_assist.LLM_ASSIST_ENABLED", True), \
         patch("backend.engine.detect_intent", lambda text, state="": "UNCLEAR"):
        spy = SpyLLMClient()
        engine = create_engine(llm_client=spy)
        safe_utt = utterance.replace(" ", "_").replace("'", "")
        conv_id = f"test_conv_yes_{safe_utt}_{uuid.uuid4().hex[:6]}"
        session = engine.session_store.get_or_create(conv_id)
        session.channel = "vocal"
        session.state = "START"
        engine._save_session(session)

        engine.handle_message(conv_id, utterance)
        session = engine.session_store.get_or_create(conv_id)

        assert spy.calls == 0, f"LLM must not be called for utterance={utterance!r}"
        assert session.state not in ("QUALIF_NAME", "QUALIF_PREF"), f"Must not route to booking: state={session.state}"


@pytest.mark.parametrize("utterance", [
    "merci",
    "bonjour",
    "salut",
])
def test_llm_not_called_for_single_token_non_filler(utterance):
    """
    START : tout énoncé single-token ne doit pas déclencher le LLM (guard len(tokens) <= 1).
    """
    with patch("backend.llm_assist.LLM_ASSIST_ENABLED", True), \
         patch("backend.engine.detect_intent", lambda text, state="": "UNCLEAR"):
        spy = SpyLLMClient()
        engine = create_engine(llm_client=spy)
        conv_id = f"test_conv_one_{utterance}_{uuid.uuid4().hex[:6]}"
        session = engine.session_store.get_or_create(conv_id)
        session.channel = "vocal"
        session.state = "START"
        engine._save_session(session)

        engine.handle_message(conv_id, utterance)
        session = engine.session_store.get_or_create(conv_id)

        assert spy.calls == 0, f"LLM must not be called for single-token utterance={utterance!r}"


# --- Miroir : LLM appelé une fois pour phrase 2+ tokens (guard pas trop strict) ---
def test_llm_called_once_when_unclear_multi_token():
    """
    START + UNCLEAR + 2+ tokens : le LLM doit être appelé (évite régression "LLM jamais appelé").
    """
    with patch("backend.llm_assist.LLM_ASSIST_ENABLED", True), \
         patch("backend.engine.detect_intent", lambda text, state="": "UNCLEAR"):
        spy = SpyLLMClient()
        engine = create_engine(llm_client=spy)
        conv_id = f"test_conv_llm_called_{uuid.uuid4().hex[:8]}"
        session = engine.session_store.get_or_create(conv_id)
        session.channel = "vocal"
        session.state = "START"
        engine._save_session(session)

        engine.handle_message(conv_id, "je voudrais venir demain")

        assert spy.calls == 1, "LLM should be called once for multi-token UNCLEAR utterance"
