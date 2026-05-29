"""Test du flux public questionnaire patient (token → GET schéma → POST soumission → mapping)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.db as db
import backend.patient_questionnaire as pq


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    monkeypatch.setattr(db, "_pg_events_url", lambda: None)
    from backend.main import app

    return TestClient(app)


def test_public_questionnaire_flow(client):
    db.upsert_cabinet_client(1, "+33655555555", raw_name="Jean", validated_name="Jean Dupont")
    token = pq.make_questionnaire_token(1, "+33655555555")

    r = client.get(f"/api/public/patient-questionnaire/{token}")
    assert r.status_code == 200
    data = r.json()
    assert data["patient_name"] == "Jean Dupont"
    assert isinstance(data["schema"], list) and len(data["schema"]) > 0
    assert data["already_completed"] is False

    r2 = client.post(
        f"/api/public/patient-questionnaire/{token}",
        json={"answers": {"birth_date": "1980-01-02", "allergies": "iode"}},
    )
    assert r2.status_code == 200
    assert r2.json()["ok"] is True

    # Mapping appliqué : profil + contexte.
    profile = db.get_cabinet_client_by_phone(1, "+33655555555")
    assert (profile.get("birth_date") or "").startswith("1980-01-02")
    notes = db.list_patient_notes(1, "+33655555555")
    assert any("iode" in (n.get("note_text") or "") for n in notes)

    # Le questionnaire est marqué complété (rempli par le patient).
    state = pq.get_questionnaire(1, "+33655555555")
    assert state["status"] == pq.STATUS_COMPLETED
    assert state["filled_by"] == pq.FILLED_BY_PATIENT


def test_public_questionnaire_prefills_from_existing_fiche(client):
    db.upsert_cabinet_client(1, "+33677777777", raw_name="Marie", validated_name="Marie Curie")
    db.update_patient_fields(
        1,
        "+33677777777",
        birth_date="1867-11-07",
        treating_physician_name="Dr Becquerel",
    )
    token = pq.make_questionnaire_token(1, "+33677777777")

    r = client.get(f"/api/public/patient-questionnaire/{token}")
    assert r.status_code == 200
    answers = r.json()["answers"]
    assert answers.get("birth_date") == "1867-11-07"
    assert answers.get("treating_physician_name") == "Dr Becquerel"


def test_public_questionnaire_invalid_token(client):
    r = client.get("/api/public/patient-questionnaire/bad.token.value")
    assert r.status_code == 404
