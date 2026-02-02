# tests/test_preference.py
"""
Tests PREFERENCE_CONFIRM : inférence répétée = confirmation implicite (Bug #2).
- User répète "je finis à 17h" → agent confirme (pas transfert).
- User donne autre inférence → mise à jour.
- User incompréhensible → recovery progressive.
"""
import uuid
import pytest
from backend.engine import create_engine


def test_inference_repetee_confirmation_implicite():
    """User répète la même phrase (je finis à 17h) → confirmation implicite, pas transfert."""
    engine = create_engine()
    conv = f"pref_repeat_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Marie Martin")
    engine.handle_message(conv, "consultation")
    # Premier "je finis à 17h" → PREFERENCE_CONFIRM ("Plutôt après-midi ?")
    engine.handle_message(conv, "je finis à 17h")
    # Répétition → doit être traité comme OUI (confirmation), pas comme échec
    events = engine.handle_message(conv, "je finis à 17h")
    assert len(events) >= 1 and events[0].type == "final"
    assert events[0].conv_state != "TRANSFERRED"
    assert "passer" not in events[0].text.lower() or "quelqu'un" not in events[0].text.lower()
    # Doit avancer (contact ou créneaux)
    assert events[0].text and events[0].text.strip()


def test_inference_autre_preference_mise_a_jour():
    """User en PREFERENCE_CONFIRM (après-midi) dit une phrase qui infère matin → mise à jour."""
    engine = create_engine()
    conv = f"pref_autre_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Paul Dupont")
    # "je finis à 17h" en QUALIF_PREF → infère après-midi → PREFERENCE_CONFIRM
    engine.handle_message(conv, "je finis à 17h")
    # User change : "avant midi c'est mieux" → infère matin → mise à jour
    events = engine.handle_message(conv, "avant midi c'est mieux")
    assert len(events) >= 1 and events[0].type == "final"
    assert "matin" in events[0].text.lower()
    assert events[0].conv_state == "PREFERENCE_CONFIRM"


def test_preference_incompris_recovery():
    """User en PREFERENCE_CONFIRM dit incompréhensible → recovery (reformulation), pas transfert direct."""
    engine = create_engine()
    conv = f"pref_incomp_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Jean Martin")
    # "je finis à 17h" en QUALIF_PREF → PREFERENCE_CONFIRM ("Plutôt après-midi ?")
    engine.handle_message(conv, "je finis à 17h")
    # Premier incompréhensible → re-demande confirmation (pas transfert)
    events = engine.handle_message(conv, "euh je sais pas")
    assert len(events) >= 1 and events[0].type == "final"
    assert events[0].conv_state != "TRANSFERRED"
    # Message de reformulation ou confirmation (après-midi / matin / bien ça)
    assert "après-midi" in events[0].text.lower() or "matin" in events[0].text.lower() or "bien" in events[0].text.lower() or "créneau" in events[0].text.lower()
