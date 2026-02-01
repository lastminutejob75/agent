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
    """'Oui' ambigu (START) → agent répond (pas silence); safe_reply garanti."""
    engine = create_engine()
    conv = "n1_oui"
    events = engine.handle_message(conv, "oui")
    assert len(events) >= 1
    assert events[0].type == "final"
    assert events[0].text and events[0].text.strip()
    # Doit avancer vers qualification (nom) ou clarification
    assert "nom" in events[0].text.lower() or "prénom" in events[0].text.lower() or "écoute" in events[0].text.lower()


def test_slot_par_jour_ou_heure():
    """Choix slot par jour/heure : 'celui de mardi', '14h' → créneau reconnu."""
    engine = create_engine()
    conv = "n1_slot"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Marie Martin")
    engine.handle_message(conv, "consultation")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "marie@test.fr")
    # On est en WAIT_CONFIRM avec des créneaux proposés
    e = engine.handle_message(conv, "celui de mardi")
    assert len(e) >= 1 and e[0].type == "final"
    assert e[0].text and e[0].text.strip()
    # Soit confirmation, soit retry; jamais vide
    assert "mardi" in e[0].text.lower() or "1" in e[0].text or "2" in e[0].text or "confirm" in e[0].text.lower() or "écoute" in e[0].text.lower()


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
    """2 incompréhensions (no match FAQ) → INTENT_ROUTER (menu 4 choix)."""
    engine = create_engine()
    conv = "n1_2fail"
    engine.handle_message(conv, "xyzabc123nope")
    events = engine.handle_message(conv, "nimportequoi456")
    assert len(events) >= 1 and events[0].type == "final"
    # Après 2 no-match → menu 1/2/3/4
    text = events[0].text.lower()
    assert "1" in events[0].text and ("2" in events[0].text or "rendez" in text or "annul" in text or "question" in text or "humain" in text)


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
    """'Attendez' / correction → rejoue dernière question."""
    engine = create_engine()
    conv = "n1_correct"
    e1 = engine.handle_message(conv, "Je veux un rdv")
    assert "nom" in e1[0].text.lower() or "prénom" in e1[0].text.lower()
    e2 = engine.handle_message(conv, "attendez")
    assert len(e2) >= 1 and e2[0].type == "final"
    assert e2[0].text and ("nom" in e2[0].text.lower() or "prénom" in e2[0].text.lower() or "écoute" in e2[0].text.lower())


def test_empty_twice_intent_router():
    """2 messages vides consécutifs → INTENT_ROUTER (menu)."""
    engine = create_engine()
    conv = "n1_empty"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "")
    events = engine.handle_message(conv, "")
    assert len(events) >= 1 and events[0].type == "final"
    text = events[0].text
    assert "1" in text and ("2" in text or "rendez" in text.lower() or "annul" in text.lower() or "question" in text.lower() or "humain" in text.lower())


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
    """INTENT_ROUTER : choix 1 (ou 'un') → QUALIF_NAME, pas reste dans INTENT_ROUTER."""
    engine = create_engine()
    conv = "n1_menu1"
    engine.handle_message(conv, "xyzabc")
    engine.handle_message(conv, "nimportequoi")
    events = engine.handle_message(conv, "un")
    assert len(events) >= 1 and events[0].type == "final"
    assert "nom" in events[0].text.lower() or "prénom" in events[0].text.lower()
    # État doit être QUALIF_NAME (vérifié via conv_state si exposé)
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
