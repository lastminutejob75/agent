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
    """Test mots français (channel vocal)"""
    ok, idx = guards.validate_booking_confirm("un", channel="vocal")
    assert ok and idx == 1

    ok, idx = guards.validate_booking_confirm("deux", channel="vocal")
    assert ok and idx == 2

    ok, idx = guards.validate_booking_confirm("trois", channel="vocal")
    assert ok and idx == 3


def test_vocal_confirmations_oui():
    """Test avec 'oui' (channel vocal)"""
    ok, idx = guards.validate_booking_confirm("oui 1", channel="vocal")
    assert ok and idx == 1

    ok, idx = guards.validate_booking_confirm("oui deux", channel="vocal")
    assert ok and idx == 2

    ok, idx = guards.validate_booking_confirm("oui trois", channel="vocal")
    assert ok and idx == 3


def test_vocal_confirmations_variantes():
    """Test variantes communes (channel vocal)"""
    ok, idx = guards.validate_booking_confirm("premier", channel="vocal")
    assert ok and idx == 1

    ok, idx = guards.validate_booking_confirm("le deuxième", channel="vocal")
    assert ok and idx == 2

    ok, idx = guards.validate_booking_confirm("troisième", channel="vocal")
    assert ok and idx == 3
    
    ok, idx = guards.validate_booking_confirm("le premier", channel="vocal")
    assert ok and idx == 1
    
    ok, idx = guards.validate_booking_confirm("le troisième", channel="vocal")
    assert ok and idx == 3
    
    ok, idx = guards.validate_booking_confirm("1er", channel="vocal")
    assert ok and idx == 1
    
    ok, idx = guards.validate_booking_confirm("le 1", channel="vocal")
    assert ok and idx == 1
    
    ok, idx = guards.validate_booking_confirm("le 2", channel="vocal")
    assert ok and idx == 2
    
    ok, idx = guards.validate_booking_confirm("le 3", channel="vocal")
    assert ok and idx == 3


def test_vocal_confirmations_invalides():
    """Test rejets"""
    ok, idx = guards.validate_booking_confirm("mardi", channel="vocal")
    assert not ok

    ok, idx = guards.validate_booking_confirm("d'accord", channel="vocal")
    assert not ok

    ok, idx = guards.validate_booking_confirm("oui", channel="vocal")
    assert not ok

    ok, idx = guards.validate_booking_confirm("le premier s'il vous plaît", channel="vocal")
    assert not ok  # Trop verbeux, pas dans mapping
    
    ok, idx = guards.validate_booking_confirm("celui de mardi", channel="vocal")
    assert not ok


def test_vocal_confirmations_normalisation():
    """Test normalisation ponctuation (channel vocal)"""
    ok, idx = guards.validate_booking_confirm("1.", channel="vocal")
    assert ok and idx == 1

    ok, idx = guards.validate_booking_confirm("deux!", channel="vocal")
    assert ok and idx == 2

    ok, idx = guards.validate_booking_confirm("Oui, trois", channel="vocal")
    assert ok and idx == 3
    
    ok, idx = guards.validate_booking_confirm("premier.", channel="vocal")
    assert ok and idx == 1
    
    ok, idx = guards.validate_booking_confirm("le deuxième!", channel="vocal")
    assert ok and idx == 2

