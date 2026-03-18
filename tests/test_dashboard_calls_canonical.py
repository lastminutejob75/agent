from datetime import datetime, timedelta, timezone

from backend.routes.admin import _build_call_item_from_vapi_row, _snapshot_outcome_from_sources


def test_build_call_item_prefers_usage_duration_and_last_event():
    started = datetime(2026, 3, 18, 10, 0, 0, tzinfo=timezone.utc)
    ended = started + timedelta(seconds=125)
    row = {
        "tenant_id": 2,
        "call_id": "call-123",
        "customer_number": "+33612345678",
        "started_at": started,
        "ended_at": ended,
        "updated_at": ended,
        "sort_ts": ended,
        "status": "ended",
        "ended_reason": "customer-ended-call",
        "duration_sec": 120.9,
        "last_event": "booking_confirmed",
    }

    item = _build_call_item_from_vapi_row(row, "Cabinet Test")

    assert item["tenant_id"] == 2
    assert item["call_id"] == "call-123"
    assert item["tenant_name"] == "Cabinet Test"
    assert item["result"] == "rdv"
    assert item["duration_sec"] == 120
    assert item["duration_min"] == 2
    assert item["started_at"].endswith("Z")
    assert item["last_event_at"].endswith("Z")


def test_build_call_item_falls_back_to_timestamps_for_duration():
    started = datetime(2026, 3, 18, 11, 0, 0, tzinfo=timezone.utc)
    ended = started + timedelta(seconds=89)
    row = {
        "tenant_id": 2,
        "call_id": "call-456",
        "customer_number": "",
        "started_at": started,
        "ended_at": ended,
        "updated_at": ended,
        "sort_ts": ended,
        "status": "ended",
        "ended_reason": "assistant-forwarded-call",
        "duration_sec": None,
        "last_event": None,
    }

    item = _build_call_item_from_vapi_row(row, "Cabinet Test")

    assert item["result"] == "transfer"
    assert item["duration_sec"] == 89
    assert item["duration_min"] == 1


def test_snapshot_outcome_keeps_legacy_labels_for_admin_widgets():
    assert _snapshot_outcome_from_sources("booking_confirmed", "ended", None) == "booking_confirmed"
    assert _snapshot_outcome_from_sources(None, "ended", "assistant-forwarded-call") == "transferred_human"
    assert _snapshot_outcome_from_sources(None, "ended", "customer-hangup") == "user_abandon"
