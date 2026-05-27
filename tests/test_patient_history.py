from backend.patient_history import build_patient_history


def test_build_patient_history_from_notes_and_docs():
    notes = [
        {
            "id": 1,
            "note_text": "[ABSENCE-RDV] Patient absent au rendez-vous du 12/05/2026.",
            "author": "Praticien",
            "created_at": "2026-05-12T08:47:00+00:00",
        }
    ]
    docs = [
        {
            "id": 2,
            "original_name": "assurance.pdf",
            "created_at": "2026-05-10T11:05:00+00:00",
        }
    ]
    out = build_patient_history(
        1,
        "+33601020304",
        calls=[],
        handoffs=[],
        notes=notes,
        documents=docs,
        limit=10,
    )
    kinds = [row["kind"] for row in out["items"]]
    assert "note" in kinds
    assert "document" in kinds
    assert out["items"][0]["date_label"]
