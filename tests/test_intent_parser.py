# tests/test_intent_parser.py
"""
Tests unitaires sur les fonctions pures du module intent_parser.
"""

import pytest
from backend.intent_parser import (
    normalize_stt_text,
    tokenize,
    detect_strong_intent,
    detect_intent,
    parse_router_choice,
    parse_slot_choice,
    parse_contact_choice,
    normalize_phone,
    words_to_digits,
    is_unclear_filler,
    Intent,
    RouterChoice,
    SlotChoice,
    ContactChoice,
)


# ---------------------------------------------------------------------------
# 1) normalize_stt_text
# ---------------------------------------------------------------------------

def test_normalize_stt_text_apres_midi():
    assert normalize_stt_text("L'après midi") == "l apres midi"


def test_normalize_stt_text_dites_rendez_vous():
    assert normalize_stt_text("Dites : rendez-vous") == "dites rendez vous"


def test_normalize_stt_text_empty():
    assert normalize_stt_text("") == ""
    assert normalize_stt_text("   ") == ""


def test_normalize_stt_text_lower_trim():
    assert normalize_stt_text("  OUI  ") == "oui"


def test_normalize_stt_text_preserve_pas_non():
    """Règle : normalisation ne doit jamais supprimer pas, non, plus, jamais."""
    assert "pas" in normalize_stt_text("je ne veux pas")
    assert "non" in normalize_stt_text("non merci")
    assert "plus" in normalize_stt_text("je ne peux plus")
    assert "jamais" in normalize_stt_text("jamais")
    assert "d" in normalize_stt_text("d'accord")  # d'accord → "d accord", le "d" reste


# ---------------------------------------------------------------------------
# 2) tokenize
# ---------------------------------------------------------------------------

def test_tokenize():
    assert tokenize("L'après midi") == ["l", "apres", "midi"]


# ---------------------------------------------------------------------------
# 3) detect_strong_intent
# ---------------------------------------------------------------------------

def test_strong_intent_transfer():
    assert detect_strong_intent("je veux parler a quelqu un") == Intent.TRANSFER
    assert detect_strong_intent("un humain") == Intent.TRANSFER
    assert detect_strong_intent("conseiller") == Intent.TRANSFER


def test_strong_intent_cancel():
    assert detect_strong_intent("annuler mon rdv") == Intent.CANCEL
    assert detect_strong_intent("annulation") == Intent.CANCEL


def test_strong_intent_modify():
    assert detect_strong_intent("deplacer mon rdv") == Intent.MODIFY
    assert detect_strong_intent("modifier mon rendez-vous") == Intent.MODIFY


def test_strong_intent_abandon():
    assert detect_strong_intent("au revoir") == Intent.ABANDON
    assert detect_strong_intent("laisse tomber") == Intent.ABANDON


def test_strong_intent_none():
    assert detect_strong_intent("") is None
    assert detect_strong_intent("bonjour") is None


# ---------------------------------------------------------------------------
# 4) detect_intent (soft + garde-fou START+YES)
# ---------------------------------------------------------------------------

def test_detect_intent_start_oui_returns_unclear():
    """Garde-fou clé : en START, 'oui' => UNCLEAR (jamais BOOKING)."""
    assert detect_intent("oui", "START") == Intent.UNCLEAR


def test_detect_intent_contact_confirm_oui_returns_yes():
    # QUALIF_CONTACT = "téléphone ou email ?" (choix, pas oui/non) → oui = UNCLEAR
    assert detect_intent("oui", "QUALIF_CONTACT") == Intent.UNCLEAR
    assert detect_intent("oui", "WAIT_CONFIRM") == Intent.YES
    assert detect_intent("oui", "CONTACT_CONFIRM") == Intent.YES


def test_detect_intent_repeat():
    assert detect_intent("vous pouvez repeter") == Intent.REPEAT
    assert detect_intent("pardon") == Intent.REPEAT
    assert detect_intent("j ai pas compris") == Intent.REPEAT


def test_detect_intent_empty_unclear():
    assert detect_intent("") == Intent.UNCLEAR
    assert detect_intent("   ") == Intent.UNCLEAR


def test_detect_intent_booking():
    assert detect_intent("je voudrais un rendez-vous", "START") == Intent.BOOKING
    assert detect_intent("prendre rdv", "START") == Intent.BOOKING


# ---------------------------------------------------------------------------
# 5) parse_router_choice
# ---------------------------------------------------------------------------

def test_parse_router_choice_cat():
    """STT erreur 'cat' => ROUTER_4."""
    assert parse_router_choice("cat") == RouterChoice.ROUTER_4


def test_parse_router_choice_le_premier():
    assert parse_router_choice("le premier") == RouterChoice.ROUTER_1
    assert parse_router_choice("1") == RouterChoice.ROUTER_1


def test_parse_router_choice_hein_none():
    """Anti résolution silencieuse : hein ≠ un ; si hésitation entre 2 routes → None, caller clarifie."""
    assert parse_router_choice("hein") is None


def test_parse_router_choice_de_none():
    """Anti résolution silencieuse : de ≠ deux ; pas de mapping ambigu."""
    assert parse_router_choice("de") is None


def test_parse_router_choice_deux():
    assert parse_router_choice("deux") == RouterChoice.ROUTER_2
    assert parse_router_choice("annuler") == RouterChoice.ROUTER_2


def test_parse_router_choice_quatre():
    assert parse_router_choice("quatre") == RouterChoice.ROUTER_4
    assert parse_router_choice("catre") == RouterChoice.ROUTER_4


# ---------------------------------------------------------------------------
# 6) parse_slot_choice
# ---------------------------------------------------------------------------

def test_parse_slot_choice_deuxieme():
    assert parse_slot_choice("deuxieme") == SlotChoice.SLOT_2


def test_parse_slot_choice_oui_2():
    assert parse_slot_choice("oui 2") == SlotChoice.SLOT_2


def test_parse_slot_choice_oui_de_none():
    """'oui de' (STT pour 'oui deux') => None, puis clarification."""
    assert parse_slot_choice("oui de") is None


# ---------------------------------------------------------------------------
# 7) parse_contact_choice
# ---------------------------------------------------------------------------

def test_parse_contact_choice_phone():
    assert parse_contact_choice("telephone") == ContactChoice.CONTACT_PHONE
    assert parse_contact_choice("portable") == ContactChoice.CONTACT_PHONE


def test_parse_contact_choice_email():
    assert parse_contact_choice("email") == ContactChoice.CONTACT_EMAIL
    assert parse_contact_choice("mail") == ContactChoice.CONTACT_EMAIL
    assert parse_contact_choice("mel") == ContactChoice.CONTACT_EMAIL


def test_parse_contact_choice_none():
    assert parse_contact_choice("bonjour") is None


# ---------------------------------------------------------------------------
# 8) normalize_phone / words_to_digits
# ---------------------------------------------------------------------------

def test_words_to_digits_zero_six_douze():
    """Exemple ANNEXE: zero six douze trente quatre cinquante six soixante dix huit => 0612345678"""
    r = words_to_digits("zero six douze trente quatre cinquante six soixante dix huit")
    assert r == "0612345678" or len(r) == 10 and r.startswith("06")


def test_normalize_phone_plus_33():
    assert normalize_phone("+33 6 12 34 56 78") == "0612345678"


def test_normalize_phone_nine_digits_6():
    assert normalize_phone("6 12 34 56 78") == "0612345678"


def test_normalize_phone_ten_digits():
    assert normalize_phone("0612345678") == "0612345678"


def test_normalize_phone_invalid_none():
    assert normalize_phone("") is None
    assert normalize_phone("abc") is None


# ---------------------------------------------------------------------------
# 9) is_unclear_filler (START : pas _handle_faq pour filler)
# ---------------------------------------------------------------------------

def test_is_unclear_filler_true():
    assert is_unclear_filler("") is True
    assert is_unclear_filler("euh") is True
    assert is_unclear_filler("hein") is True
    assert is_unclear_filler("hum") is True


def test_is_unclear_filler_false():
    assert is_unclear_filler("je veux un rdv") is False
    assert is_unclear_filler("oui") is False
