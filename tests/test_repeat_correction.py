"""
Tests distinction CORRECTION (rejouer question) vs RÉPÉTITION (répéter message).
"""
import pytest
from backend.engine import create_engine, detect_user_intent_repeat


# ═══════════════════════════════════════════════════════════════
# Détection
# ═══════════════════════════════════════════════════════════════

def test_repeat_vs_correction_detection():
    """Tester distinction repeat vs correction."""
    assert detect_user_intent_repeat("attendez") == "correction"
    assert detect_user_intent_repeat("erreur") == "correction"
    assert detect_user_intent_repeat("je me suis trompé") == "correction"
    assert detect_user_intent_repeat("pas ça") == "correction"

    assert detect_user_intent_repeat("vous pouvez répéter ?") == "repeat"
    assert detect_user_intent_repeat("j'ai pas compris") == "repeat"
    assert detect_user_intent_repeat("pouvez-vous répéter") == "repeat"
    assert detect_user_intent_repeat("pardon") == "repeat"

    assert detect_user_intent_repeat("oui") is None
    assert detect_user_intent_repeat("Martin Dupont") is None
    assert detect_user_intent_repeat("") is None


# ═══════════════════════════════════════════════════════════════
# Répétition pendant le flow (répéter dernier message)
# ═══════════════════════════════════════════════════════════════

def test_repeat_during_booking():
    """User demande répétition après un message agent → on répète le même message (pas repart au début)."""
    engine = create_engine()
    conv = "t_repeat_1"
    # Amener à un message agent (ex: demande du nom)
    events = engine.handle_message(conv, "je veux un rendez-vous")
    assert events
    first_message = events[0].text
    assert "nom" in first_message.lower() or "quel" in first_message.lower()

    # User demande répétition
    events = engine.handle_message(conv, "vous pouvez répéter ?")
    assert events
    # Doit répéter le même message (demande du nom)
    assert events[0].text == first_message


def test_repeat_after_faq():
    """Après une réponse FAQ, 'répéter' renvoie la même réponse."""
    engine = create_engine()
    conv = "t_repeat_faq"
    # Question FAQ (selon les items chargés, sinon no-match → reformulation)
    events = engine.handle_message(conv, "quels sont les horaires ?")
    assert events
    faq_message = events[0].text

    events = engine.handle_message(conv, "j'ai pas compris, vous pouvez répéter ?")
    assert events
    assert events[0].text == faq_message


# ═══════════════════════════════════════════════════════════════
# Correction pendant le flow (rejouer dernière question)
# ═══════════════════════════════════════════════════════════════

def test_correction_during_booking():
    """User dit 'attendez' → agent rejoue la dernière question (ex: préférence ou nom)."""
    engine = create_engine()
    conv = "t_correction_1"
    engine.handle_message(conv, "je veux un rdv")
    engine.handle_message(conv, "Jean Dupont")
    # Agent demande préférence (ou motif selon flow)
    events = engine.handle_message(conv, "euh")
    assert events
    # Au moins une question posée (retry ou question)
    question_message = events[0].text

    events = engine.handle_message(conv, "attendez")
    assert events
    # Doit rejouer la dernière question (préférence / nom / motif)
    replayed = events[0].text.lower()
    assert "matin" in replayed or "après-midi" in replayed or "nom" in replayed or "préférez" in replayed or "exemple" in replayed or "créneau" in replayed
