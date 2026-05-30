"""Tests audit middleware — classification actions questionnaires."""

from __future__ import annotations

from backend.main import (
    _classify_patient_action,
    _classify_questionnaire_v2_action,
)


def test_classify_patient_summary_refresh():
    assert _classify_patient_action(
        "GET",
        "/api/tenant/patients/+33612345678/summary",
        "refresh=true",
    ) == "refresh_summary"
    assert _classify_patient_action(
        "GET",
        "/api/tenant/patients/+33612345678/summary",
        "",
    ) == "view_summary"


def test_classify_questionnaire_routes():
    assert _classify_patient_action(
        "POST",
        "/api/tenant/patients/+33612345678/questionnaires",
    ) == "send_questionnaire"
    assert _classify_patient_action(
        "GET",
        "/api/tenant/patients/+33612345678/questionnaires-v2",
    ) == "view_questionnaires"
    assert _classify_patient_action(
        "GET",
        "/api/tenant/patients/+33612345678/questionnaire",
    ) == "view_questionnaire"


def test_classify_questionnaire_v2_detail_routes():
    assert _classify_questionnaire_v2_action(
        "GET",
        "/api/tenant/questionnaires-v2/abc-123",
    ) == "view_questionnaire_response"
    assert _classify_questionnaire_v2_action(
        "POST",
        "/api/tenant/questionnaires-v2/abc-123/integrate",
    ) == "integrate_questionnaire"
