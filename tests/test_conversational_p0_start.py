# tests/test_conversational_p0_start.py
"""
P0 Tests for Conversational Mode (START state only).

Tests validate:
1. Natural LLM responses with placeholder replacement
2. Strict validation rejects unsafe content
3. Fallback to FSM on validation failure
4. Strong intents bypass LLM
5. Confidence threshold enforcement
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional

from backend.cabinet_data import CabinetData, DEFAULT_CABINET_DATA
from backend.placeholders import (
    ALLOWED_PLACEHOLDERS,
    find_placeholders,
    validate_placeholders,
    replace_placeholders,
)
from backend.response_validator import (
    validate_llm_json,
    validate_conv_result,
    full_validate,
    VALID_NEXT_MODES,
)
from backend.llm_conversation import (
    LLMClient,
    StubLLMClient,
    ConvResult,
    build_system_prompt,
)
from backend.conversational_engine import ConversationalEngine
from backend.session import Session, SessionStore
from backend.tools_faq import FaqStore


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def mock_faq_store():
    """Mock FAQ store that returns predefined answers."""
    store = MagicMock(spec=FaqStore)

    @dataclass
    class FaqResult:
        match: bool
        answer: Optional[str]
        faq_id: Optional[str]
        score: float

    def mock_search(query):
        faq_answers = {
            "horaires": FaqResult(
                match=True,
                answer="Le cabinet est ouvert du lundi au vendredi de 9h à 18h.",
                faq_id="FAQ_HORAIRES",
                score=0.95,
            ),
            "adresse": FaqResult(
                match=True,
                answer="Le cabinet est situé au 10 rue de la Santé, Paris 13e.",
                faq_id="FAQ_ADRESSE",
                score=0.95,
            ),
            "tarifs": FaqResult(
                match=True,
                answer="Consultation générale : 25€. Conventionné secteur 1.",
                faq_id="FAQ_TARIFS",
                score=0.95,
            ),
        }
        q = query.lower()
        for key, result in faq_answers.items():
            if key in q:
                return result
        return FaqResult(match=False, answer=None, faq_id=None, score=0.0)

    store.search = mock_search
    return store


@pytest.fixture
def session_store():
    """Fresh session store for each test."""
    return SessionStore()


@pytest.fixture
def mock_fsm_engine(session_store, mock_faq_store):
    """Mock FSM engine for fallback."""
    engine = MagicMock()
    engine.session_store = session_store
    engine.faq_store = mock_faq_store

    def mock_handle_message(conv_id, user_text):
        from backend.engine import Event
        return [Event("final", f"FSM fallback: {user_text}", conv_state="START")]

    engine.handle_message = mock_handle_message
    return engine


@pytest.fixture
def stub_llm_client():
    """Stub LLM client for testing."""
    return StubLLMClient()


@pytest.fixture
def conversational_engine(mock_fsm_engine, stub_llm_client, mock_faq_store):
    """Configured conversational engine for testing."""
    return ConversationalEngine(
        fsm_engine=mock_fsm_engine,
        llm_client=stub_llm_client,
        faq_store=mock_faq_store,
        cabinet_data=DEFAULT_CABINET_DATA,
    )


# ============================================================
# Test: JSON Validation
# ============================================================

class TestJsonValidation:
    """Tests for validate_llm_json function."""

    def test_valid_json(self):
        raw = '{"response_text": "Bonjour!", "next_mode": "FSM_FAQ", "confidence": 0.9}'
        result = validate_llm_json(raw)
        assert result is not None
        assert result["response_text"] == "Bonjour!"

    def test_rejects_markdown(self):
        raw = '```json\n{"response_text": "test"}\n```'
        assert validate_llm_json(raw) is None

    def test_rejects_non_object(self):
        assert validate_llm_json("[]") is None
        assert validate_llm_json('"string"') is None

    def test_rejects_invalid_json(self):
        assert validate_llm_json('{"broken":') is None
        assert validate_llm_json("not json at all") is None

    def test_rejects_empty(self):
        assert validate_llm_json("") is None
        assert validate_llm_json("   ") is None


# ============================================================
# Test: ConvResult Validation
# ============================================================

class TestConvResultValidation:
    """Tests for validate_conv_result function."""

    def test_valid_result(self):
        data = {
            "response_text": "Bonjour ! Comment puis-je vous aider ?",
            "next_mode": "FSM_FALLBACK",
            "confidence": 0.85,
        }
        is_valid, reason = validate_conv_result(data)
        assert is_valid
        assert reason == ""

    def test_missing_response_text(self):
        data = {"next_mode": "FSM_FALLBACK", "confidence": 0.85}
        is_valid, reason = validate_conv_result(data)
        assert not is_valid
        assert reason == "missing_response_text"

    def test_invalid_next_mode(self):
        data = {
            "response_text": "Bonjour !",
            "next_mode": "INVALID_MODE",
            "confidence": 0.85,
        }
        is_valid, reason = validate_conv_result(data)
        assert not is_valid
        assert "invalid_next_mode" in reason

    def test_low_confidence_rejected(self):
        data = {
            "response_text": "Bonjour !",
            "next_mode": "FSM_FALLBACK",
            "confidence": 0.4,
        }
        is_valid, reason = validate_conv_result(data)
        assert not is_valid
        assert "low_confidence" in reason

    def test_response_too_long(self):
        data = {
            "response_text": "x" * 300,  # > 280
            "next_mode": "FSM_FALLBACK",
            "confidence": 0.85,
        }
        is_valid, reason = validate_conv_result(data)
        assert not is_valid
        assert "response_too_long" in reason

    def test_contains_digits_rejected(self):
        data = {
            "response_text": "Le cabinet ouvre à 9h",
            "next_mode": "FSM_FAQ",
            "confidence": 0.9,
        }
        is_valid, reason = validate_conv_result(data)
        assert not is_valid
        assert reason == "contains_digits"

    def test_contains_currency_rejected(self):
        data = {
            "response_text": "La consultation coûte €",
            "next_mode": "FSM_FAQ",
            "confidence": 0.9,
        }
        is_valid, reason = validate_conv_result(data)
        assert not is_valid
        assert reason == "contains_currency"

    def test_forbidden_words_rejected(self):
        data = {
            "response_text": "Nous sommes ouvert du lundi au vendredi",
            "next_mode": "FSM_FAQ",
            "confidence": 0.9,
        }
        is_valid, reason = validate_conv_result(data)
        assert not is_valid
        assert "forbidden_word:ouvert" in reason

    def test_medical_markers_rejected(self):
        data = {
            "response_text": "La posologie recommandée est de prendre deux fois par jour",
            "next_mode": "FSM_FAQ",
            "confidence": 0.9,
        }
        is_valid, reason = validate_conv_result(data)
        assert not is_valid
        assert "medical_marker:posologie" in reason

    def test_allowed_placeholder_accepted(self):
        data = {
            "response_text": "Voici nos informations : {FAQ_HORAIRES}",
            "next_mode": "FSM_FAQ",
            "confidence": 0.9,
        }
        is_valid, reason = validate_conv_result(data)
        assert is_valid

    def test_unknown_placeholder_rejected(self):
        data = {
            "response_text": "Voici les infos : {FAQ_PIZZA}",
            "next_mode": "FSM_FAQ",
            "confidence": 0.9,
        }
        is_valid, reason = validate_conv_result(data)
        assert not is_valid
        assert "unknown_placeholder" in reason


# ============================================================
# Test: Placeholder System
# ============================================================

class TestPlaceholders:
    """Tests for placeholder finding and validation."""

    def test_find_placeholders(self):
        text = "Bonjour ! {FAQ_HORAIRES} et aussi {FAQ_ADRESSE}"
        found = find_placeholders(text)
        assert "{FAQ_HORAIRES}" in found
        assert "{FAQ_ADRESSE}" in found
        assert len(found) == 2

    def test_find_no_placeholders(self):
        text = "Bonjour, comment puis-je vous aider ?"
        found = find_placeholders(text)
        assert len(found) == 0

    def test_validate_allowed_placeholders(self):
        text = "Nos horaires : {FAQ_HORAIRES}"
        is_valid, invalid = validate_placeholders(text)
        assert is_valid
        assert len(invalid) == 0

    def test_validate_unknown_placeholder(self):
        text = "Notre menu : {FAQ_PIZZA}"
        is_valid, invalid = validate_placeholders(text)
        assert not is_valid
        assert "{FAQ_PIZZA}" in invalid

    def test_replace_placeholders(self, mock_faq_store):
        text = "Voici nos horaires : {FAQ_HORAIRES}"
        replaced, success = replace_placeholders(text, mock_faq_store)
        assert success
        assert "{FAQ_HORAIRES}" not in replaced
        assert "9h à 18h" in replaced


# ============================================================
# Test: LLM START → Booking Flow
# ============================================================

class TestLLMStartBooking:
    """Test LLM generates natural greeting then routes to booking."""

    def test_llm_start_generates_natural_then_booking(self, conversational_engine, stub_llm_client):
        """LLM returns natural text and routes to FSM_BOOKING."""
        # Configure LLM response
        stub_llm_client.set_response("rdv", '''{
            "response_text": "Bonjour ! Je serais ravi de vous aider à prendre rendez-vous. C'est à quel nom ?",
            "next_mode": "FSM_BOOKING",
            "extracted": null,
            "confidence": 0.92
        }''')

        events = conversational_engine.handle_message("conv1", "Je voudrais un rdv")

        assert len(events) == 1
        assert events[0].type == "final"
        assert "Bonjour" in events[0].text
        assert events[0].conv_state == "QUALIF_NAME"


# ============================================================
# Test: LLM FAQ with Placeholder Replacement
# ============================================================

class TestLLMFaqPlaceholder:
    """Test LLM FAQ answers with placeholder replacement."""

    def test_llm_start_faq_placeholder_replaced(self, conversational_engine, stub_llm_client, mock_faq_store):
        """LLM response with placeholder gets replaced with actual FAQ."""
        stub_llm_client.set_response("horaires", '''{
            "response_text": "Bien sûr ! {FAQ_HORAIRES} Est-ce que cela vous convient ?",
            "next_mode": "FSM_FAQ",
            "extracted": null,
            "confidence": 0.9
        }''')

        events = conversational_engine.handle_message("conv2", "Quels sont vos horaires ?")

        assert len(events) == 1
        # Placeholder should be replaced with actual hours
        assert "9h à 18h" in events[0].text
        assert "{FAQ_HORAIRES}" not in events[0].text
        assert events[0].conv_state == "FAQ_ANSWERED"


# ============================================================
# Test: Validation Rejection → Fallback
# ============================================================

class TestValidationRejection:
    """Test that invalid LLM responses trigger FSM fallback."""

    def test_llm_rejected_if_contains_digits(self, conversational_engine, stub_llm_client):
        """Response with digits triggers fallback."""
        stub_llm_client.set_response("horaires", '''{
            "response_text": "Le cabinet est ouvert de 9h à 18h",
            "next_mode": "FSM_FAQ",
            "confidence": 0.9
        }''')

        events = conversational_engine.handle_message("conv3", "horaires")

        # Should fallback to FSM
        assert "FSM fallback" in events[0].text

    def test_llm_rejected_if_unknown_placeholder(self, conversational_engine, stub_llm_client):
        """Response with unknown placeholder triggers fallback."""
        stub_llm_client.set_default_response('''{
            "response_text": "Voici notre menu : {FAQ_PIZZA}",
            "next_mode": "FSM_FAQ",
            "confidence": 0.9
        }''')

        events = conversational_engine.handle_message("conv4", "pizza")

        # Should fallback to FSM
        assert "FSM fallback" in events[0].text

    def test_llm_rejected_if_invalid_json(self, conversational_engine, stub_llm_client):
        """Invalid JSON triggers fallback."""
        stub_llm_client.set_default_response("This is not JSON at all")

        events = conversational_engine.handle_message("conv5", "test")

        assert "FSM fallback" in events[0].text


# ============================================================
# Test: Strong Intent Bypasses LLM
# ============================================================

class TestStrongIntentBypass:
    """Test that strong intents go directly to FSM."""

    def test_strong_intent_bypasses_llm(self, conversational_engine, stub_llm_client, mock_fsm_engine):
        """Cancel intent should bypass LLM entirely."""
        # Set up LLM to return something - but it shouldn't be called
        stub_llm_client.set_default_response('''{
            "response_text": "LLM was called - this is wrong!",
            "next_mode": "FSM_FAQ",
            "confidence": 0.9
        }''')

        # Track if FSM was called
        fsm_called = False
        original_handle = mock_fsm_engine.handle_message

        def tracking_handle(conv_id, user_text):
            nonlocal fsm_called
            fsm_called = True
            return original_handle(conv_id, user_text)

        mock_fsm_engine.handle_message = tracking_handle

        events = conversational_engine.handle_message("conv6", "je veux annuler mon rendez-vous")

        assert fsm_called
        assert "FSM fallback" in events[0].text


# ============================================================
# Test: Low Confidence → Fallback
# ============================================================

class TestLowConfidenceFallback:
    """Test that low confidence triggers FSM fallback."""

    def test_llm_low_confidence_fallback(self, conversational_engine, stub_llm_client):
        """Low confidence response triggers fallback."""
        stub_llm_client.set_default_response('''{
            "response_text": "Je ne suis pas certain de comprendre...",
            "next_mode": "FSM_FAQ",
            "confidence": 0.4
        }''')

        events = conversational_engine.handle_message("conv7", "quelque chose")

        # Should fallback to FSM due to low confidence
        assert "FSM fallback" in events[0].text


# ============================================================
# Test: Non-START State → Direct FSM
# ============================================================

class TestNonStartState:
    """Test that non-START states go directly to FSM."""

    def test_qualif_name_state_uses_fsm(self, conversational_engine, session_store):
        """Messages in QUALIF_NAME state should bypass conversational engine."""
        # Create session in QUALIF_NAME state
        session = session_store.get_or_create("conv8")
        session.state = "QUALIF_NAME"

        events = conversational_engine.handle_message("conv8", "Jean Dupont")

        # Should go directly to FSM
        assert "FSM fallback" in events[0].text


# ============================================================
# Test: Entity Extraction
# ============================================================

class TestEntityExtraction:
    """Test that extracted entities are applied to session."""

    def test_extracted_name_applied(self, conversational_engine, stub_llm_client, session_store):
        """Extracted name should be applied to session."""
        stub_llm_client.set_response("Martin", '''{
            "response_text": "Enchanté ! C'est pour quel type de consultation ?",
            "next_mode": "FSM_BOOKING",
            "extracted": {"name": "Martin Dupont"},
            "confidence": 0.92
        }''')

        events = conversational_engine.handle_message("conv9", "Bonjour, je suis Martin Dupont")

        session = session_store.get("conv9")
        assert session.qualif_data.name == "Martin Dupont"
        assert session.extracted_name is True


# ============================================================
# Test: Full Validation Pipeline
# ============================================================

class TestFullValidation:
    """Test full_validate function."""

    def test_full_validate_success(self):
        raw = '''{
            "response_text": "Bonjour ! Comment puis-je vous aider ?",
            "next_mode": "FSM_FALLBACK",
            "confidence": 0.85,
            "extracted": null
        }'''
        is_valid, data, reason = full_validate(raw)
        assert is_valid
        assert data is not None
        assert reason == ""

    def test_full_validate_invalid_json(self):
        is_valid, data, reason = full_validate("not json")
        assert not is_valid
        assert data is None
        assert reason == "invalid_json"

    def test_full_validate_with_digits(self):
        raw = '''{
            "response_text": "Ouvert de 9h à 18h",
            "next_mode": "FSM_FAQ",
            "confidence": 0.9
        }'''
        is_valid, data, reason = full_validate(raw)
        assert not is_valid
        assert reason == "contains_digits"


# ============================================================
# Test: Stub LLM Client
# ============================================================

class TestStubLLMClient:
    """Test StubLLMClient functionality."""

    def test_pattern_matching(self):
        client = StubLLMClient()
        client.set_response("hello", '{"test": "hello_response"}')

        result = client.complete("Hello there!", [], "START", DEFAULT_CABINET_DATA)
        assert "hello_response" in result

    def test_default_response(self):
        client = StubLLMClient()
        client.set_default_response('{"test": "default"}')

        result = client.complete("random message", [], "START", DEFAULT_CABINET_DATA)
        assert "default" in result


# ============================================================
# Test: System Prompt Building
# ============================================================

class TestSystemPrompt:
    """Test system prompt construction."""

    def test_build_system_prompt_contains_placeholders(self):
        prompt = build_system_prompt(DEFAULT_CABINET_DATA, "START")

        # Should list allowed placeholders
        assert "{FAQ_HORAIRES}" in prompt
        assert "{FAQ_ADRESSE}" in prompt

        # Should include business name
        assert "Cabinet Dupont" in prompt

        # Should include state
        assert "START" in prompt


# ============================================================
# Test: All Next Modes
# ============================================================

class TestNextModes:
    """Test all valid next_mode values."""

    def test_all_valid_modes_accepted(self):
        for mode in VALID_NEXT_MODES:
            data = {
                "response_text": "Test",
                "next_mode": mode,
                "confidence": 0.85,
            }
            is_valid, reason = validate_conv_result(data)
            assert is_valid, f"Mode {mode} should be valid, got: {reason}"
