"""Accès réservé aux patients enregistrés (cabinet_clients)."""

from __future__ import annotations

from types import SimpleNamespace


def test_public_callback_request_rejects_unregistered_patient(monkeypatch):
    from backend.routes import public_appointment_actions as routes

    monkeypatch.setattr(routes, "_resolve_tenant_id", lambda slug: 2)
    monkeypatch.setattr(routes, "_rate_limit_public_action", lambda *a, **k: None)
    monkeypatch.setattr(routes, "validate_phone", lambda p: True)
    monkeypatch.setattr(routes, "find_registered_patient", lambda *a, **k: None)

    class Req:
        pass

    body = routes.PublicCallbackRequestBody(
        name="Inconnu Test",
        phone="0612345678",
        reason="other",
    )
    try:
        routes.public_callback_request("cabinet-demo-uwi", body, Req())
        assert False, "expected HTTPException"
    except routes.HTTPException as exc:
        assert exc.status_code == 403


def test_find_registered_patient_for_session_uses_phone(monkeypatch):
    from backend.registered_patient_access import find_registered_patient_for_session

    seen = {}

    def _find(tenant_id, phone=None, email=None):
        seen["tenant_id"] = tenant_id
        seen["phone"] = phone
        return {"phone": phone} if phone == "+33612345678" else None

    monkeypatch.setattr("backend.registered_patient_access.find_registered_patient", _find)
    session = SimpleNamespace(
        tenant_id=3,
        customer_phone="+33612345678",
        qualif_data=SimpleNamespace(contact=None, contact_type=None, email=None),
    )
    profile = find_registered_patient_for_session(3, session)
    assert profile is not None
    assert seen["phone"] == "+33612345678"


def test_ensure_transfer_handoff_skips_unregistered(monkeypatch):
    from backend.handoffs import ensure_transfer_handoff

    monkeypatch.setattr(
        "backend.registered_patient_access.find_registered_patient_for_session",
        lambda tenant_id, session: None,
    )
    session = SimpleNamespace(tenant_id=1, conv_id="call-1", channel="vocal")
    assert ensure_transfer_handoff(session, trigger_reason="explicit_human_request") is None
