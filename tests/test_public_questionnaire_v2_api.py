"""Tests API publique questionnaires V2 (/api/q/{token})."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.db as db
from backend.patient_v2_db import ensure_patient_v2_schema
from backend.questionnaire_v2 import (
    create_questionnaire_request,
    ensure_default_admin_template,
    submit_questionnaire_response,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    monkeypatch.setattr(db, "_pg_events_url", lambda: None)
    ensure_patient_v2_schema()
    from backend.main import app

    return TestClient(app)


def _setup_patient(tenant_id: int = 1, phone: str = "+33655555555"):
    db.upsert_cabinet_client(tenant_id, phone, raw_name="Jean", validated_name="Jean Dupont")
    db.update_patient_fields(
        tenant_id,
        phone,
        email="jean@example.com",
        treating_physician_name="Dr Martin",
    )
    tpl = ensure_default_admin_template(tenant_id)
    req, raw_token = create_questionnaire_request(
        tenant_id,
        phone,
        template_id=tpl["id"],
        sent_to_email="jean@example.com",
    )
    return req, raw_token, phone


def test_public_questionnaire_v2_get_prefill(client):
    _, raw_token, phone = _setup_patient()

    r = client.get(f"/api/q/{raw_token}")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["patient_name"] == "Jean Dupont"
    assert data["prefill_answers"]["confirm_email"] == "jean@example.com"
    assert data["prefill_answers"]["confirm_phone"] == phone
    assert data["prefill_answers"]["medecin_traitant"] == "Dr Martin"
    assert isinstance(data["template"]["sections_json"], list)
    field_ids = {f["field_id"] for f in data["template"]["sections_json"]}
    assert "disponibilites" in field_ids
    assert "confirm_email" in field_ids


def test_public_questionnaire_v2_submit_flow(client):
    _, raw_token, phone = _setup_patient()

    r = client.post(
        f"/api/q/{raw_token}/submit",
        json={
            "consent_given": True,
            "answers": {
                "type_demande": "suivi",
                "deja_patient": True,
                "confirm_email": "jean@example.com",
                "disponibilites": "matin",
                "consentement": True,
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["is_health"] is False
    assert body["response_id"]
    assert body["ai_summary"]

    r2 = client.get(f"/api/q/{raw_token}")
    assert r2.status_code == 404

    notes = db.list_patient_notes(1, phone)
    assert any("Formulaire administratif complété" in (n.get("note_text") or "") for n in notes)


def test_public_questionnaire_v2_submit_requires_consent(client):
    _, raw_token, _ = _setup_patient()

    r = client.post(
        f"/api/q/{raw_token}/submit",
        json={
            "consent_given": False,
            "answers": {
                "type_demande": "suivi",
                "deja_patient": True,
                "consentement": True,
            },
        },
    )
    assert r.status_code == 400


def test_public_questionnaire_v2_invalid_token(client):
    r = client.get("/api/q/not-a-valid-token")
    assert r.status_code == 404
