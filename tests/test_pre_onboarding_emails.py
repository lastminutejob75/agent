# tests/test_pre_onboarding_emails.py
"""Emails prospect + callback-booking (pre_onboarding)."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


MIN_COMMIT_BODY = {
    "email": "prospect@test.fr",
    "daily_call_volume": "25-50",
    "medical_specialty": "medecin_generaliste",
    "primary_pain_point": "Je suis interrompu(e) en consultation par les appels",
    "assistant_name": "Emma",
    "voice_gender": "female",
    "opening_hours": {
        "0": {"start": "09:00", "end": "18:00", "closed": False},
        "1": {"start": "09:00", "end": "18:00", "closed": False},
    },
}


@patch("backend.security.issue_lead_access_token", return_value="tok_test")
@patch("backend.routes.pre_onboarding.send_lead_prospect_confirmation_email", return_value=(True, None))
@patch("backend.routes.pre_onboarding.send_lead_founder_email", return_value=(True, None))
@patch("backend.routes.pre_onboarding.check_pre_onboarding_commit")
@patch("backend.routes.pre_onboarding.upsert_lead", return_value="lead_email_1")
def test_commit_sends_prospect_confirmation_when_email_present(
    _mock_upsert,
    _mock_rate,
    _mock_founder,
    mock_prospect,
    _mock_token,
    client,
):
    r = client.post("/api/pre-onboarding/commit", json=MIN_COMMIT_BODY)
    assert r.status_code == 200, r.text
    mock_prospect.assert_called_once()
    assert mock_prospect.call_args.kwargs["to_email"] == "prospect@test.fr"
    assert mock_prospect.call_args.kwargs["assistant_name"] == "Emma"
    assert mock_prospect.call_args.kwargs.get("callback_date_iso") is None


@patch("backend.security.assert_lead_access")
@patch("backend.routes.pre_onboarding.get_lead")
@patch("backend.routes.pre_onboarding.update_lead_callback_booking", return_value=True)
@patch("backend.routes.pre_onboarding.update_lead")
@patch("backend.services.email_service.send_lead_prospect_confirmation_email", return_value=(True, None))
@patch("backend.services.email_service.send_lead_callback_booking_email", return_value=(True, None))
def test_callback_booking_sends_founder_and_prospect_emails(
    mock_founder_cb,
    mock_prospect_cb,
    _mock_update_lead,
    _mock_update_cb,
    mock_get_lead,
    _mock_assert,
    client,
):
    mock_get_lead.side_effect = [
        {
            "id": "lead_cb_1",
            "email": "prospect@test.fr",
            "assistant_name": "Emma",
            "notes_log": [],
        },
        {
            "id": "lead_cb_1",
            "email": "prospect@test.fr",
            "assistant_name": "Emma",
            "notes_log": [],
        },
    ]
    with patch.dict(os.environ, {"ADMIN_BASE_URL": "https://www.uwiapp.com"}, clear=False):
        r = client.post(
            "/api/pre-onboarding/leads/lead_cb_1/callback-booking?token=tok_test",
            json={"date": "2026-05-23", "slot": "10h00", "phone": "0612345678"},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data.get("prospect_email_sent") is True
    mock_founder_cb.assert_called_once()
    mock_prospect_cb.assert_called_once()
    assert mock_prospect_cb.call_args.kwargs["callback_date_iso"] == "2026-05-23"
    assert mock_prospect_cb.call_args.kwargs["callback_slot"] == "10h00"


def test_callback_booking_founder_email_builds_and_sends_without_datetime_error():
    from backend.services.email_service import send_lead_callback_booking_email

    env = {
        "FOUNDER_EMAIL": "founder@test.fr",
        "ADMIN_BASE_URL": "https://www.uwiapp.com",
        "POSTMARK_SERVER_TOKEN": "pm_test",
        "EMAIL_FROM": "noreply@test.fr",
    }
    with patch.dict(os.environ, env, clear=False), patch(
        "backend.services.email_service._send_via_postmark",
        return_value=(True, None),
    ) as mock_send:
        ok, error = send_lead_callback_booking_email(
            lead_id="lead-callback-1",
            assistant_name="Emma",
            callback_date_iso="2026-07-15",
            callback_slot="10h00",
            callback_phone="0612345678",
            dashboard_base_url="https://www.uwiapp.com",
        )

    assert ok is True
    assert error is None
    mock_send.assert_called_once()
