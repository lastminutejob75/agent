# tests/test_slot_choice.py
"""Tests pour le choix de créneau non ambigu (early commit)."""
import pytest
from backend.slot_choice import detect_slot_choice_early, detect_slot_choice_by_datetime


def test_early_commit_oui_1():
    assert detect_slot_choice_early("oui 1") == 1
    assert detect_slot_choice_early("Oui 1") == 1
    assert detect_slot_choice_early("oui un") == 1


def test_early_commit_le_premier():
    assert detect_slot_choice_early("le premier") == 1
    assert detect_slot_choice_early("Le premier") == 1
    assert detect_slot_choice_early("premier") == 1
    assert detect_slot_choice_early("1") == 1
    assert detect_slot_choice_early("un") == 1
    assert detect_slot_choice_early("le 1") == 1


def test_early_commit_2_and_3():
    assert detect_slot_choice_early("2") == 2
    assert detect_slot_choice_early("deux") == 2
    assert detect_slot_choice_early("le deuxième") == 2
    assert detect_slot_choice_early("oui 2") == 2
    assert detect_slot_choice_early("3") == 3
    assert detect_slot_choice_early("trois") == 3
    assert detect_slot_choice_early("le troisième") == 3
    assert detect_slot_choice_early("oui 3") == 3


def test_early_commit_choix_option_creneau_numero():
    """choix 1, option 2, créneau 3, numero 1, n° 2."""
    assert detect_slot_choice_early("choix 1") == 1
    assert detect_slot_choice_early("option 2") == 2
    assert detect_slot_choice_early("créneau 3") == 3
    assert detect_slot_choice_early("numero 1") == 1
    assert detect_slot_choice_early("numéro 2") == 2
    assert detect_slot_choice_early("n° 2") == 2
    assert detect_slot_choice_early("n 1") == 1


def test_no_early_commit_ambiguous_oui():
    """'oui' seul = ambigu, pas de choix."""
    assert detect_slot_choice_early("oui") is None
    assert detect_slot_choice_early("Oui") is None
    assert detect_slot_choice_early("ouais") is None
    assert detect_slot_choice_early("ok") is None
    assert detect_slot_choice_early("d'accord") is None
    assert detect_slot_choice_early("parfait") is None


def test_no_early_commit_ambiguous_ce_creneau():
    """'je veux ce créneau' = ambigu (sans numéro)."""
    assert detect_slot_choice_early("je veux ce créneau") is None
    assert detect_slot_choice_early("oui je veux ce créneau") is None
    assert detect_slot_choice_early("je prends vendredi") is None
    assert detect_slot_choice_early("celui-là") is None


# ---------- P0.5 : Faux positifs (chiffre en phrase sans marqueur) ----------


def test_no_early_commit_false_positive_phrase_with_digit():
    """Chiffre dans une phrase sans marqueur de choix -> None."""
    assert detect_slot_choice_early("j'ai 2 questions") is None
    assert detect_slot_choice_early("je veux 3 rendez-vous") is None
    assert detect_slot_choice_early("mon numero c'est 06 12 34 56 78") is None
    assert detect_slot_choice_early("il y a 1 place") is None


# ---------- P0.5 : Jour + heure (match unique) ----------


def _make_slot(idx: int, day: str, hour: int, label: str = ""):
    return type("Slot", (), {"idx": idx, "day": day, "hour": hour, "label": label or f"{day} {hour}h", "start": ""})()


def test_detect_slot_choice_by_datetime_unique_match():
    """pending_slots = [vendredi 14h, lundi 9h, mardi 16h] -> 'vendredi 14h' retourne 1."""
    slots = [
        _make_slot(1, "vendredi", 14, "Vendredi 05/02 - 14:00"),
        _make_slot(2, "lundi", 9, "Lundi 09/02 - 09:00"),
        _make_slot(3, "mardi", 16, "Mardi 10/02 - 16:00"),
    ]
    assert detect_slot_choice_by_datetime("vendredi 14h", slots) == 1
    assert detect_slot_choice_by_datetime("vendredi à 14h", slots) == 1
    assert detect_slot_choice_by_datetime("vendredi 14:00", slots) == 1
    assert detect_slot_choice_by_datetime("lundi 9h", slots) == 2
    assert detect_slot_choice_by_datetime("mardi 16h", slots) == 3


def test_detect_slot_choice_by_datetime_ambiguous_refused():
    """Jour seul ou heure seule -> None. Deux slots même jour+heure -> None."""
    slots = [
        _make_slot(1, "vendredi", 14, "Vendredi 05/02 - 14:00"),
        _make_slot(2, "lundi", 9, "Lundi 09/02 - 09:00"),
        _make_slot(3, "mardi", 16, "Mardi 10/02 - 16:00"),
    ]
    assert detect_slot_choice_by_datetime("vendredi", slots) is None
    assert detect_slot_choice_by_datetime("14h", slots) is None
    # Deux slots vendredi 14h (simulé) -> None
    slots_dup = [
        _make_slot(1, "vendredi", 14),
        _make_slot(2, "vendredi", 14),
        _make_slot(3, "mardi", 16),
    ]
    assert detect_slot_choice_by_datetime("vendredi 14h", slots_dup) is None


def test_early_commit_with_pending_slots_vendredi_14h():
    """detect_slot_choice_early avec pending_slots : 'vendredi 14h' -> 1."""
    slots = [
        _make_slot(1, "vendredi", 14),
        _make_slot(2, "lundi", 9),
        _make_slot(3, "mardi", 16),
    ]
    assert detect_slot_choice_early("vendredi 14h", slots) == 1
    assert detect_slot_choice_early("vendredi 14h", None) is None
