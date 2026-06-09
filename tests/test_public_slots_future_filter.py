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
    assert [s["id"] for s in kept] == ["4"]


def test_filter_future_public_slots_allows_same_day_when_explicit():
    ref = datetime(2026, 6, 4, 15, 0, 0)
    slots = [
        {"id": "1", "startIso": "2026-06-03T10:00:00", "label": "hier"},
        {"id": "2", "startIso": "2026-06-04T14:00:00", "label": "aujourd'hui passé"},
        {"id": "3", "startIso": "2026-06-04T16:00:00", "label": "aujourd'hui futur"},
        {"id": "4", "date": "2026-06-05", "time": "09:00", "label": "demain"},
    ]
    kept = routes._filter_future_public_slots(
        slots,
        now=ref,
        min_lead_minutes=30,
        allow_today_explicit=True,
    )
    assert [s["id"] for s in kept] == ["3", "4"]


def test_materialize_demo_slots_adds_start_iso():
    ref = datetime(2026, 6, 4, 15, 0, 0)  # jeudi
    materialized = routes._materialize_demo_slots(now=ref)
    assert materialized
    assert all(slot.get("startIso") and slot.get("date") for slot in materialized)
    kept = routes._filter_future_public_slots(materialized, now=ref, min_lead_minutes=30)
    assert kept


def test_materialize_demo_slots_on_friday_shows_upcoming_business_days():
    ref = datetime(2026, 6, 5, 10, 0, 0)  # vendredi
    materialized = routes._materialize_demo_slots(now=ref)
    labels = [slot["day"] for slot in materialized]
    assert labels.count("Auj.") == 2
    assert "Lun." in labels
    assert "Mar." in labels
    assert "Mer." not in labels
    assert "Jeu." not in labels
