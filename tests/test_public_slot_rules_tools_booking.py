from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

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
