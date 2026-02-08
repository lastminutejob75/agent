# tests/test_start_guidance.py
"""Tests guidage proactif START (question ouverte : 1 clarification → 2 guidage → 3 INTENT_ROUTER)."""

import uuid
import pytest
from backend.engine import Engine
from backend.session import SessionStore
from backend.tools_faq import FaqStore


def _engine_start():
    return Engine(session_store=SessionStore(), faq_store=FaqStore(items=[]))


def test_start_je_sais_pas_clarification_not_faq_paiement():
    """« Je sais pas » à l'accueil → clarification (pas FAQ paiement/espèces/chèque)."""
    from backend.engine import create_engine
    engine = create_engine()
    conv = f"conv_jsaispas_{uuid.uuid4().hex[:8]}"
    events = engine.handle_message(conv, "je sais pas")
    assert len(events) >= 1
    text = events[0].text.lower()
    assert "chèque" not in text and "espèces" not in text and "carte bancaire" not in text
    assert "rendez-vous" in text or "question" in text or "aide" in text


def test_start_unclear_once_clarification():
    """1ère incompréhension (filler) en START → clarification générique (rendez-vous ou question)."""
    engine = _engine_start()
    conv = f"conv_guidance_1_{uuid.uuid4().hex[:8]}"
    events = engine.handle_message(conv, "euh...")
    assert len(events) == 1
    assert events[0].type == "final"
    assert events[0].conv_state == "START"
    text = events[0].text.lower()
    assert "rendez-vous" in text
    assert "question" in text
    assert "je peux vous aider" in text or "compris" in text or "qu'est-ce que je peux" in text


def test_start_unclear_twice_guidance():
    """2e incompréhension en START → guidage proactif (RDV, horaires, adresse, services)."""
    engine = _engine_start()
    conv = f"conv_guidance_2_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "euh")
    events = engine.handle_message(conv, "je sais pas")
    assert len(events) == 1
    assert events[0].type == "final"
    assert events[0].conv_state == "START"
    text = events[0].text.lower()
    assert "rendez-vous" in text
    assert "horaires" in text
    assert "adresse" in text or "services" in text


def test_start_unclear_thrice_router():
    """3e incompréhension (phrase réelle, pas filler) en START → INTENT_ROUTER (menu)."""
    engine = _engine_start()
    conv = f"conv_guidance_3_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "euh")
    engine.handle_message(conv, "hmm")
    events = engine.handle_message(conv, "autre chose")
    assert len(events) == 1
    assert events[0].type == "final"
    assert events[0].conv_state == "INTENT_ROUTER"
    assert "dites" in events[0].text.lower() or "1" in events[0].text or "2" in events[0].text


def test_start_three_fillers_transfer_direct():
    """3 fillers consécutifs en START → TRANSFERRED (transfert direct, pas INTENT_ROUTER)."""
    engine = _engine_start()
    conv = f"conv_guidance_3f_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "euh")
    engine.handle_message(conv, "euh")
    events = engine.handle_message(conv, "euh")
    assert len(events) == 1
    assert events[0].type == "final"
    assert events[0].conv_state == "TRANSFERRED"
    text = events[0].text.lower()
    assert "conseiller" in text or "pass" in text or "entends pas" in text
    # Pas le menu 1/2/3/4
    assert "dites 1" not in text and "dites 2" not in text


def test_start_booking_resets_counter():
    """Intent BOOKING en START → reset start_unclear_count, démarrage booking."""
    engine = _engine_start()
    conv = f"conv_guidance_booking_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "xyz vague")
    engine.handle_message(conv, "toujours vague")
    events = engine.handle_message(conv, "je veux un rendez-vous")
    assert len(events) == 1
    assert events[0].conv_state == "QUALIF_NAME"
    text = events[0].text.lower()
    assert "nom" in text


def test_start_faq_resets_counter():
    """FAQ match en START → reset start_unclear_count, state POST_FAQ."""
    from backend.tools_faq import FaqItem
    items = [FaqItem(faq_id="HORAIRES", question="horaires", answer="Ouvert 9h-18h.", priority="high")]
    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=items))
    conv = f"conv_guidance_faq_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "euh")
    events = engine.handle_message(conv, "quels sont vos horaires ?")
    assert len(events) == 1
    assert events[0].conv_state == "POST_FAQ"
    assert "9h" in events[0].text or "18h" in events[0].text


def test_start_guidance_web_format():
    """Guidage web → format structuré avec bullets."""
    engine = _engine_start()
    conv = f"conv_guidance_web_{uuid.uuid4().hex[:8]}"
    session = engine.session_store.get_or_create(conv)
    session.channel = "web"
    engine.handle_message(conv, "euh")
    events = engine.handle_message(conv, "hmm")
    assert len(events) == 1
    text = events[0].text
    assert "•" in text or "-" in text or "rendez-vous" in text.lower()
    assert "horaires" in text.lower()
