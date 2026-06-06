"""Tests V2 : questionnaires typés, is_health, résumé patient."""

from __future__ import annotations

import pytest

from backend.patient_v2_db import ensure_patient_v2_schema
from backend.questionnaire_v2 import (
    ADMIN_TYPE_DEMANDE_OPTIONS,
    compute_response_is_health,
    create_questionnaire_request,
    default_admin_template,
    default_medical_template,
    ensure_default_admin_template,
    ensure_default_medical_template,
    expire_stale_questionnaire_requests,
    get_questionnaire_response,
    integrate_response,
    prefill_public_answers,
    public_questionnaire_payload,
    submit_questionnaire_response,
    validate_answers_against_template,
    validate_template_fields,
    _questionnaire_ai_summary,
)
from backend.services.context_providers import SanteProvider, build_context_pack
from backend.services.patient_summary import _inputs_hash, get_or_generate_summary
from backend.tenant_capabilities import RequesterContext


@pytest.fixture(autouse=True)
def _schema():
    ensure_patient_v2_schema()


def test_default_admin_template_rejects_health_fields_without_hds():
    tpl = default_admin_template()
    validate_template_fields(tpl["sections_json"], hds_active=False)
    bad = tpl["sections_json"] + [
        {"field_id": "symptomes", "label": "Symptômes", "type": "text", "sensitivity": "health", "required": False}
    ]
    with pytest.raises(ValueError, match="santé"):
        validate_template_fields(bad, hds_active=False)


def test_compute_response_is_health_from_unconstrained_text():
    tpl = {
        "sections_json": [
            {"field_id": "comment", "label": "Commentaire", "type": "text", "sensitivity": "admin", "constrained": False}
        ]
    }
    assert compute_response_is_health(tpl, {"comment": "douleur"}, has_uploads=False) is True
    assert compute_response_is_health(tpl, {}, has_uploads=False) is False
    assert compute_response_is_health(tpl, {}, has_uploads=True) is True


def test_validate_admin_answers_ok():
    tpl = default_admin_template()
    answers = validate_answers_against_template(
        tpl,
        {
            "type_demande": ADMIN_TYPE_DEMANDE_OPTIONS[0],
            "deja_patient": True,
            "confirm_email": "patient@example.com",
            "disponibilites": "matin",
            "consentement": True,
        },
        hds_active=False,
    )
    assert answers["type_demande"] == "premiere_consultation"
    assert answers["deja_patient"] is True
    assert answers["confirm_email"] == "patient@example.com"
    assert answers["disponibilites"] == "matin"


def test_prefill_public_answers_from_profile():
    profile = {
        "email": "marie@example.com",
        "treating_physician_name": "Dr Curie",
    }
    out = prefill_public_answers(profile, "+33698765432")
    assert out["confirm_email"] == "marie@example.com"
    assert out["confirm_phone"] == "+33698765432"
    assert out["medecin_traitant"] == "Dr Curie"


def test_questionnaire_ai_summary_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    tpl = default_admin_template()
    summary = _questionnaire_ai_summary(
        tpl,
        {"type_demande": "suivi", "deja_patient": True, "consentement": True},
        is_health=False,
    )
    assert "Suivi" in summary or "suivi" in summary.lower()


def test_get_response_and_integrate_updates_profile(monkeypatch):
    monkeypatch.setenv("UWI_HDS_ENABLED", "false")
    tenant_id = 1
    phone = "+33611112222"
    from backend.db import upsert_cabinet_client, update_patient_fields, get_cabinet_client_by_phone

    upsert_cabinet_client(tenant_id, phone, raw_name="Paul")
    update_patient_fields(tenant_id, phone, email="old@example.com")
    tpl = ensure_default_admin_template(tenant_id)
    _, raw_token = create_questionnaire_request(
        tenant_id,
        phone,
        template_id=tpl["id"],
        sent_to_email="old@example.com",
    )
    result = submit_questionnaire_response(
        raw_token,
        {
            "type_demande": "renouvellement",
            "deja_patient": True,
            "confirm_email": "new@example.com",
            "medecin_traitant": "Dr House",
            "consentement": True,
        },
        consent_given=True,
    )
    response_id = result["response_id"]
    detail = get_questionnaire_response(tenant_id, response_id)
    assert detail["answers"]["confirm_email"] == "new@example.com"
    assert any(a["field_id"] == "type_demande" for a in detail["answers_display"])

    integrate_response(tenant_id, response_id)
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    assert profile.get("email") == "new@example.com"
    assert profile.get("treating_physician_name") == "Dr House"


def test_expire_stale_questionnaire_requests(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.db.DB_PATH", str(tmp_path / "expire.db"))
    monkeypatch.setattr("backend.db._pg_events_url", lambda: None)
    ensure_patient_v2_schema()
    tenant_id = 1
    phone = "+33633334444"
    from backend.db import get_conn, upsert_cabinet_client

    upsert_cabinet_client(tenant_id, phone, raw_name="Exp")
    tpl = ensure_default_admin_template(tenant_id)
    req, _ = create_questionnaire_request(
        tenant_id,
        phone,
        template_id=tpl["id"],
        sent_to_email="exp@example.com",
    )
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE questionnaire_requests
            SET expires_at = datetime('now', '-1 day'), status = 'sent', token_used = 0
            WHERE id = ?
            """,
            (req["id"],),
        )
        conn.commit()
    finally:
        conn.close()

    count = expire_stale_questionnaire_requests()
    assert count >= 1
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT status FROM questionnaire_requests WHERE id = ?",
            (req["id"],),
        ).fetchone()
        assert row["status"] == "expired"
    finally:
        conn.close()


def test_submit_admin_questionnaire_flow(monkeypatch):
    monkeypatch.setenv("UWI_HDS_ENABLED", "false")
    tenant_id = 1
    phone = "+33612345678"
    from backend.db import get_conn, upsert_cabinet_client

    upsert_cabinet_client(tenant_id, phone, raw_name="Test Patient")
    from backend.db import update_patient_fields

    update_patient_fields(tenant_id, phone, email="test@example.com")
    tpl = ensure_default_admin_template(tenant_id)
    assert tpl["type"] == "admin"
    req, raw_token = create_questionnaire_request(
        tenant_id,
        phone,
        template_id=tpl["id"],
        sent_to_email="test@example.com",
    )
    assert req["status"] == "sent"
    payload = public_questionnaire_payload(raw_token)
    assert payload["template"]["name"]
    result = submit_questionnaire_response(
        raw_token,
        {
            "type_demande": "suivi",
            "deja_patient": True,
            "consentement": True,
        },
        consent_given=True,
    )
    assert result["is_health"] is False
    with pytest.raises(ValueError, match="déjà utilisé"):
        submit_questionnaire_response(raw_token, {}, consent_given=True)


def test_default_medical_template_requires_hds():
    tpl = default_medical_template()
    assert tpl["is_health"] is True
    assert tpl["type"] == "medical"
    with pytest.raises(ValueError, match="santé"):
        validate_template_fields(tpl["sections_json"], hds_active=False)


def test_ensure_medical_template_blocked_without_hds(monkeypatch):
    monkeypatch.setenv("UWI_HDS_ENABLED", "false")
    with pytest.raises(ValueError, match="HDS"):
        ensure_default_medical_template(1)


def test_ensure_medical_template_with_hds(monkeypatch):
    monkeypatch.setenv("UWI_HDS_ENABLED", "true")

    def _fake_tenant(_tid):
        return {"params": {"hds_enabled": True}}

    monkeypatch.setattr("backend.questionnaire_v2._tenant_detail", _fake_tenant)
    tpl = ensure_default_medical_template(1)
    assert tpl["type"] == "medical"
    assert any(f.get("field_id") == "allergies" for f in tpl["sections_json"])


def test_hds_active_respects_tenant_params(monkeypatch):
    monkeypatch.setenv("UWI_HDS_ENABLED", "true")

    def _fake_tenant(_tid):
        return {"params": {"hds_enabled": True}}

    monkeypatch.setattr("backend.questionnaire_v2._tenant_detail", _fake_tenant)
    from backend.questionnaire_v2 import _hds_active

    assert _hds_active(1) is True

    monkeypatch.setattr("backend.questionnaire_v2._tenant_detail", lambda _tid: {"params": {}})
    assert _hds_active(1) is False


def test_summary_cache_and_context_pack():
    tenant_id = 1
    phone = "+33698765432"
    from backend.db import get_conn, upsert_cabinet_client

    upsert_cabinet_client(tenant_id, phone, raw_name="Marie Dupont")
    conn = get_conn()
    pack, contains_health = build_context_pack(conn, tenant_id, phone, set())
    assert contains_health is False
    assert "identite" in pack
    h1 = _inputs_hash(pack)
    h2 = _inputs_hash(pack)
    assert h1 == h2
    requester = RequesterContext("user-1", "owner")
    summary = get_or_generate_summary(conn, tenant_id, phone, set(), requester)
    assert "sections_json" in summary
    cached = get_or_generate_summary(conn, tenant_id, phone, set(), requester)
    assert cached.get("from_cache") is True


def test_build_context_pack_keeps_notes_if_metrics_fail(monkeypatch):
    tenant_id = 1
    phone = "+33690001122"
    from backend.db import get_conn, upsert_cabinet_client

    upsert_cabinet_client(tenant_id, phone, raw_name="Nora")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("metrics down")

    monkeypatch.setattr("backend.services.context_providers.get_patient_metrics", _boom)
    monkeypatch.setattr(
        "backend.services.context_providers._fetch_notes",
        lambda *_args, **_kwargs: [{"author": "Praticien", "content": "Douleur mandibulaire", "created_at": "2026-06-06"}],
    )

    conn = get_conn()
    try:
        pack, contains_health = build_context_pack(conn, tenant_id, phone, set())
    finally:
        conn.close()

    assert contains_health is False
    reception = pack.get("ReceptionProvider") or {}
    assert reception.get("metriques") == {}
    assert reception.get("notes_recentes")
    assert "Douleur mandibulaire" in reception["notes_recentes"][0]["content"]


def test_sante_provider_mvp_and_v2_health(monkeypatch):
    monkeypatch.setenv("UWI_HDS_ENABLED", "true")
    tenant_id = 1
    phone = "+33655556666"
    from backend.db import get_conn, upsert_cabinet_client
    from backend.patient_questionnaire import save_questionnaire

    upsert_cabinet_client(tenant_id, phone, raw_name="Jean")
    save_questionnaire(
        tenant_id,
        phone,
        answers={
            "medical_history": "Appendicectomie 2010",
            "current_treatments": "Paracétamol si besoin",
            "allergies": "Pénicilline",
            "main_reason": "Suivi annuel",
        },
        status="completed",
        filled_by="patient",
        mark_completed=True,
    )

    def _fake_tenant(_tid):
        return {"params": {"hds_enabled": True}}

    monkeypatch.setattr("backend.questionnaire_v2._tenant_detail", _fake_tenant)
    tpl = ensure_default_medical_template(tenant_id)
    _, raw_token = create_questionnaire_request(
        tenant_id,
        phone,
        template_id=tpl["id"],
        sent_to_email="jean@example.com",
    )
    submit_questionnaire_response(
        raw_token,
        {"consentement": True, "allergies": "Pénicilline"},
        consent_given=True,
    )
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE questionnaire_responses
            SET ai_summary = 'Résumé clinique V2 test'
            WHERE tenant_id = ? AND patient_phone = ?
            """,
            (tenant_id, phone),
        )
        conn.commit()
        provider = SanteProvider()
        data, exposes_health = provider.fetch(conn, tenant_id, phone, hds_active=True)
    finally:
        conn.close()

    assert exposes_health is True
    assert "Appendicectomie 2010" in data["antecedents"][0]
    assert data["allergies"] == "Pénicilline"
    assert any("Résumé clinique V2" in n for n in data["notes_cliniques"])


def test_build_context_pack_includes_sante_with_hds(monkeypatch):
    monkeypatch.setenv("UWI_HDS_ENABLED", "true")
    tenant_id = 1
    phone = "+33677778888"
    from backend.db import get_conn, upsert_cabinet_client
    from backend.patient_questionnaire import save_questionnaire

    upsert_cabinet_client(tenant_id, phone, raw_name="Luc")
    save_questionnaire(
        tenant_id,
        phone,
        answers={"allergies": "Latex"},
        status="completed",
        filled_by="patient",
        mark_completed=True,
    )
    conn = get_conn()
    try:
        pack, contains_health = build_context_pack(conn, tenant_id, phone, {"hds_enabled"})
    finally:
        conn.close()
    assert contains_health is True
    assert "SanteProvider" in pack
    assert pack["SanteProvider"]["allergies"] == "Latex"


def test_tenant_capabilities_endpoint(monkeypatch):
    monkeypatch.setenv("UWI_HDS_ENABLED", "true")
    monkeypatch.delenv("S3_BUCKET", raising=False)

    def _fake_tenant(_tid):
        return {"params": {"hds_enabled": True}}

    monkeypatch.setattr("backend.routes.patient_context._tenant_detail", _fake_tenant)

    from backend.main import app
    from backend.routes import tenant as tenant_routes
    from fastapi.testclient import TestClient

    app.dependency_overrides[tenant_routes.require_tenant_auth] = lambda: {
        "tenant_id": 1,
        "sub": "1",
        "role": "owner",
        "email": "owner@test.fr",
    }
    try:
        client = TestClient(app)
        r = client.get("/api/tenant/capabilities")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["hds_enabled"] is True
        assert body["document_storage_backend"] == "local"
        assert body["document_storage_configured"] is False
    finally:
        app.dependency_overrides.pop(tenant_routes.require_tenant_auth, None)
