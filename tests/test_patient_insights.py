from backend.patient_insights import (
    ABSENCE_NOTE_PREFIX,
    _count_absence_notes,
    compute_patient_insights,
)


def test_count_absence_notes_structured_and_free_text():
    notes = [
        {"note_text": f"{ABSENCE_NOTE_PREFIX} Patient absent au rendez-vous du 12/05/2026."},
        {"note_text": "Le patient n'est pas venu au rdv de mardi."},
        {"note_text": "Préfère les SMS pour les rappels."},
    ]
    assert _count_absence_notes(notes) == 2


def test_compute_patient_insights_empty(monkeypatch):
    monkeypatch.setattr(
        "backend.patient_insights.list_patient_notes",
        lambda tenant_id, phone, limit=200: [],
    )
    monkeypatch.setattr(
        "backend.patient_insights._list_patient_past_appointments",
        lambda tenant_id, phone_norm, limit=120: [],
    )
    out = compute_patient_insights(1, "+33601020304", notes=[])
    assert out["tags"] == []
    assert out["stats"]["past_appointments"] == 0
