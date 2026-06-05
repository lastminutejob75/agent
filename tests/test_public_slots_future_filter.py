from datetime import datetime

from backend.routes import public_pages as routes


def test_filter_future_public_slots_drops_past_and_keeps_future():
    ref = datetime(2026, 6, 4, 15, 0, 0)
    slots = [
        {"id": "1", "startIso": "2026-06-03T10:00:00", "label": "hier"},
        {"id": "2", "startIso": "2026-06-04T14:00:00", "label": "aujourd'hui passé"},
        {"id": "3", "startIso": "2026-06-04T16:00:00", "label": "aujourd'hui futur"},
        {"id": "4", "date": "2026-06-05", "time": "09:00", "label": "demain"},
    ]
    kept = routes._filter_future_public_slots(slots, now=ref, min_lead_minutes=30)
    assert [s["id"] for s in kept] == ["3", "4"]


def test_materialize_demo_slots_adds_start_iso():
    ref = datetime(2026, 6, 4, 15, 0, 0)  # jeudi
    materialized = routes._materialize_demo_slots(now=ref)
    assert materialized
    assert all(slot.get("startIso") and slot.get("date") for slot in materialized)
    kept = routes._filter_future_public_slots(materialized, now=ref, min_lead_minutes=30)
    assert kept
