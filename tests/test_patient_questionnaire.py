"""Tests du module questionnaire médical patient (token, sanitize, persistance, mapping)."""
from __future__ import annotations

import pytest

import backend.db as db
import backend.patient_questionnaire as pq


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    # Pas de Postgres en test → tout passe par SQLite.
    monkeypatch.setattr(db, "_pg_events_url", lambda: None)
    return tmp_path


def test_token_roundtrip():
    token = pq.make_questionnaire_token(7, "+33612345678")
    ref = pq.parse_questionnaire_token(token)
    assert ref == {"tenant_id": 7, "phone": "+33612345678"}


def test_parse_token_invalid():
    assert pq.parse_questionnaire_token("n'importe.quoi") is None
    assert pq.parse_questionnaire_token("") is None


def test_sanitize_answers_drops_unknown_and_trims():
    clean = pq.sanitize_answers(
        {
            "allergies": "  pénicilline  ",
            "inconnu": "ignoré",
            "birth_date": "1990-05-12",
        }
    )
    assert clean == {"allergies": "pénicilline", "birth_date": "1990-05-12"}


def test_save_and_get_roundtrip(sqlite_db):
    state = pq.save_questionnaire(
        1,
        "+33611111111",
        answers={"allergies": "aucune", "main_reason": "douleur dos"},
        status=pq.STATUS_COMPLETED,
        filled_by=pq.FILLED_BY_PRACTITIONER,
        mark_completed=True,
    )
    assert state["status"] == pq.STATUS_COMPLETED
    assert state["filled_by"] == pq.FILLED_BY_PRACTITIONER
    assert state["answers"]["allergies"] == "aucune"

    again = pq.get_questionnaire(1, "+33611111111")
    assert again["answers"]["main_reason"] == "douleur dos"
    assert again["completed_at"]


def test_get_questionnaire_empty(sqlite_db):
    state = pq.get_questionnaire(1, "+33600000000")
    assert state["status"] == pq.STATUS_DRAFT
    assert state["answers"] == {}


def test_context_note_only_context_fields():
    note = pq._context_note_from_answers(
        {
            "birth_date": "1990-05-12",
            "allergies": "pollen",
            "medical_history": "asthme",
        },
        source_label="rempli par le patient",
    )
    assert "rempli par le patient" in note
    assert "pollen" in note
    assert "asthme" in note
    # La date de naissance va au profil, pas dans la note de contexte.
    assert "1990-05-12" not in note


def test_apply_answers_updates_profile_and_adds_note(sqlite_db):
    db.upsert_cabinet_client(1, "+33622222222", raw_name="Test", validated_name="Test Patient")

    pq.apply_answers_to_patient(
        1,
        "+33622222222",
        {
            "birth_date": "1985-03-04",
            "treating_physician_name": "Dr House",
            "allergies": "arachides",
        },
        source_label="rempli par le patient",
        add_context_note=True,
    )

    profile = db.get_cabinet_client_by_phone(1, "+33622222222")
    assert (profile.get("birth_date") or "").startswith("1985-03-04")
    assert profile.get("treating_physician_name") == "Dr House"

    notes = db.list_patient_notes(1, "+33622222222")
    assert any("arachides" in (n.get("note_text") or "") for n in notes)
