from unittest.mock import patch

from backend import tools_booking


class _FakeCalendar:
    def __init__(self):
        self.calls = []

    def get_free_slots_range(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("per_day_limit", 1) > 1:
            return [
                {"start": "2026-03-31T16:00:00+02:00", "label": "Mardi 31 mars à 16 heures"},
                {"start": "2026-03-31T16:30:00+02:00", "label": "Mardi 31 mars à 16 heures 30"},
                {"start": "2026-04-01T16:15:00+02:00", "label": "Mercredi 1 avril à 16 heures 15"},
                {"start": "2026-04-01T16:45:00+02:00", "label": "Mercredi 1 avril à 16 heures 45"},
            ]
        return [
            {"start": "2026-03-31T16:00:00+02:00", "label": "Mardi 31 mars à 16 heures"},
            {"start": "2026-04-01T16:15:00+02:00", "label": "Mercredi 1 avril à 16 heures 15"},
            {"start": "2026-04-02T16:00:00+02:00", "label": "Jeudi 2 avril à 16 heures"},
        ]


@patch(
    "backend.tenant_config.get_booking_rules",
    return_value={
        "duration_minutes": 15,
        "start_hour": 9,
        "end_hour": 18,
        "booking_days": [0, 1, 2, 3, 4],
        "buffer_minutes": 0,
    },
)
def test_google_pool_requests_richer_batch_for_explicit_time_constraint(_mock_rules):
    calendar = _FakeCalendar()

    pool = tools_booking._get_slots_from_google_calendar(
        calendar,
        limit=3,
        pref="après-midi",
        tenant_id=1,
        preferred_minute=16 * 60 + 30,
        preferred_time_type="after",
    )

    assert calendar.calls, "Le batch Google doit être utilisé."
    assert calendar.calls[0]["per_day_limit"] >= 4
    starts = [slot.start for slot in pool]
    assert "2026-03-31T16:30:00+02:00" in starts
    assert "2026-04-01T16:45:00+02:00" in starts
