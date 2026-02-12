# tests/test_contact_parser.py
"""Tests P0 contact vocal : extract_phone, extract_email, detect_channel."""

import pytest
from backend.contact_parser import (
    extract_phone_digits_vocal,
    extract_email_vocal,
    detect_contact_channel,
    normalize_stt_text,
)


# ============================================
# extract_phone_digits_vocal
# ============================================

def test_phone_zerosix_digits():
    """zéro six douze trente-quatre... → OK"""
    digits, conf, partial = extract_phone_digits_vocal("zéro six douze trente-quatre cinquante-six soixante-dix huit")
    assert len(digits) >= 9
    assert conf >= 0.5


def test_phone_already_digits():
    """06 12 34 56 78 → OK"""
    digits, conf, partial = extract_phone_digits_vocal("06 12 34 56 78")
    assert digits == "0612345678" or len(digits) == 10
    assert conf >= 0.95
    assert partial is False


def test_phone_double_six():
    """double six → 66"""
    digits, conf, partial = extract_phone_digits_vocal("zéro six double six douze trente-quatre cinquante-six soixante-dix huit")
    assert "66" in digits or digits.count("6") >= 2


def test_phone_empty():
    """Chaîne vide → (\"\", 0.0, False)"""
    digits, conf, partial = extract_phone_digits_vocal("")
    assert digits == ""
    assert conf == 0.0
    assert partial is False


def test_phone_partial():
    """Moins de 10 chiffres → is_partial True"""
    digits, conf, partial = extract_phone_digits_vocal("zéro six douze")
    assert len(digits) < 10
    assert partial is True


# ============================================
# extract_email_vocal
# ============================================

def test_email_simple():
    """prenom point nom arobase gmail point com → OK"""
    email, conf = extract_email_vocal("prenom point nom arobase gmail point com")
    assert email is not None
    assert "@" in email
    assert "gmail" in email
    assert conf >= 0.7


def test_email_arobase_at():
    """arobase et at supportés"""
    email1, _ = extract_email_vocal("jean arobase gmail point com")
    email2, _ = extract_email_vocal("jean at gmail dot com")
    assert email1 == "jean@gmail.com"
    assert email2 == "jean@gmail.com"


def test_email_tiret_underscore():
    """tiret et underscore supportés"""
    email, _ = extract_email_vocal("jean tiret dupont arobase domain point fr")
    assert email == "jean-dupont@domain.fr"


def test_email_invalid_no_arobase():
    """Pas d'arobase → invalide"""
    email, conf = extract_email_vocal("jean gmail point com")
    assert email is None
    assert conf == 0.0


def test_email_invalid_empty():
    """Chaîne vide → invalide"""
    email, conf = extract_email_vocal("")
    assert email is None
    assert conf == 0.0


# ============================================
# detect_contact_channel
# ============================================

def test_channel_mail():
    """envoyez-moi un mail → email"""
    assert detect_contact_channel("envoyez-moi un mail") == "email"


def test_channel_appelez():
    """appelez-moi → phone"""
    assert detect_contact_channel("appelez-moi") == "phone"


def test_channel_digits():
    """9+ digits sans @ → phone"""
    assert detect_contact_channel("06 12 34 56 78") == "phone"


def test_channel_dictated_email():
    """Pattern email dicté → email"""
    assert detect_contact_channel("jean arobase gmail point com") == "email"


def test_channel_none():
    """Texte ambigu → None"""
    assert detect_contact_channel("") is None


# ============================================
# normalize_stt_text
# ============================================

def test_normalize_stt():
    """Normalisation de base"""
    assert normalize_stt_text("  bonjour   ") == "bonjour"
    assert normalize_stt_text("") == ""


# ============================================
# P0 : confirmation unique format
# ============================================

def test_phone_confirmation_format():
    """Confirmation : « Je récapitule : 06 12 34 56 78. C'est correct ? »"""
    digits, _, _ = extract_phone_digits_vocal("06 12 34 56 78")
    assert len(digits) == 10
    formatted = " ".join([digits[i:i+2] for i in range(0, 10, 2)])
    assert "06" in formatted and "12" in formatted


def test_email_invalid_then_guidance():
    """Email invalide (pas d'arobase) → extract_email_vocal retourne None"""
    email, conf = extract_email_vocal("jean gmail point com")
    assert email is None
    assert conf == 0.0


def test_correction_non_redemande():
    """Simulation : 'non' en CONTACT_CONFIRM → engine redemande (testé via intent NO)"""
    from backend.intent_parser import detect_intent
    assert detect_intent("non", "CONTACT_CONFIRM").value == "NO"
