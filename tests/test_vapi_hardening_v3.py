# tests/test_vapi_hardening_v3.py
"""Tests Hardening V3 : payload book strict, booking_failures, get_slots exclude, log."""
from datetime import datetime
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
            with patch("backend.engine._persist_ivr_event") as mock_persist:
                payload, err = handle_book(session, "1", "Marie", "Consultation", "call-1")
    assert err is None
    assert payload["status"] == "confirmed"
    assert payload["event_id"] == "evt-123"
    assert payload["start_iso"] == "2025-02-05T10:00:00"
    assert payload["end_iso"] == "2025-02-05T10:30:00"
    assert session.booking_failures == 0
    mock_persist.assert_called_once()
    args, kwargs = mock_persist.call_args
    assert args == (session, "booking_confirmed")
    assert "context" in kwargs


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


def test_get_slots_for_display_provider_none_uses_local_fallback():
    """provider=none doit proposer les créneaux locaux UWI sans appeler Google."""
    from backend.calendar_adapter import _NoneCalendarAdapter
    from backend.tools_booking import get_slots_for_display

    local_pool = [{"start_iso": "2025-02-05T10:00:00", "end_iso": "2025-02-05T10:30:00", "label": "A", "source": "sqlite"}]

    class Session:
        tenant_id = 7
        rejected_slot_starts = []

    with patch("backend.calendar_adapter.get_calendar_adapter", return_value=_NoneCalendarAdapter()):
        with patch.object(tools_booking, "_get_calendar_service") as mock_google:
            with patch.object(tools_booking, "_get_slots_from_sqlite", return_value=local_pool):
                with patch.object(tools_booking, "_spread_slots", side_effect=lambda p, **kw: p[: kw.get("limit", 3)]):
                    with patch.object(tools_booking, "_get_cached_slots", return_value=None):
                        with patch.object(tools_booking, "_set_cached_slots"):
                            slots = get_slots_for_display(limit=3, session=Session())

    assert slots == local_pool
    mock_google.assert_not_called()


def test_get_slots_for_display_google_provider_does_not_fallback_to_local_on_permission():
    """provider=google explicite: si Google échoue, ne jamais peupler des slots UWI en secours."""
    from backend.google_calendar import GoogleCalendarPermissionError
    from backend.tools_booking import get_slots_for_display

    class Session:
        tenant_id = 9
        rejected_slot_starts = []

    class FakeGoogleAdapter:
        def can_propose_slots(self):
            return True

    sqlite_called = {"value": False}

    def _fake_sqlite(*args, **kwargs):
        sqlite_called["value"] = True
        return [{"start_iso": "2025-02-05T10:00:00", "end_iso": "2025-02-05T10:30:00", "label": "A", "source": "sqlite"}]

    with patch("backend.tenant_config.get_params", return_value={"calendar_provider": "google", "calendar_id": "cabinet@test"}):
        with patch("backend.calendar_adapter.get_calendar_adapter", return_value=FakeGoogleAdapter()):
            with patch.object(tools_booking, "_get_slots_from_google_calendar", side_effect=GoogleCalendarPermissionError(Exception("403"))):
                with patch.object(tools_booking, "_get_slots_from_sqlite", side_effect=_fake_sqlite):
                    with patch.object(tools_booking, "_get_cached_slots", return_value=None):
                        with patch.object(tools_booking, "_set_cached_slots"):
                            slots = get_slots_for_display(limit=3, session=Session())

    assert slots == []
    assert sqlite_called["value"] is False


def test_get_slots_for_display_cache_hit_skips_tenant_params_lookup():
    """Un cache hit chaud ne doit pas relire tenant_config avant de répondre."""
    from backend.tools_booking import get_slots_for_display

    class Session:
        tenant_id = 9
        rejected_slot_starts = []

    cached_slots = [{"start_iso": "2025-02-05T10:00:00", "end_iso": "2025-02-05T10:15:00", "label": "A", "source": "google"}]

    with patch.object(tools_booking, "_get_cached_slots", return_value=cached_slots):
        with patch("backend.tenant_config.get_params", side_effect=AssertionError("get_params should not be called on cache hit")):
            slots = get_slots_for_display(limit=3, pref="matin", session=Session())

    assert slots == cached_slots


def test_handle_get_slots_uses_short_sync_fetch_on_cold_cache():
    """Sur cache froid, le tool vocal doit tenter une lecture courte et rendre des slots dès le premier essai."""
    session = _make_session()

    fresh_slots = [
        {"start_iso": "2025-02-05T14:00:00", "end_iso": "2025-02-05T14:15:00", "label": "Mercredi 5 février à 14h00", "source": "google"},
        {"start_iso": "2025-02-06T15:00:00", "end_iso": "2025-02-06T15:15:00", "label": "Jeudi 6 février à 15h00", "source": "google"},
    ]

    with patch.object(tools_booking, "_get_cached_slots", return_value=None):
        with patch.object(tools_booking, "get_slots_for_display", return_value=fresh_slots) as mock_fetch:
            def _capture_store(sess, slots, enrich_google=False):
                sess._slots_source = "google"
                sess.pending_slots = slots

            with patch.object(tools_booking, "store_pending_slots", side_effect=_capture_store) as mock_store:
                labels, source, err = handle_get_slots(session, "après-midi", "call-cold-cache")

    assert err == ""
    assert source == "google_calendar"
    assert labels is not None
    assert len(labels) == 2
    assert mock_fetch.called is True
    mock_store.assert_called_once_with(session, fresh_slots, enrich_google=False)


def test_get_slots_from_google_calendar_prefers_batched_range_call():
    """Le fetch Google multi-jours doit utiliser la lecture groupée pour éviter 1 appel API par jour."""

    class FakeCalendar:
        def __init__(self):
            self.range_calls = 0
            self.single_calls = 0

        def get_free_slots_range(self, **kwargs):
            self.range_calls += 1
            dates = kwargs["dates"]
            return [
                {
                    "start": dates[0].replace(hour=14, minute=0, second=0, microsecond=0).isoformat(),
                    "end": dates[0].replace(hour=14, minute=15, second=0, microsecond=0).isoformat(),
                    "label": "Premier",
                },
                {
                    "start": dates[1].replace(hour=15, minute=0, second=0, microsecond=0).isoformat(),
                    "end": dates[1].replace(hour=15, minute=15, second=0, microsecond=0).isoformat(),
                    "label": "Deuxième",
                },
                {
                    "start": dates[2].replace(hour=16, minute=0, second=0, microsecond=0).isoformat(),
                    "end": dates[2].replace(hour=16, minute=15, second=0, microsecond=0).isoformat(),
                    "label": "Troisième",
                },
            ]

        def get_free_slots(self, **kwargs):
            self.single_calls += 1
            return []

    rules = {
        "duration_minutes": 15,
        "start_hour": 9,
        "end_hour": 18,
        "booking_days": [0, 1, 2, 3, 4],
        "buffer_minutes": 0,
    }
    calendar = FakeCalendar()

    with patch("backend.tenant_config.get_booking_rules", return_value=rules):
        slots = tools_booking._get_slots_from_google_calendar(calendar, limit=3, pref="après-midi", tenant_id=2)

    assert len(slots) == 3
    assert calendar.range_calls == 1
    assert calendar.single_calls == 0
    assert all(getattr(slot, "source", "") == "google" for slot in slots)
    assert all(isinstance(datetime.fromisoformat(slot.start), datetime) for slot in slots)


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


def test_vapi_tool_resolves_tenant_from_assistant_when_did_missing():
    """Le tool-call doit appeler la résolution tenant normale même si le fast-cache renvoie 1."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with patch("backend.tenant_routing._fast_resolve_assistant_id", return_value=1):
        with patch(
            "backend.tenant_routing.resolve_tenant_id_from_vapi_payload",
            return_value=(7, "assistant"),
        ) as mock_resolve:
            with patch("backend.vapi_tool_handlers.handle_get_slots", return_value=(["Demain 10h"], "google", None)):
                with patch("backend.routes.voice.ENGINE") as mock_engine:
                    mock_engine.session_store = MagicMock()
                    resp = client.post(
                        "/api/vapi/tool",
                        json={
                            "message": {
                                "call": {"id": "call-assistant-route", "assistantId": "asst_live_123"},
                                "toolCallList": [
                                    {
                                        "id": "tool_1",
                                        "function": {
                                            "name": "function_tool",
                                            "arguments": {
                                                "action": "get_slots",
                                                "patient_name": "Jean",
                                                "motif": "Consultation",
                                            },
                                        },
                                    }
                                ],
                            }
                        },
                    )
    assert resp.status_code == 200
    mock_resolve.assert_called_once()
