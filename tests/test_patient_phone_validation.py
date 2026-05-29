"""Validation stricte du format de numéro patient (anti fiches « fantômes »)."""
from __future__ import annotations

import pytest

from backend.db import is_valid_patient_phone, normalize_phone_number


@pytest.mark.parametrize(
    "value",
    [
        "0612345678",
        "06 12 34 56 78",
        "+33612345678",
        "0033612345678",
        "33612345678",
        "+447911123456",
    ],
)
def test_valid_phones(value):
    assert is_valid_patient_phone(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "",
        None,
        "06968547855555555",   # 17 chiffres — cas réel signalé
        "061234",              # trop court
        "abc",
        "06 12 34",
        "12345",
    ],
)
def test_invalid_phones(value):
    assert is_valid_patient_phone(value) is False


def test_invalid_phone_passes_through_normalize_but_is_rejected():
    # normalize_phone_number laisse passer la valeur brute…
    assert normalize_phone_number("06968547855555555") == "06968547855555555"
    # …mais la validation stricte la refuse.
    assert is_valid_patient_phone("06968547855555555") is False
