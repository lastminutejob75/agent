from backend.booking_code import format_booking_code, normalize_booking_code
from backend.public_action_tokens import decode_public_action_token, issue_public_action_token
from backend.public_bookings_pg import _contact_email_matches, _contact_phone_matches


def test_public_action_token_roundtrip():
    token = issue_public_action_token(
        tenant_id=42,
        source_type="public_booking",
        source_id="abc-123",
        booking_code="A7K3M2",
    )
    payload = decode_public_action_token(token)
    assert payload is not None
    assert payload["tenant_id"] == 42
    assert payload["source_type"] == "public_booking"
    assert payload["source_id"] == "abc-123"
    assert payload["booking_code"] == "A7K3M2"


def test_contact_phone_matches_normalized():
    assert _contact_phone_matches("0612345678", "+33612345678")
    assert not _contact_phone_matches("0612345678", "+33698765432")


def test_contact_email_matches_case_insensitive():
    assert _contact_email_matches("Patient@Email.com", "patient@email.com")
    assert not _contact_email_matches("a@b.com", "c@d.com")


def test_format_booking_code_in_lookup_response():
    assert format_booking_code(normalize_booking_code("RDV-Z9X8Y7")) == "RDV-Z9X8Y7"


def test_public_callback_request_links_appointment_from_token(monkeypatch):
    from backend.routes import public_appointment_actions as routes

    captured = {}

    def _fake_insert(**kwargs):
        captured.update(kwargs)
        return "req-1"

    monkeypatch.setattr(routes, "insert_callback_request", _fake_insert)
    monkeypatch.setattr(routes, "_resolve_tenant_id", lambda slug: 2)
    monkeypatch.setattr(routes, "_rate_limit_public_action", lambda *a, **k: None)
    monkeypatch.setattr(routes, "validate_phone", lambda p: True)
    monkeypatch.setattr(
        routes,
        "find_registered_patient",
        lambda tenant_id, phone=None, email=None: {"phone": phone or "+33612345678"},
    )
    monkeypatch.setattr(
        "backend.public_action_tokens.decode_public_action_token",
        lambda token: {
            "tenant_id": 2,
            "source_type": "public_booking",
            "source_id": "abc-123",
            "booking_code": "A7K3M2",
        },
    )

    class Req:
        pass

    body = routes.PublicCallbackRequestBody(
        name="Patient Test",
        phone="0612345678",
        reason="question_rdv",
        actionToken="fake-token",
    )
    out = routes.public_callback_request("cabinet-demo-uwi", body, Req())
    assert out["ok"] is True
    assert captured.get("appointment_source") == "public"
    assert captured.get("appointment_id") == "abc-123"


def test_dispatch_cancel_notifications_patient_sms_and_email(monkeypatch):
    from backend import public_action_notifications as mod

    sent = {"sms": [], "emails": []}

    monkeypatch.setattr(
        mod,
        "_practitioner_for_slug",
        lambda slug: {"name": "Dr Test", "email": "cabinet@example.com"},
    )
    monkeypatch.setattr(
        "backend.routes.public_pages._send_sms",
        lambda phone, body: sent["sms"].append((phone, body)) or True,
    )
    monkeypatch.setattr(
        mod,
        "_send_html_email",
        lambda to, subject, html: sent["emails"].append((to, subject)) or True,
    )
    monkeypatch.setenv("PUBLIC_BOOKING_CABINET_SMS_TO", "+33600000001")

    record = {
        "source_type": "public_booking",
        "patient_name": "Jean Dupont",
        "patient_phone": "+33612345678",
        "patient_email": "jean@example.com",
        "slot_label": "mercredi a 09:30",
    }
    out = mod.dispatch_public_cancel_notifications(
        slug="cabinet-demo",
        tenant_id=2,
        record=record,
        booking_code="GTYEGG",
        slot_label="mercredi a 09:30",
        reason="Indisponible",
    )

    assert out["patient_sms"] is True
    assert out["patient_email"] is True
    assert out["cabinet_sms"] is True
    assert out["cabinet_email"] is True
    assert sent["sms"][0][0] == "+33612345678"
    assert "RDV-GTYEGG" in sent["sms"][0][1]
    assert sent["emails"][0][0] == "jean@example.com"


def test_cancel_appointment_triggers_notifications(monkeypatch):
    from backend import public_appointment_actions as actions

    calls = []

    monkeypatch.setattr(
        actions,
        "decode_public_action_token",
        lambda token: {
            "tenant_id": 2,
            "source_type": "public_booking",
            "source_id": "pb-1",
            "booking_code": "GTYEGG",
        },
    )
    monkeypatch.setattr(
        actions,
        "_load_record_from_token",
        lambda payload: {
            "source_type": "public_booking",
            "id": "pb-1",
            "patient_name": "Jean Dupont",
            "patient_phone": "+33612345678",
            "patient_email": "jean@example.com",
            "slot_label": "mercredi a 09:30",
            "booking_code": "GTYEGG",
            "start_iso": "2026-06-03T09:30:00+02:00",
        },
    )
    monkeypatch.setattr(actions, "_verify_contact_for_record", lambda *a, **k: True)
    monkeypatch.setattr(actions, "_enforce_action_rules", lambda *a, **k: None)
    monkeypatch.setattr(actions, "_cancel_all_for_booking", lambda *a, **k: True)
    monkeypatch.setattr(
        actions,
        "uses_google_calendar",
        lambda tenant_id: False,
    )
    monkeypatch.setattr(
        "backend.public_action_notifications.dispatch_public_cancel_notifications",
        lambda **kwargs: calls.append(kwargs) or {"patient_sms": True},
    )

    out = actions.cancel_appointment(
        slug="cabinet-demo",
        action_token="token",
        phone="+33612345678",
    )
    assert out["cancelled"] is True
    assert len(calls) == 1
    assert calls[0]["slug"] == "cabinet-demo"
    assert calls[0]["booking_code"] == "GTYEGG"
