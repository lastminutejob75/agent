from __future__ import annotations

from unittest.mock import patch

from backend.handoffs import build_handoff_payload, create_handoff, get_handoff_by_call_id
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
