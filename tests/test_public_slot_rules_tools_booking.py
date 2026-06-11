from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend import tools_booking


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 6, 9, 14, 0, 0)


def test_context_min_start_public_defaults_to_tomorrow():
    session = SimpleNamespace(booking_origin="public_page", appointment_preferences={})
    with patch("backend.tools_booking.datetime", _FixedDateTime):
        out = tools_booking._context_min_start_datetime(
            pref=None,
            target_date_obj=None,
            weekday_pref=None,
            session=session,
            channel="web",
        )
    assert out == _FixedDateTime(2026, 6, 10, 0, 0, 0)


def test_context_min_start_public_allows_today_when_explicit():
    session = SimpleNamespace(booking_origin="public_page", appointment_preferences={})
    with patch("backend.tools_booking.datetime", _FixedDateTime):
        out = tools_booking._context_min_start_datetime(
            pref="aujourd'hui",
            target_date_obj=None,
            weekday_pref=None,
            session=session,
            channel="web",
        )
    assert out == _FixedDateTime(2026, 6, 9, 15, 0, 0)


def test_has_explicit_today_request_with_current_date_in_preferences():
    today = date(2026, 6, 9)
    session = SimpleNamespace(
        appointment_preferences={
            "earliest_date": "2026-06-09",
            "latest_date": "2026-06-09",
        }
    )
    assert tools_booking._has_explicit_today_request(
        pref=None,
        target_date_obj=None,
        weekday_pref=None,
        session=session,
        today=today,
    )


def test_get_slots_from_google_calendar_converts_utc_to_tenant_local_day():
    class FakeCalendar:
        def get_free_slots_range(self, **kwargs):
            return [
                {
                    "start": "2026-06-10T22:30:00+00:00",
                    "end": "2026-06-10T22:45:00+00:00",
                    "label": "slot-utc",
                }
            ]

    rules = {
        "duration_minutes": 15,
        "start_hour": 9,
        "end_hour": 18,
        "booking_days": [0, 1, 2, 3, 4],
        "buffer_minutes": 0,
    }
    with patch("backend.tenant_config.get_booking_rules", return_value=rules):
        with patch("backend.tools_booking._tenant_zoneinfo", return_value=ZoneInfo("Europe/Paris")):
            out = tools_booking._get_slots_from_google_calendar(
                FakeCalendar(),
                limit=1,
                pref=None,
                tenant_id=1,
                target_date=date(2026, 6, 11),
            )

    assert len(out) == 1
    # 22:30 UTC = 00:30 Europe/Paris (lendemain)
    assert out[0].start.startswith("2026-06-11T00:30:00")
