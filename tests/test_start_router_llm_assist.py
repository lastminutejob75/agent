# tests/test_start_router_llm_assist.py
"""Anti-régression : un seul router START, pas de double décision LLM."""

import pytest
from backend.start_router import route_start, StartRoute
from backend.intent_parser import Intent


class FakeAssist:
    def __init__(self, intent, confidence, faq_bucket=None, out_of_scope_response=None):
        self.intent = intent
        self.confidence = confidence
        self.faq_bucket = faq_bucket
        self.out_of_scope_response = out_of_scope_response


def test_no_double_decision_llm_not_called_when_booking_heuristic(monkeypatch):
    """
    GIVEN phrase "voir docteur X" => heuristic BOOKING
    THEN LLM assist must not be invoked (no double router).
    """
    called = {"n": 0}

    def fake_llm_assist(**kwargs):
        called["n"] += 1
        return None

    monkeypatch.setattr("backend.llm_assist.llm_assist_classify", fake_llm_assist)

    def should_try(text, intent, strong):
        return True

    r = route_start(
        "Je demande à voir le docteur Dupont",
        state="START",
        channel="vocal",
        llm_client=object(),
        should_try_llm_assist=should_try,
        strong_intent=None,
        llm_assist_min_confidence=0.70,
    )

    assert r.intent == Intent.BOOKING
    assert called["n"] == 0


def test_llm_low_confidence_is_ignored(monkeypatch):
    """
    GIVEN parser returns UNCLEAR AND LLM says FAQ with low confidence (0.51)
    THEN route_start must ignore LLM and keep UNCLEAR (fallback parser).
    """
    monkeypatch.setattr(
        "backend.llm_assist.llm_assist_classify",
        lambda **kwargs: FakeAssist("FAQ", 0.51, faq_bucket="HORAIRES"),
    )

    def should_try(text, intent, strong):
        return True

    r = route_start(
        "blabla incompréhensible",
        state="START",
        channel="vocal",
        llm_client=object(),
        should_try_llm_assist=should_try,
        strong_intent=None,
        llm_assist_min_confidence=0.70,
    )

    assert r.intent == Intent.UNCLEAR


def test_llm_hallucination_invalid_response_is_ignored(monkeypatch):
    """
    GIVEN LLM returns None or invalid
    THEN route_start must not crash and should fallback (parser).
    """
    monkeypatch.setattr("backend.llm_assist.llm_assist_classify", lambda **kwargs: None)

    def should_try(text, intent, strong):
        return True

    r = route_start(
        "un truc bizarre",
        state="START",
        channel="vocal",
        llm_client=object(),
        should_try_llm_assist=should_try,
        strong_intent=None,
        llm_assist_min_confidence=0.70,
    )

    assert r.intent in (
        Intent.UNCLEAR,
        Intent.FAQ,
        Intent.BOOKING,
        Intent.TRANSFER,
        Intent.CANCEL,
        Intent.MODIFY,
        Intent.ABANDON,
        Intent.ORDONNANCE,
    )


def test_no_faq_path_engine_calls_handle_start_unclear_no_faq(monkeypatch):
    """
    GIVEN route_start returns UNCLEAR with no_faq=True (LLM hors-sujet)
    THEN engine must call _handle_start_unclear_no_faq (clarify), not _handle_faq.
    """
    from backend.engine import ENGINE
    from backend.start_router import StartRoute

    def fake_route_start(*args, **kwargs):
        return StartRoute(
            intent=Intent.UNCLEAR,
            confidence=0.85,
            entities={"no_faq": True, "llm_used": True},
            source="llm_assist",
        )

    monkeypatch.setattr("backend.engine.route_start", fake_route_start)

    conv_id = "test-no-faq-path"
    ENGINE.session_store.get_or_create(conv_id)
    events = ENGINE.handle_message(conv_id, "acheter une voiture")

    assert len(events) >= 1
    msg = getattr(events[0], "text", "") or ""
    assert "rendez-vous" in msg.lower() or "question" in msg.lower() or "aide" in msg.lower()
    session = ENGINE.session_store.get(conv_id)
    assert session.state == "START"
