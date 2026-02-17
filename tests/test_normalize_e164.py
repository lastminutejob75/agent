# tests/test_normalize_e164.py
"""Tests normalisation E.164 (backend.utils.phone)."""
from __future__ import annotations

import pytest
from backend.utils.phone import normalize_e164


def test_valid_plus_digits():
    assert normalize_e164("+33612345678") == "+33612345678"


def test_spaces_stripped():
    assert normalize_e164("+33 6 12 34 56 78") == "+33612345678"


def test_whatsapp_prefix():
    assert normalize_e164("whatsapp:+33612345678") == "+33612345678"


def test_tel_prefix():
    assert normalize_e164("tel:+33612345678") == "+33612345678"


def test_sip_prefix():
    assert normalize_e164("sip:+33612345678") == "+33612345678"


def test_dashes_dots_removed():
    assert normalize_e164("+33-6-12-34-56-78") == "+33612345678"
    assert normalize_e164("+33.6.12.34.56.78") == "+33612345678"


def test_00_converted_to_plus():
    assert normalize_e164("0033612345678") == "+33612345678"


def test_empty_raises():
    with pytest.raises(ValueError) as exc:
        normalize_e164("")
    assert "Invalid E.164" in str(exc.value)


def test_no_plus_raises():
    with pytest.raises(ValueError) as exc:
        normalize_e164("0612345678")
    assert "Invalid E.164" in str(exc.value) or "must start with +" in str(exc.value)


def test_none_raises():
    with pytest.raises(ValueError):
        normalize_e164(None)


def test_too_short_raises():
    with pytest.raises(ValueError):
        normalize_e164("+123")


def test_valid_min_length():
    assert normalize_e164("+12345678") == "+12345678"
