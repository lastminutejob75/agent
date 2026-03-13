from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from backend.handoff_router import resolve_handoff_decision, resolve_handoff_target_phone
from backend.handoffs import build_handoff_payload, create_handoff, get_handoff_by_call_id, update_handoff_status
from backend.session import QualifData, Session


def test_create_handoff_returns_existing_for_same_call(monkeypatch):
    existing = {
        "id": 7,
        "tenant_id": 12,
        "call_id": "call_123",
        "status": "callback_created",
        "target": "assistant",
    }

    with patch("backend.handoffs.get_handoff_by_call_id", side_effect=[existing, existing]):
        row = create_handoff(
            12,
            "call_123",
            channel="vocal",
            reason="explicit_human_request",
            target="assistant",
            mode="callback_only",
            priority="normal",
            status="callback_created",
        )

    assert row == existing


def test_build_handoff_payload_uses_phone_and_name_from_session():
    session = Session(conv_id="call_abc", channel="vocal", tenant_id=12, customer_phone="+33698765432")
    session.qualif_data = QualifData(name="Claire Dupont", motif="Question de traitement", contact=None, contact_type=None)
    session.add_message("user", "Je veux parler au médecin.")
    session.add_message("agent", "Je transmets votre demande.")

    with patch("backend.handoffs.db.get_cabinet_client_by_phone", return_value=None):
        payload = build_handoff_payload(
            session,
            reason="explicit_practitioner_request",
            target="practitioner",
            mode="callback_only",
            priority="high",
        )

    assert payload["tenant_id"] == 12
    assert payload["call_id"] == "call_abc"
    assert payload["patient_phone"] == "+33698765432"
    assert payload["raw_name"] == "Claire Dupont"
    assert payload["display_name"] == "Claire Dupont"
    assert payload["booking_motif"] == "Question de traitement"
    assert "Patient: Je veux parler au médecin." in payload["transcript_excerpt"]


def test_resolve_handoff_decision_uses_live_then_callback_when_configured():
    session = Session(conv_id="call_cfg", channel="vocal", tenant_id=12, customer_phone="+33698765432")

    with patch(
        "backend.handoff_router.get_params",
        return_value={
            "transfer_live_enabled": "true",
            "transfer_callback_enabled": "true",
            "transfer_assistant_phone": "+33123456789",
        },
    ):
        decision = resolve_handoff_decision(
            session,
            trigger_reason="technical_failure",
            channel="vocal",
            user_text="Je veux parler à quelqu'un",
        )

    assert decision["target"] == "assistant"
    assert decision["mode"] == "live_then_callback"


def test_resolve_handoff_decision_accepts_legacy_assistant_phone_fields():
    session = Session(conv_id="call_cfg_legacy", channel="vocal", tenant_id=12, customer_phone="+33698765432")

    with patch(
        "backend.handoff_router.get_params",
        return_value={
            "transfer_live_enabled": "true",
            "transfer_callback_enabled": "true",
            "phone_number": "+33123456789",
        },
    ):
        decision = resolve_handoff_decision(
            session,
            trigger_reason="technical_failure",
            channel="vocal",
            user_text="Je veux parler à quelqu'un",
        )

    assert decision["target"] == "assistant"
    assert decision["mode"] == "live_then_callback"


def test_resolve_handoff_target_phone_prefers_dedicated_assistant_phone_then_legacy_fields():
    assert (
        resolve_handoff_target_phone(
            {
                "transfer_assistant_phone": "+33911111111",
                "transfer_number": "+33922222222",
                "phone_number": "+33933333333",
            },
            "assistant",
        )
        == "+33911111111"
    )
    assert resolve_handoff_target_phone({"transfer_number": "+33922222222"}, "assistant") == "+33922222222"
    assert resolve_handoff_target_phone({"phone_number": "+33933333333"}, "assistant") == "+33933333333"
    assert resolve_handoff_target_phone({"phone_number": "+33933333333"}, "practitioner") == ""


def test_resolve_handoff_target_phone_falls_back_to_main_human_number_for_client_wizard():
    assert (
        resolve_handoff_target_phone(
            {
                "transfer_number": "+33922222222",
                "transfer_config_confirmed_signature": "sig",
                "transfer_cases": ["urgent"],
            },
            "practitioner",
        )
        == "+33922222222"
    )


def test_resolve_handoff_decision_keeps_legacy_live_behavior_without_wizard_preferences():
    session = Session(conv_id="call_cfg_legacy_live", channel="vocal", tenant_id=12, customer_phone="+33698765432")

    with patch(
        "backend.handoff_router.get_params",
        return_value={
            "transfer_live_enabled": "true",
            "transfer_callback_enabled": "true",
            "transfer_number": "+33123456789",
        },
    ):
        decision = resolve_handoff_decision(
            session,
            trigger_reason="technical_failure",
            channel="vocal",
            user_text="Je veux parler a quelqu'un",
        )

    assert decision["mode"] == "live_then_callback"


def test_resolve_handoff_decision_respects_transfer_cases_for_automatic_live_transfer():
    session = Session(conv_id="call_cfg_cases", channel="vocal", tenant_id=12, customer_phone="+33698765432")

    with patch(
        "backend.handoff_router.get_params",
        return_value={
            "transfer_live_enabled": "true",
            "transfer_callback_enabled": "true",
            "transfer_number": "+33123456789",
            "transfer_config_confirmed_signature": "sig",
            "transfer_cases": ["urgent"],
        },
    ):
        decision = resolve_handoff_decision(
            session,
            trigger_reason="technical_failure",
            channel="vocal",
            user_text="J'ai besoin d'aide",
        )

    assert decision["mode"] == "callback_only"


def test_resolve_handoff_decision_allows_urgent_override_outside_transfer_hours():
    session = Session(conv_id="call_cfg_urgent", channel="vocal", tenant_id=12, customer_phone="+33698765432")

    with patch(
        "backend.handoff_router.get_params",
        return_value={
            "transfer_live_enabled": "true",
            "transfer_callback_enabled": "true",
            "transfer_number": "+33123456789",
            "transfer_config_confirmed_signature": "sig",
            "transfer_cases": ["urgent"],
            "transfer_always_urgent": "true",
            "transfer_hours": {
                "Lundi": {"enabled": True, "from": "09:00", "to": "18:00"},
            },
        },
    ), patch("backend.handoff_router._now_for_transfer_window", return_value=datetime(2026, 3, 16, 21, 0)):
        decision = resolve_handoff_decision(
            session,
            trigger_reason="urgent_non_vital_case",
            channel="vocal",
            user_text="C'est urgent",
        )

    assert decision["mode"] == "live_then_callback"


def test_update_handoff_status_can_update_notes_without_changing_status():
    current = {
        "id": 11,
        "tenant_id": 12,
        "call_id": "call_notes",
        "status": "callback_created",
        "notes": "",
    }
    updated = {**current, "notes": "Rappel ce soir"}

    with patch("backend.handoffs.get_handoff_by_id", side_effect=[current, updated]), patch(
        "backend.handoffs.db._pg_events_url",
        return_value="",
    ), patch("backend.handoffs.db.get_conn") as mock_conn:
        conn = mock_conn.return_value
        result = update_handoff_status(12, 11, notes="Rappel ce soir")

    assert result == updated
    _, params = conn.execute.call_args_list[-1][0]
    assert params[0] == "callback_created"
    assert params[2] == "Rappel ce soir"
