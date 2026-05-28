from backend.routes.tenant import _looks_like_google_event_id, _resolve_google_event_id_for_booking


def test_looks_like_google_event_id():
    assert _looks_like_google_event_id("abc123xyz") is True
    assert _looks_like_google_event_id("42") is False
    assert _looks_like_google_event_id("") is False
    assert _looks_like_google_event_id(None) is False


def test_resolve_google_event_id_prefers_stored_on_appointment():
    detail = {
        "params": {
            "calendar_provider": "google",
            "calendar_id": "cabinet@test.calendar.google.com",
            "timezone": "Europe/Paris",
        }
    }
    local = {
        "id": 321,
        "slot_id": 654,
        "google_event_id": "evt_persisted",
        "contact": "+33612345678",
        "name": "Claire",
    }
    resolved = _resolve_google_event_id_for_booking(
        12,
        detail,
        local_booking=local,
    )
    assert resolved == "evt_persisted"


def test_resolve_google_event_id_uses_explicit_external_id():
    detail = {
        "params": {
            "calendar_provider": "google",
            "calendar_id": "cabinet@test.calendar.google.com",
        }
    }
    local = {"id": 321, "slot_id": 654, "google_event_id": "evt_stored"}
    resolved = _resolve_google_event_id_for_booking(
        12,
        detail,
        explicit_event_id="evt_explicit",
        local_booking=local,
    )
    assert resolved == "evt_explicit"
