from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.routes.voice import _maybe_start_live_transfer_for_session
from backend.session import Session
from fastapi.testclient import TestClient

from backend.main import app
from backend.vapi_live_transfer import (
    extract_control_url,
    maybe_start_live_transfer,
    maybe_start_terminal_booking_end,
    normalize_transfer_destination_phone,
    poll_transfer_confirmation,
)


def test_extract_control_url_supports_root_and_message_call():
    assert (
        extract_control_url({"call": {"monitor": {"controlUrl": "https://example.com/live"}}})
        == "https://example.com/live/control"
    )
    assert (
        extract_control_url({"message": {"call": {"monitor": {"controlUrl": "https://example.com/live/control"}}}})
        == "https://example.com/live/control"
    )


def test_normalize_transfer_destination_phone_supports_fr_formats():
    assert normalize_transfer_destination_phone("06 12 34 56 78") == "+33612345678"
    assert normalize_transfer_destination_phone("01 23 45 67 89") == "+33123456789"
    assert normalize_transfer_destination_phone("+33612345678") == "+33612345678"
    assert normalize_transfer_destination_phone("123") == ""


def test_maybe_start_live_transfer_posts_control_request_and_marks_handoff():
    session = Session(conv_id="call-live-ok", channel="vocal", tenant_id=12)
    session.state = "TRANSFERRED"
    session.last_transfer_reason = "explicit_transfer_request"

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    with patch("backend.vapi_live_transfer.resolve_handoff_decision", return_value={
        "reason": "explicit_human_request",
        "target": "assistant",
        "mode": "live_then_callback",
        "priority": "normal",
    }), patch("backend.vapi_live_transfer.get_params", return_value={
        "transfer_assistant_phone": "+33123456789",
    }), patch("backend.vapi_live_transfer.ensure_transfer_handoff", return_value={"id": 7}), patch(
        "backend.vapi_live_transfer.update_handoff_status"
    ) as mock_update, patch("backend.vapi_live_transfer.schedule_transfer_confirmation") as mock_schedule, patch(
        "backend.vapi_live_transfer.httpx.Client"
    ) as mock_httpx_client:
        mock_httpx_client.return_value.__enter__.return_value = mock_client
        result = maybe_start_live_transfer(
            {"call": {"monitor": {"controlUrl": "https://api.vapi.test/call-1"}}},
            session,
            response_text="Je vous transfère maintenant.",
            user_text="Je veux parler à quelqu'un",
        )

    assert result["ok"] is True
    assert session.live_transfer_requested is True
    mock_client.post.assert_called_once()
    assert mock_client.post.call_args.kwargs["json"]["type"] == "transfer"
    assert mock_client.post.call_args.kwargs["json"]["destination"]["number"] == "+33123456789"
    mock_update.assert_called_once_with(12, 7, status="live_attempted")
    mock_schedule.assert_called_once_with("call-live-ok", 12, 7)


def test_maybe_start_live_transfer_returns_failure_when_control_post_fails():
    session = Session(conv_id="call-live-ko", channel="vocal", tenant_id=12)
    session.state = "TRANSFERRED"
    session.last_transfer_reason = "technical_failure"

    mock_client = MagicMock()
    mock_client.post.side_effect = RuntimeError("network down")

    with patch("backend.vapi_live_transfer.resolve_handoff_decision", return_value={
        "reason": "technical_failure",
        "target": "assistant",
        "mode": "live_then_callback",
        "priority": "normal",
    }), patch("backend.vapi_live_transfer.get_params", return_value={
        "transfer_assistant_phone": "+33123456789",
    }), patch("backend.vapi_live_transfer.ensure_transfer_handoff", return_value={"id": 8}), patch(
        "backend.vapi_live_transfer.update_handoff_status"
    ) as mock_update, patch("backend.vapi_live_transfer.httpx.Client") as mock_httpx_client:
        mock_httpx_client.return_value.__enter__.return_value = mock_client
        result = maybe_start_live_transfer(
            {"message": {"call": {"monitor": {"controlUrl": "https://api.vapi.test/call-2/control"}}}},
            session,
            response_text="Je vous transfère maintenant.",
            user_text="Je veux parler à quelqu'un",
        )

    assert result["attempted"] is True
    assert result["ok"] is False
    assert not getattr(session, "live_transfer_requested", False)
    mock_update.assert_called_once_with(12, 8, status="live_failed")


def test_maybe_start_live_transfer_uses_legacy_phone_number_as_assistant_fallback():
    session = Session(conv_id="call-live-fallback", channel="vocal", tenant_id=12)
    session.state = "TRANSFERRED"
    session.last_transfer_reason = "technical_failure"

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    with patch("backend.vapi_live_transfer.resolve_handoff_decision", return_value={
        "reason": "technical_failure",
        "target": "assistant",
        "mode": "live_then_callback",
        "priority": "normal",
    }), patch("backend.vapi_live_transfer.get_params", return_value={
        "phone_number": "01 23 45 67 89",
    }), patch("backend.vapi_live_transfer.ensure_transfer_handoff", return_value={"id": 12}), patch(
        "backend.vapi_live_transfer.update_handoff_status"
    ) as mock_update, patch("backend.vapi_live_transfer.schedule_transfer_confirmation"), patch(
        "backend.vapi_live_transfer.httpx.Client"
    ) as mock_httpx_client:
        mock_httpx_client.return_value.__enter__.return_value = mock_client
        result = maybe_start_live_transfer(
            {"call": {"monitor": {"controlUrl": "https://api.vapi.test/call-fallback"}}},
            session,
            response_text="Je vous transfère maintenant.",
            user_text="Je veux parler à quelqu'un",
        )

    assert result["ok"] is True
    assert mock_client.post.call_args.kwargs["json"]["destination"]["number"] == "+33123456789"
    mock_update.assert_called_once_with(12, 12, status="live_attempted")


def test_voice_helper_can_suppress_followup_tts_when_live_transfer_started():
    session = Session(conv_id="call-live-helper", channel="vocal", tenant_id=12)
    session.state = "TRANSFERRED"

    with patch("backend.routes.voice.maybe_start_live_transfer", return_value={"ok": True}), patch(
        "backend.routes.voice.ENGINE"
    ) as mock_engine:
        mock_engine.session_store = MagicMock()
        response_text, suppressed = _maybe_start_live_transfer_for_session(
            {"call": {"monitor": {"controlUrl": "https://api.vapi.test/call-3"}}},
            session,
            response_text="Je vous transfère maintenant.",
            user_text="parler à quelqu'un",
            suppress_model_tts=True,
        )

    assert response_text == ""
    assert suppressed is True


def test_maybe_start_terminal_booking_end_mutes_assistant_then_says_and_hangs_up():
    session = Session(conv_id="call-book-end-ok", channel="vocal", tenant_id=12)

    mock_client = MagicMock()
    mute_response = MagicMock()
    mute_response.raise_for_status.return_value = None
    say_response = MagicMock()
    say_response.raise_for_status.return_value = None
    mock_client.post.side_effect = [mute_response, say_response]

    with patch("backend.vapi_live_transfer.httpx.Client") as mock_httpx_client:
        mock_httpx_client.return_value.__enter__.return_value = mock_client
        result = maybe_start_terminal_booking_end(
            {"call": {"monitor": {"controlUrl": "https://api.vapi.test/call-book-end"}}},
            session,
        )

    assert result["ok"] is True
    assert session.booking_end_control_requested is True
    assert mock_client.post.call_count == 2
    assert mock_client.post.call_args_list[0].kwargs["json"] == {"type": "control", "control": "mute-assistant"}
    assert mock_client.post.call_args_list[1].kwargs["json"] == {
        "type": "say",
        "content": "Votre rendez-vous est confirmé. Merci pour votre appel. Bonne journée.",
        "endCallAfterSpoken": True,
    }


def test_maybe_start_terminal_booking_end_returns_failure_when_control_url_missing():
    session = Session(conv_id="call-book-end-missing", channel="vocal", tenant_id=12)

    result = maybe_start_terminal_booking_end({}, session)

    assert result["attempted"] is False
    assert result["ok"] is False
    assert result["reason"] == "missing_control_url"
    assert not getattr(session, "booking_end_control_requested", False)


def test_poll_transfer_confirmation_marks_timeout_when_unconfirmed():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.content = b'{}'
    mock_response.json.return_value = {"status": "in-progress"}
    mock_client.get.return_value = mock_response

    with patch("backend.vapi_live_transfer._vapi_api_key", return_value="sk_test"), patch(
        "backend.vapi_live_transfer.httpx.Client"
    ) as mock_httpx_client, patch(
        "backend.vapi_live_transfer._update_handoff_if_needed"
    ) as mock_update, patch(
        "backend.vapi_live_transfer.time.time",
        side_effect=[0, 0, 21, 21],
    ), patch("backend.vapi_live_transfer.time.sleep", return_value=None):
        mock_httpx_client.return_value.__enter__.return_value = mock_client
        poll_transfer_confirmation("call-timeout-1", 12, 9)

    mock_update.assert_called_once_with(12, 9, "live_unconfirmed_timeout")


def test_status_update_promotes_handoff_on_forwarding_and_forwarded_end():
    client = TestClient(app)
    payload = {
        "message": {
            "type": "status-update",
            "status": "forwarding",
            "call": {
                "id": "call-forward-1",
                "assistantId": "asst_123",
                "status": "forwarding",
            },
        }
    }

    with patch("backend.tenant_routing.resolve_tenant_id_from_vapi_payload", return_value=(12, "assistant")), patch(
        "backend.tenant_routing.extract_customer_phone_from_vapi_payload",
        return_value="+33612345678",
    ), patch("backend.routes.voice.upsert_vapi_call", create=True) as _unused, patch(
        "backend.vapi_calls_pg.upsert_vapi_call",
        return_value=True,
    ), patch("backend.routes.voice.get_handoff_by_call_id", create=True) as _unused2, patch(
        "backend.handoffs.get_handoff_by_call_id",
        return_value={"id": 5, "status": "live_attempted"},
    ), patch("backend.handoffs.update_handoff_status") as mock_update:
        response = client.post("/api/vapi/webhook", json=payload)

    assert response.status_code == 200
    mock_update.assert_called_once_with(12, 5, status="live_forwarding_confirmed")

    payload["message"]["status"] = "ended"
    payload["message"]["endedReason"] = "assistant-forwarded-call"
    payload["message"]["call"]["status"] = "ended"
    payload["message"]["call"]["endedReason"] = "assistant-forwarded-call"

    with patch("backend.tenant_routing.resolve_tenant_id_from_vapi_payload", return_value=(12, "assistant")), patch(
        "backend.tenant_routing.extract_customer_phone_from_vapi_payload",
        return_value="+33612345678",
    ), patch("backend.vapi_calls_pg.upsert_vapi_call", return_value=True), patch(
        "backend.handoffs.get_handoff_by_call_id",
        return_value={"id": 5, "status": "live_forwarding_confirmed"},
    ), patch("backend.handoffs.update_handoff_status") as mock_update:
        response = client.post("/api/vapi/webhook", json=payload)

    assert response.status_code == 200
    mock_update.assert_called_once_with(12, 5, status="live_connected")
