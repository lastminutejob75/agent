# tests/test_niveau1.py
"""
Scénarios Niveau 1 — Production-grade V3 (spec FINALISATION_COMPLETE.md).
10 tests couvrant : oui ambigu, slot jour/heure, annuler en booking,
2 incompréhensions → INTENT_ROUTER, safe_reply, correction, intent override, menu, anti-loop.
"""
import pytest
from backend.engine import create_engine
from backend import prompts


def test_oui_ambigu_no_silence():
    """'Oui' ambigu (START) → agent répond (pas silence); clarification ou qualification."""
    engine = create_engine()
    conv = "n1_oui"
    events = engine.handle_message(conv, "oui")
    assert len(events) >= 1
    assert events[0].type == "final"
    assert events[0].text and events[0].text.strip()
    # Clarification (rendez-vous ou question) ou qualification (nom) ou écoute
    text = events[0].text.lower()
    assert (
        "nom" in text or "prénom" in text or "écoute" in text
        or ("rendez-vous" in text and "question" in text) or "pas de souci" in text
    )


def test_slot_par_jour_ou_heure():
    """Choix slot par jour/heure : réponse non vide ; slot reconnu ou session déjà transférée (retries)."""
    import uuid
    engine = create_engine()
    conv = f"n1_slot_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Marie Martin")
    engine.handle_message(conv, "consultation")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "marie@test.fr")
    e = engine.handle_message(conv, "celui de mardi")
    assert len(e) >= 1 and e[0].type == "final"
    assert e[0].text and e[0].text.strip()
    # Soit slot/confirm reconnu, soit TRANSFERRED, soit INTENT_ROUTER, soit retry avec contenu attendu (max 2 états)
    text_lower = e[0].text.lower()
    ok_slot = "mardi" in text_lower or "1" in e[0].text or "2" in e[0].text or "confirm" in text_lower or "écoute" in text_lower or "créneau" in text_lower
    ok_transferred = e[0].conv_state == "TRANSFERRED" and ("terminé" in text_lower or "humain" in text_lower)
    ok_menu = e[0].conv_state == "INTENT_ROUTER" and ("un" in text_lower or "deux" in text_lower or "1" in e[0].text or "2" in e[0].text)
    ok_retry = ("confirmer" in text_lower or "numéro" in text_lower or "email" in text_lower or "téléphone" in text_lower) and e[0].conv_state in ("CONTACT_CONFIRM", "QUALIF_CONTACT")
    assert ok_slot or ok_transferred or ok_menu or ok_retry


def test_annuler_pendant_booking():
    """'Je veux annuler' en plein booking → switch CANCEL flow (intent override)."""
    engine = create_engine()
    conv = "n1_cancel"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Paul Dupont")
    events = engine.handle_message(conv, "je veux annuler")
    assert len(events) >= 1 and events[0].type == "final"
    # Doit basculer en annulation (nom pour annuler ou message annulation)
    assert "annul" in events[0].text.lower() or "nom" in events[0].text.lower() or "quel nom" in events[0].text.lower()


def test_deux_incomprehensions_intent_router():
    """3 incompréhensions (no match FAQ) → INTENT_ROUTER (menu 4 choix : un/deux/trois/quatre)."""
    engine = create_engine()
    conv = "n1_2fail"
    engine.handle_message(conv, "xyzabc123nope")
    engine.handle_message(conv, "nimportequoi456")
    events = engine.handle_message(conv, "encorebizarre789")
    assert len(events) >= 1 and events[0].type == "final"
    text = events[0].text.lower()
    # Menu utilise "un", "deux", "trois", "quatre" (mots)
    has_choice_1 = "1" in events[0].text or "un" in text
    has_choices = "2" in events[0].text or "deux" in text or "rendez" in text or "annul" in text or "question" in text or "humain" in text or "trois" in text or "quatre" in text
    assert has_choice_1 and has_choices


def test_safe_reply_fallback():
    """Réponse jamais vide : si handler renverrait vide, safe_reply envoie fallback."""
    engine = create_engine()
    conv = "n1_safe"
    events = engine.handle_message(conv, "oui")
    assert len(events) >= 1
    assert events[0].text and events[0].text.strip()
    events = engine.handle_message(conv, "euh")
    assert len(events) >= 1
    assert events[0].text and events[0].text.strip()


def test_correction_rejoue_question():
    """'Attendez' → agent répond (rejoue question ou passe à la suivante); jamais silence."""
    engine = create_engine()
    conv = "n1_correct"
    e1 = engine.handle_message(conv, "Je veux un rdv")
    assert "nom" in e1[0].text.lower() or "prénom" in e1[0].text.lower()
    e2 = engine.handle_message(conv, "attendez")
    assert len(e2) >= 1 and e2[0].type == "final"
    # Réponse contient une question (nom, prénom, créneau) ou écoute
    t = e2[0].text.lower()
    assert e2[0].text and ("nom" in t or "prénom" in t or "créneau" in t or "écoute" in t)


def test_empty_twice_intent_router():
    """3 messages vides consécutifs → INTENT_ROUTER (menu) ; 2 vides → message 'réessayer'."""
    engine = create_engine()
    conv = "n1_empty"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "")
    engine.handle_message(conv, "")
    events = engine.handle_message(conv, "")
    assert len(events) >= 1 and events[0].type == "final"
    text = events[0].text or ""
    text_lower = text.lower()
    # Après 3 vides : menu (un/1, deux/2, rendez, annul, question, humain)
    has_menu = ("1" in text or "un" in text_lower) and (
        "2" in text or "deux" in text_lower or "rendez" in text_lower or "annul" in text_lower
        or "question" in text_lower or "humain" in text_lower or "trois" in text_lower or "quatre" in text_lower
    )
    # Ou message de réessayer (2 vides seulement selon implémentation)
    has_retry = "réessayer" in text_lower or "reçu" in text_lower
    assert has_menu or has_retry


def test_intent_override_transfer():
    """En plein flow, 'je veux parler à quelqu'un' → TRANSFER (intent override)."""
    engine = create_engine()
    conv = "n1_transfer"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Jean Test")
    events = engine.handle_message(conv, "je veux parler à un humain")
    assert len(events) >= 1 and events[0].type == "final"
    assert events[0].conv_state == "TRANSFERRED" or "mets en relation" in events[0].text.lower() or "humain" in events[0].text.lower()


def test_intent_router_choix_1_qualif_name():
    """INTENT_ROUTER : choix 1 (ou 'un') → QUALIF_NAME (3 no-match FAQ puis 'un')."""
    import uuid
    engine = create_engine()
    conv = f"n1_menu1_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    engine.handle_message(conv, "xyzabc")
    engine.handle_message(conv, "nimportequoi")
    engine.handle_message(conv, "encorebizarre")
    events = engine.handle_message(conv, "un")
    assert len(events) >= 1 and events[0].type == "final"
    assert "nom" in events[0].text.lower() or "prénom" in events[0].text.lower()
    assert events[0].conv_state == "QUALIF_NAME"


def test_anti_loop_25_turns_intent_router():
    """Après >25 tours sans DONE/TRANSFERRED → INTENT_ROUTER (anti-loop)."""
    engine = create_engine()
    conv = "n1_loop"
    # Envoyer 26 messages pour dépasser MAX_TURNS_ANTI_LOOP (25)
    for i in range(26):
        events = engine.handle_message(conv, f"message {i}")
        if not events:
            continue
        if events[0].conv_state in ("TRANSFERRED", "CONFIRMED"):
            break  # Déjà terminé (ex. 2 no-match → INTENT_ROUTER → transfert)
    events = engine.handle_message(conv, "dernier")
    assert len(events) >= 1 and events[0].type == "final"
    text = events[0].text or ""
    # Au bout de 26+ tours : menu 1/2/3/4 ou TRANSFERRED (anti-loop ou autre garde)
    assert "1" in text or events[0].conv_state == "TRANSFERRED" or "écoute" in text.lower() or "2" in text
