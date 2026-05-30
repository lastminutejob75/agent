"""Tests V2 : questionnaires typés, is_health, résumé patient."""

from __future__ import annotations

import pytest

from backend.patient_v2_db import ensure_patient_v2_schema
from backend.questionnaire_v2 import (
    ADMIN_TYPE_DEMANDE_OPTIONS,
    compute_response_is_health,
    create_questionnaire_request,
    default_admin_template,
    ensure_default_admin_template,
    public_questionnaire_payload,
    submit_questionnaire_response,
    validate_answers_against_template,
    validate_template_fields,
)
from backend.services.context_providers import build_context_pack
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
            "consentement": True,
        },
        hds_active=False,
    )
    assert answers["type_demande"] == "premiere_consultation"
    assert answers["deja_patient"] is True


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
