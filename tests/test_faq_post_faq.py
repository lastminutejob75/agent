# tests/test_faq_post_faq.py
"""
P1 : UX après FAQ — relance + disambiguation "oui" ambigu (POST_FAQ → POST_FAQ_CHOICE).
"""
import uuid
import pytest
from backend.engine import create_engine
from backend import prompts
from backend.guards import is_yes_only


# ═══════════════════════════════════════════════════════════
# Tests helper is_yes_only
# ═══════════════════════════════════════════════════════════


def test_is_yes_only_true():
    """Patterns 'oui' seul → True."""
    assert is_yes_only("oui") is True
    assert is_yes_only("ok") is True
    assert is_yes_only("d'accord") is True
    assert is_yes_only("ouais") is True
    assert is_yes_only("  oui  ") is True
    assert is_yes_only("oui.") is True


def test_is_yes_only_false():
    """Textes avec contexte → False."""
    assert is_yes_only("oui je veux un rdv") is False
    assert is_yes_only("oui l'adresse") is False
    assert is_yes_only("et l'adresse") is False
    assert is_yes_only("rendez-vous") is False
    assert is_yes_only("") is False


# ═══════════════════════════════════════════════════════════
# Tests flow POST_FAQ
# ═══════════════════════════════════════════════════════════


def test_post_faq_yes_goes_to_choice():
    """Après une réponse FAQ, si l'utilisateur dit 'oui' (ambigu) → POST_FAQ_CHOICE + disambiguation."""
    engine = create_engine()
    conv = f"conv_post_faq_yes_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Quels sont vos horaires ?")
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "POST_FAQ"
    events = engine.handle_message(conv, "oui")
    assert len(events) == 1
    assert events[0].type == "final"
    reply = (events[0].text or "").lower()
    assert "rendez-vous" in reply and "question" in reply
    session2 = engine.session_store.get(conv)
    assert session2 is not None
    assert session2.state == "POST_FAQ_CHOICE"


def test_post_faq_yes_rdv_explicit_direct_booking():
    """'Oui je veux un rendez-vous' en POST_FAQ → booking direct (pas disambiguation)."""
    engine = create_engine()
    conv = f"conv_post_faq_rdv_explicit_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Quels sont vos horaires ?")
    events = engine.handle_message(conv, "oui je veux un rendez-vous")
    assert len(events) >= 1
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state in ("QUALIF_NAME", "QUALIF_MOTIF", "QUALIF_PREF", "QUALIF_CONTACT")
    assert "nom" in (events[0].text or "").lower()


def test_post_faq_choice_rendez_vous_starts_booking():
    """En POST_FAQ_CHOICE, si l'utilisateur dit 'rendez-vous' → démarrage du flow booking (QUALIF_NAME)."""
    engine = create_engine()
    conv = f"conv_post_faq_rdv_{uuid.uuid4().hex[:8]}"
    # Mettre la session en POST_FAQ puis POST_FAQ_CHOICE
    engine.handle_message(conv, "Quels sont vos horaires ?")
    engine.handle_message(conv, "oui")
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "POST_FAQ_CHOICE"
    # User dit "rendez-vous"
    events = engine.handle_message(conv, "rendez-vous")
    assert len(events) >= 1
    session2 = engine.session_store.get(conv)
    assert session2 is not None
    assert session2.state in ("QUALIF_NAME", "QUALIF_MOTIF", "QUALIF_PREF", "QUALIF_CONTACT"), (
        f"Expected booking flow state, got {session2.state}"
    )


def test_post_faq_choice_question_routes_to_faq():
    """En POST_FAQ_CHOICE, si l'utilisateur pose une question (ex. 'et l'adresse ?') → re-FAQ (START ou POST_FAQ)."""
    engine = create_engine()
    conv = f"conv_post_faq_question_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Quels sont vos horaires ?")
    engine.handle_message(conv, "oui")
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "POST_FAQ_CHOICE"
    # User pose une question (peut matcher une FAQ ou donner une reformulation)
    events = engine.handle_message(conv, "et l'adresse ?")
    assert len(events) >= 1
    session2 = engine.session_store.get(conv)
    assert session2 is not None
    assert session2.state in ("START", "POST_FAQ", "POST_FAQ_CHOICE"), (
        f"Expected START or POST_FAQ after re-FAQ, got {session2.state}"
    )
    # Réponse doit contenir soit une info FAQ soit la relance / reformulation
    text = events[0].text or ""
    assert len(text) > 0
    assert "Source :" in text or "question" in text.lower() or "reformul" in text.lower() or "adresse" in text.lower() or "souhaitez" in text.lower()


def test_post_faq_ca_sera_tout_merci_goodbye_state_confirmed():
    """FAQ → 'ça sera tout merci' → réponse au revoir + state CONFIRMED (pas de relance rdv/horaires/adresse)."""
    engine = create_engine()
    conv = f"conv_post_faq_goodbye_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je voudrais l'adresse")
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "POST_FAQ"
    events = engine.handle_message(conv, "ça sera tout merci")
    assert len(events) == 1
    reply = (events[0].text or "").strip()
    assert "au revoir" in reply.lower() or "bonne journée" in reply.lower()
    assert reply.lower() != "ça sera tout merci"
    session2 = engine.session_store.get(conv)
    assert session2 is not None
    assert session2.state == "CONFIRMED"


def test_post_faq_abandon_lexicon_matches():
    """'ça sera tout merci' (normalisé) est détecté comme ABANDON."""
    from backend.intent_parser import detect_strong_intent, normalize_stt_text
    t = normalize_stt_text("ça sera tout merci")
    assert "ca" in t or "sera" in t
    strong = detect_strong_intent("ça sera tout merci")
    assert strong is not None
    assert strong.value == "ABANDON"
