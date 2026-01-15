# tests/test_vocal_mapping.py

import pytest
from backend.guards import (
    validate_booking_confirm,
    parse_vocal_choice_1_3,
    parse_vocal_email_min,
    looks_like_dictated_email,
)


# ============================================
# Tests confirmation vocale
# ============================================

def test_vocal_choice_simple():
    """Test mots français basiques"""
    assert parse_vocal_choice_1_3("un") == 1
    assert parse_vocal_choice_1_3("deux") == 2
    assert parse_vocal_choice_1_3("trois") == 3


def test_vocal_choice_oui():
    """Test avec oui"""
    assert parse_vocal_choice_1_3("oui un") == 1
    assert parse_vocal_choice_1_3("oui deux") == 2
    assert parse_vocal_choice_1_3("oui trois") == 3


def test_vocal_choice_ordinaux():
    """Test ordinaux"""
    assert parse_vocal_choice_1_3("premier") == 1
    assert parse_vocal_choice_1_3("le premier") == 1
    assert parse_vocal_choice_1_3("deuxième") == 2
    assert parse_vocal_choice_1_3("le deuxième") == 2
    assert parse_vocal_choice_1_3("troisième") == 3


def test_vocal_choice_numero():
    """Test numéro"""
    assert parse_vocal_choice_1_3("numéro 1") == 1
    assert parse_vocal_choice_1_3("numero 2") == 2
    assert parse_vocal_choice_1_3("numéro trois") == 3


def test_vocal_choice_accents():
    """Test normalisation accents"""
    assert parse_vocal_choice_1_3("première") == 1
    assert parse_vocal_choice_1_3("deuxieme") == 2  # Sans accent


def test_vocal_choice_invalides():
    """Test rejets"""
    assert parse_vocal_choice_1_3("quatre") is None
    assert parse_vocal_choice_1_3("mardi") is None
    assert parse_vocal_choice_1_3("d'accord") is None


def test_validate_confirm_web():
    """Test validation web strict"""
    assert validate_booking_confirm("1", "web") == (True, 1)
    assert validate_booking_confirm("oui 2", "web") == (True, 2)
    assert validate_booking_confirm("deux", "web") == (False, None)


def test_validate_confirm_vocal():
    """Test validation vocal élargi"""
    assert validate_booking_confirm("1", "vocal") == (True, 1)
    assert validate_booking_confirm("deux", "vocal") == (True, 2)
    assert validate_booking_confirm("oui trois", "vocal") == (True, 3)
    assert validate_booking_confirm("le deuxième", "vocal") == (True, 2)


# ============================================
# Tests email vocal
# ============================================

def test_parse_email_simple():
    assert parse_vocal_email_min("jean arobase gmail point com") == "jean@gmail.com"


def test_parse_email_complex():
    assert parse_vocal_email_min("jean point dupont arobase gmail point com") == "jean.dupont@gmail.com"


def test_looks_dictated():
    assert looks_like_dictated_email("jean arobase gmail point com") is True
    assert looks_like_dictated_email("jean@gmail.com") is False
