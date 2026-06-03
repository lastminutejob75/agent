# tests/test_appointment_preference_parser.py
"""Tests parseur de préférences RDV (spec page publique UWi)."""

from datetime import date

import pytest

from backend.appointment_preference_parser import (
    parse_appointment_preferences,
    merge_appointment_preferences,
    filter_slots_by_appointment_preferences,
    build_preference_ack,
    empty_preferences,
    preferences_to_legacy_pref,
)
from backend import prompts


def _slot(day: str, hour: int, start: str):
    return prompts.SlotDisplay(
        idx=1,
        label=f"{day} {hour}h",
        slot_id=1,
        start=start,
        day=day,
        hour=hour,
    )


class TestParseNegative:
    def test_pas_le_matin(self):
        p = parse_appointment_preferences("Je ne suis pas dispo le matin")
        labels = [w["label"] for w in p["excluded_time_windows"]]
        assert "matin" in labels
        assert any(w["strength"] == "hard" for w in p["excluded_time_windows"])

    def test_rdv_pas_dispo_matin_legacy_pref(self):
        """Bug prod : ne doit pas fixer pref=matin ni préférer le matin."""
        text = "je veux un rdv mais je ne suis pas dispo le matin"
        p = parse_appointment_preferences(text)
        assert preferences_to_legacy_pref(p) == "après-midi"
        assert not any(
            w["label"] == "matin" and w["strength"] == "soft"
            for w in p["preferred_time_windows"]
        )


class TestParsePositive:
    def test_fin_de_journee(self):
        p = parse_appointment_preferences("Plutôt en fin de journée")
        assert any(
            w["label"] == "fin_de_journee" and w["start"] == "17:00" and w["end"] == "19:30"
            for w in p["preferred_time_windows"]
        )
        assert p["preferred_time_windows"][0]["strength"] == "soft"

    def test_combined_example(self):
        text = (
            "Je voudrais un rendez-vous, plutôt en fin de journée, "
            "je ne suis pas dispo le matin."
        )
        p = parse_appointment_preferences(text)
        assert any(w["label"] == "fin_de_journee" for w in p["preferred_time_windows"])
        assert any(w["label"] == "matin" for w in p["excluded_time_windows"])
        ack = build_preference_ack(p)
        assert "matin" in ack and "fin de journée" in ack


class TestHourLimits:
    def test_pas_avant_17h(self):
        p = parse_appointment_preferences("Pas avant 17h")
        assert p["earliest_time"] == "17:00"

    def test_travaille_jusqu_a_18h(self):
        p = parse_appointment_preferences("Je travaille jusqu'à 18h")
        assert p["earliest_time"] in ("18:00", "18:30") or any(
            w["label"] in ("matin", "milieu_apres_midi", "fin_apres_midi")
            for w in p["excluded_time_windows"]
        )


class TestPauseDejeuner:
    def test_pause_dejeuner(self):
        p = parse_appointment_preferences("Je peux pendant ma pause déjeuner")
        assert any(w["label"] == "pause_dejeuner" for w in p["preferred_time_windows"])
        w = next(x for x in p["preferred_time_windows"] if x["label"] == "pause_dejeuner")
        assert w["start"] == "12:00" and w["end"] == "14:00"


class TestExcludedDays:
    def test_pas_mercredi(self):
        p = parse_appointment_preferences("Pas le mercredi")
        assert "mercredi" in p["excluded_days"]


class TestFlexibilityUrgency:
    def test_flexible(self):
        p = parse_appointment_preferences("Je suis flexible")
        assert p["flexibility"] == "high"

    def test_premier_disponible(self):
        p = parse_appointment_preferences("Je prends le premier disponible")
        assert p["flexibility"] == "high"
        assert p["sorting"] == "earliest_available"


class TestSafety:
    def test_douleur_thoracique(self):
        p = parse_appointment_preferences("C'est urgent, j'ai une douleur thoracique")
        assert p["safety_required"] is True
        assert "15" in (p["safety_message"] or "")


class TestFilterSlots:
    def test_excludes_morning_slots(self):
        prefs = parse_appointment_preferences("pas le matin")
        slots = [
            _slot("mardi", 9, "2026-06-10T09:00:00"),
            _slot("mardi", 17, "2026-06-10T17:30:00"),
        ]
        out = filter_slots_by_appointment_preferences(slots, prefs)
        assert len(out) == 1
        assert out[0].hour == 17


class TestMerge:
    def test_merge_accumulates(self):
        a = parse_appointment_preferences("plutôt en fin de journée")
        b = parse_appointment_preferences("pas le matin")
        m = merge_appointment_preferences(a, b)
        assert any(w["label"] == "fin_de_journee" for w in m["preferred_time_windows"])
        assert any(w["label"] == "matin" for w in m["excluded_time_windows"])
