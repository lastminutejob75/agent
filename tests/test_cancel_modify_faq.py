# tests/test_cancel_modify_faq.py
"""
Tests recovery progressive flows CANCEL, MODIFY, FAQ.
Mission : pas de transfert direct sans 2-3 retries.
"""
import pytest
from backend.engine import create_engine


def test_cancel_name_incompris_recovery():
    """User dit 'annuler', agent demande nom, user incompréhensible 3x → INTENT_ROUTER."""
    engine = create_engine()
    conv = "t_cancel_name"
    events = engine.handle_message(conv, "annuler un rdv")
    assert "nom" in events[0].text.lower() or "quel nom" in events[0].text.lower()

    events = engine.handle_message(conv, "e")
    assert "répéter" in events[0].text.lower() or "noté" in events[0].text.lower()

    events = engine.handle_message(conv, "e")
    assert "exemple" in events[0].text.lower() or "martin" in events[0].text.lower() or "dupont" in events[0].text.lower()

    events = engine.handle_message(conv, "e")
    text = events[0].text.lower()
    assert "un" in text and ("deux" in text or "rendez" in text or "annul" in text or "question" in text or "humain" in text or "2" in events[0].text)


def test_cancel_rdv_pas_trouve_offre_alternatives():
    """RDV pas trouvé → propose de vérifier orthographe (pas transfert direct)."""
    engine = create_engine()
    conv = "t_cancel_rdv"
    engine.handle_message(conv, "annuler")
    events = engine.handle_message(conv, "Zzzinexistant")
    assert len(events) >= 1 and events[0].type == "final"
    text = events[0].text.lower()
    assert "vérifier" in text or "verifier" in text or "orthographe" in text or "humain" in text
    assert events[0].conv_state != "TRANSFERRED"


def test_modify_name_incompris_recovery():
    """Modify : nom incompris 3x → INTENT_ROUTER (même logique que cancel)."""
    engine = create_engine()
    conv = "t_modify_name"
    engine.handle_message(conv, "modifier mon rdv")
    events = engine.handle_message(conv, "x")
    assert "répéter" in events[0].text.lower() or "noté" in events[0].text.lower()
    events = engine.handle_message(conv, "x")
    assert "exemple" in events[0].text.lower() or "martin" in events[0].text.lower() or "dupont" in events[0].text.lower()
    events = engine.handle_message(conv, "x")
    text = events[0].text.lower()
    assert "un" in text and ("deux" in text or "rendez" in text or "2" in events[0].text)


def test_faq_incomprise_recovery():
    """Question FAQ incomprise → reformulation (1), puis INTENT_ROUTER (2) — pas transfert direct."""
    engine = create_engine()
    conv = "t_faq"
    events = engine.handle_message(conv, "bzzzz question bizarre")
    assert "reformuler" in events[0].text.lower() or "reformul" in events[0].text.lower() or "compris" in events[0].text.lower()

    events = engine.handle_message(conv, "bzzzz encore bizarre")
    assert events[0].conv_state == "INTENT_ROUTER"
    text = events[0].text.lower()
    assert "dites" in text and ("un" in text or "1" in text) and ("deux" in text or "2" in text or "rendez" in text)
