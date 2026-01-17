# tests/test_vocal_confirmations.py
"""Tests pour les confirmations vocales (un, deux, trois)"""

import pytest
from backend import guards


def test_vocal_confirmations_chiffres():
    """Test chiffres simples"""
    ok, idx = guards.validate_booking_confirm("1")
    assert ok and idx == 1

    ok, idx = guards.validate_booking_confirm("2")
    assert ok and idx == 2

    ok, idx = guards.validate_booking_confirm("3")
    assert ok and idx == 3


def test_vocal_confirmations_mots():
    """Test mots français"""
    ok, idx = guards.validate_booking_confirm("un")
    assert ok and idx == 1

    ok, idx = guards.validate_booking_confirm("deux")
    assert ok and idx == 2

    ok, idx = guards.validate_booking_confirm("trois")
    assert ok and idx == 3


def test_vocal_confirmations_oui():
    """Test avec 'oui'"""
    ok, idx = guards.validate_booking_confirm("oui 1")
    assert ok and idx == 1

    ok, idx = guards.validate_booking_confirm("oui deux")
    assert ok and idx == 2

    ok, idx = guards.validate_booking_confirm("oui trois")
    assert ok and idx == 3


def test_vocal_confirmations_variantes():
    """Test variantes communes"""
    ok, idx = guards.validate_booking_confirm("premier")
    assert ok and idx == 1

    ok, idx = guards.validate_booking_confirm("le deuxième")
    assert ok and idx == 2

    ok, idx = guards.validate_booking_confirm("troisième")
    assert ok and idx == 3
    
    ok, idx = guards.validate_booking_confirm("le premier")
    assert ok and idx == 1
    
    ok, idx = guards.validate_booking_confirm("le troisième")
    assert ok and idx == 3
    
    ok, idx = guards.validate_booking_confirm("1er")
    assert ok and idx == 1
    
    ok, idx = guards.validate_booking_confirm("le 1")
    assert ok and idx == 1
    
    ok, idx = guards.validate_booking_confirm("le 2")
    assert ok and idx == 2
    
    ok, idx = guards.validate_booking_confirm("le 3")
    assert ok and idx == 3


def test_vocal_confirmations_invalides():
    """Test rejets"""
    ok, idx = guards.validate_booking_confirm("mardi")
    assert not ok

    ok, idx = guards.validate_booking_confirm("d'accord")
    assert not ok

    ok, idx = guards.validate_booking_confirm("oui")
    assert not ok

    ok, idx = guards.validate_booking_confirm("le premier s'il vous plaît")
    assert not ok  # Trop verbeux, pas dans mapping
    
    ok, idx = guards.validate_booking_confirm("celui de mardi")
    assert not ok


def test_vocal_confirmations_normalisation():
    """Test normalisation ponctuation"""
    ok, idx = guards.validate_booking_confirm("1.")
    assert ok and idx == 1

    ok, idx = guards.validate_booking_confirm("deux!")
    assert ok and idx == 2

    ok, idx = guards.validate_booking_confirm("Oui, trois")
    assert ok and idx == 3
    
    ok, idx = guards.validate_booking_confirm("premier.")
    assert ok and idx == 1
    
    ok, idx = guards.validate_booking_confirm("le deuxième!")
    assert ok and idx == 2

