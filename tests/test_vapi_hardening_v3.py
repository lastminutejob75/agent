# tests/test_vapi_hardening_v3.py
"""Tests Hardening V3 : payload book strict, booking_failures, get_slots exclude, log."""
import json
from unittest.mock import MagicMock, patch

import pytest

from backend import tools_booking
from backend.session import Session, QualifData
from backend.vapi_tool_handlers import (
    _chosen_slot_iso,
    build_vapi_tool_response,
    handle_book,
    handle_get_slots,
)


def _make_session(conv_id: str = "test-conv", pending_slots: list = None):
    s = Session(conv_id=conv_id)
    s.qualif_data = QualifData(name="Test", motif="Consultation", pref=None, contact="c", contact_type="email")
    s.pending_slots = pending_slots or []
    return s


def test_handle_book_confirmed_resets_booking_failures():
    """book → confirmed : payload status=confirmed, booking_failures remis à 0."""
    session = _make_session()
    session.booking_failures = 2
    session.pending_slots = [
        {"start_iso": "2025-02-05T10:00:00", "end_iso": "2025-02-05T10:30:00", "source": "google"},
    ]
    with patch.object(tools_booking, "book_slot_from_session", return_value=(True, None)):
        with patch.object(session, "google_event_id", "evt-123", create=True):
            payload, err = handle_book(session, "1", "Marie", "Consultation", "call-1")
    assert err is None
    assert payload["status"] == "confirmed"
    assert payload["event_id"] == "evt-123"
    assert payload["start_iso"] == "2025-02-05T10:00:00"
    assert payload["end_iso"] == "2025-02-05T10:30:00"
    assert session.booking_failures == 0


def test_handle_book_slot_taken_once():
    """book → slot_taken une fois : payload slot_taken, booking_failures == 1."""
    session = _make_session()
    session.pending_slots = [
        {"start_iso": "2025-02-05T14:00:00", "end_iso": "2025-02-05T14:30:00", "source": "google"},
    ]
    with patch.object(tools_booking, "book_slot_from_session", return_value=(False, "slot_taken")):
        payload, err = handle_book(session, "1", None, None, "call-1")
    assert err is None
    assert payload["status"] == "slot_taken"
    assert payload["start_iso"] == "2025-02-05T14:00:00"
    assert payload["end_iso"] == "2025-02-05T14:30:00"
    assert session.booking_failures == 1


def test_handle_book_slot_taken_twice_fallback_transfer():
    """book → slot_taken deux fois : payload fallback_transfer, booking_failures == 2."""
    session = _make_session()
    session.booking_failures = 1
    session.pending_slots = [
        {"start_iso": "2025-02-05T16:00:00", "end_iso": "2025-02-05T16:30:00", "source": "google"},
    ]
    with patch.object(tools_booking, "book_slot_from_session", return_value=(False, "slot_taken")):
        payload, err = handle_book(session, "1", None, None, "call-1")
    assert err is None
    assert payload["status"] == "fallback_transfer"
    assert session.booking_failures == 2


def test_handle_book_technical_error():
    """book → technical : payload technical_error, code calendar_unavailable."""
    session = _make_session()
    session.pending_slots = [{"start_iso": "2025-02-05T10:00:00", "end_iso": "2025-02-05T10:30:00"}]
    with patch.object(tools_booking, "book_slot_from_session", return_value=(False, "technical")):
        payload, err = handle_book(session, "1", None, None, "call-1")
    assert err is None
    assert payload["status"] == "technical_error"
    assert payload.get("code") == "calendar_unavailable"


def test_handle_book_permission_error():
    """book → permission : payload technical_error, code permission."""
    session = _make_session()
    session.pending_slots = [{"start_iso": "2025-02-05T10:00:00", "end_iso": "2025-02-05T10:30:00"}]
    with patch.object(tools_booking, "book_slot_from_session", return_value=(False, "permission")):
        payload, err = handle_book(session, "1", None, None, "call-1")
    assert err is None
    assert payload["status"] == "technical_error"
    assert payload.get("code") == "permission"


def test_chosen_slot_iso():
    """_chosen_slot_iso retourne start_iso, end_iso du créneau choice."""
    session = _make_session(
        pending_slots=[
            {"start_iso": "2025-02-05T09:00:00", "end_iso": "2025-02-05T09:30:00"},
            {"start_iso": "2025-02-05T10:00:00", "end_iso": "2025-02-05T10:30:00"},
        ]
    )
    start, end = _chosen_slot_iso(session, 2)
    assert start == "2025-02-05T10:00:00"
    assert end == "2025-02-05T10:30:00"
    start, end = _chosen_slot_iso(session, 5)
    assert start is None
    assert end is None


def test_build_vapi_tool_response_result_is_string():
    """build_vapi_tool_response avec dict produit result = JSON string."""
    payload = {"status": "confirmed", "event_id": "e1", "start_iso": "2025-02-05T10:00:00", "end_iso": "2025-02-05T10:30:00"}
    body = build_vapi_tool_response("call_1", payload, None)
    assert "results" in body
    assert len(body["results"]) == 1
    assert body["results"][0]["toolCallId"] == "call_1"
    assert body["results"][0].get("error") is None
    result_str = body["results"][0]["result"]
    assert isinstance(result_str, str)
    parsed = json.loads(result_str)
    assert parsed["status"] == "confirmed"
    assert parsed["event_id"] == "e1"


def test_get_slots_for_display_excludes_slot():
    """get_slots_for_display avec exclude_start_iso / exclude_end_iso exclut le créneau correspondant."""
    from backend.tools_booking import get_slots_for_display

    slot_a = {"start_iso": "2025-02-05T10:00:00", "end_iso": "2025-02-05T10:30:00", "label": "A"}
    slot_b = {"start_iso": "2025-02-05T14:00:00", "end_iso": "2025-02-05T14:30:00", "label": "B"}
    slot_c = {"start_iso": "2025-02-06T09:00:00", "end_iso": "2025-02-06T09:30:00", "label": "C"}
    pool = [slot_a, slot_b, slot_c]
    with patch.object(tools_booking, "_get_calendar_service", return_value=None):
        with patch.object(tools_booking, "_get_slots_from_sqlite", return_value=pool):
            with patch.object(tools_booking, "_spread_slots", side_effect=lambda p, **kw: p[: kw.get("limit", 3)]):
                with patch.object(tools_booking, "_get_cached_slots", return_value=None):
                    with patch.object(tools_booking, "_set_cached_slots"):
                        slots = get_slots_for_display(
                            limit=3,
                            session=None,
                            exclude_start_iso="2025-02-05T14:00:00",
                            exclude_end_iso="2025-02-05T14:30:00",
                        )
    starts = [s.get("start_iso") or getattr(s, "start_iso", None) or (s.start if hasattr(s, "start") else None) for s in slots]
    assert "2025-02-05T14:00:00" not in starts
    assert len(slots) == 2


def test_vapi_tool_book_response_contains_json_result():
    """POST /api/vapi/tool action=book : la réponse a results[0].result = JSON string du payload."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    session = _make_session()
    session.pending_slots = [
        {"start_iso": "2025-02-05T10:00:00", "end_iso": "2025-02-05T10:30:00", "source": "google"},
    ]
    session.google_event_id = "evt-456"
    with patch("backend.routes.voice._get_or_resume_voice_session", return_value=session):
        with patch.object(tools_booking, "book_slot_from_session", return_value=(True, None)):
            with patch("backend.routes.voice.ENGINE") as mock_engine:
                mock_engine.session_store = MagicMock()
                resp = client.post(
                    "/api/vapi/tool",
                    json={
                        "call_id": "call-v3-test",
                        "message": {
                            "toolCallList": [
                                {
                                    "id": "tool_1",
                                    "function": {
                                        "name": "function_tool",
                                        "arguments": {
                                            "action": "book",
                                            "selected_slot": "1",
                                            "patient_name": "Jean",
                                            "motif": "Consultation",
                                        },
                                    },
                                }
                            ],
                        },
                    },
                )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) == 1
    result_str = data["results"][0].get("result")
    assert result_str is not None
    payload = json.loads(result_str)
    assert payload["status"] == "confirmed"
    assert payload["event_id"] == "evt-456"
    assert "start_iso" in payload and "end_iso" in payload
