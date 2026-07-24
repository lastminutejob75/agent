from datetime import date, datetime, time
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from backend.services.counter_schedule import (
    CounterSchedule,
    generate_counter_slots,
)


POST_ID = UUID("12345678-1234-5678-1234-567812345678")
ALGIERS = ZoneInfo("Africa/Algiers")
ROOT = Path(__file__).resolve().parents[1]


def pilot_schedule(**overrides) -> CounterSchedule:
    values = {
        "post_id": POST_ID,
        "weekdays": (0, 2, 4),
        "opens_at": time(10, 0),
        "closes_at": time(13, 0),
        "slot_minutes": 15,
        "timezone": "Africa/Algiers",
        "horizon_days": 60,
        "visa_category_filter": None,
    }
    values.update(overrides)
    return CounterSchedule(**values)


def test_pilot_rule_generates_twelve_slots_per_open_day():
    schedule = pilot_schedule(horizon_days=1)
    sunday_morning = datetime(2026, 7, 26, 9, 0, tzinfo=ALGIERS)

    slots = generate_counter_slots(schedule, now=sunday_morning)

    assert len(slots) == 12
    assert slots[0].start == datetime(2026, 7, 26, 10, 0, tzinfo=ALGIERS)
    assert slots[-1].start == datetime(2026, 7, 26, 12, 45, tzinfo=ALGIERS)
    assert slots[-1].end == datetime(2026, 7, 26, 13, 0, tzinfo=ALGIERS)


def test_pilot_rule_generates_thirty_six_slots_per_week():
    schedule = pilot_schedule(horizon_days=7)
    sunday_morning = datetime(2026, 7, 26, 9, 0, tzinfo=ALGIERS)

    slots = generate_counter_slots(schedule, now=sunday_morning)

    assert len(slots) == 36
    assert {slot.start.isoweekday() for slot in slots} == {2, 4, 7}


def test_closures_from_either_calendar_remove_the_whole_day():
    schedule = pilot_schedule(horizon_days=7)
    sunday_morning = datetime(2026, 7, 26, 9, 0, tzinfo=ALGIERS)

    slots = generate_counter_slots(
        schedule,
        now=sunday_morning,
        closure_dates={date(2026, 7, 28)},
    )

    assert len(slots) == 24
    assert all(slot.start.date() != date(2026, 7, 28) for slot in slots)


def test_past_and_current_slots_are_never_proposed():
    schedule = pilot_schedule(horizon_days=1)
    after_first_slots = datetime(2026, 7, 26, 10, 15, tzinfo=ALGIERS)

    slots = generate_counter_slots(schedule, now=after_first_slots)

    assert slots[0].start == datetime(2026, 7, 26, 10, 30, tzinfo=ALGIERS)
    assert all(slot.start > after_first_slots for slot in slots)


def test_category_rule_is_hidden_from_other_or_unknown_categories():
    schedule = pilot_schedule(
        horizon_days=1,
        visa_category_filter="D",
    )
    sunday_morning = datetime(2026, 7, 26, 9, 0, tzinfo=ALGIERS)

    assert generate_counter_slots(schedule, now=sunday_morning) == []
    assert generate_counter_slots(
        schedule,
        now=sunday_morning,
        visa_category="C",
    ) == []
    assert len(
        generate_counter_slots(
            schedule,
            now=sunday_morning,
            visa_category="D",
        )
    ) == 12


def test_limit_never_exposes_the_full_stock():
    schedule = pilot_schedule(horizon_days=60)
    sunday_morning = datetime(2026, 7, 26, 9, 0, tzinfo=ALGIERS)

    slots = generate_counter_slots(schedule, now=sunday_morning, limit=3)

    assert len(slots) == 3


def test_generator_uses_configured_timezone():
    schedule = pilot_schedule(horizon_days=1)
    utc_now = datetime(2026, 7, 26, 8, 0, tzinfo=ZoneInfo("UTC"))

    slots = generate_counter_slots(schedule, now=utc_now, limit=1)

    assert slots[0].start.utcoffset().total_seconds() == 3600
    assert slots[0].slot_start == "2026-07-26T10:00:00+01:00"


def test_invalid_schedule_bounds_are_rejected():
    with pytest.raises(ValueError, match="opens_at"):
        pilot_schedule(opens_at=time(13, 0), closes_at=time(10, 0))

    with pytest.raises(ValueError, match="weekdays"):
        pilot_schedule(weekdays=(0, 7))

    with pytest.raises(ValueError, match="horizon_days"):
        pilot_schedule(horizon_days=0)


def test_naive_reference_time_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        generate_counter_slots(
            pilot_schedule(horizon_days=1),
            now=datetime(2026, 7, 26, 9, 0),
        )


def test_schedule_migration_forces_post_rls_and_seeds_both_calendars():
    sql = (ROOT / "migrations" / "055_counter_schedule.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS counter_schedule" in sql
    assert "CREATE TABLE IF NOT EXISTS counter_closures" in sql
    assert "ALTER TABLE %I FORCE ROW LEVEL SECURITY" in sql
    assert "USING (app_post_matches(post_id))" in sql
    assert "ARRAY[0, 2, 4]::SMALLINT[]" in sql
    assert "'Africa/Algiers'" in sql
    assert "'DZ'" in sql
    assert "'BG'" in sql
    assert "Vendredi saint orthodoxe" in sql
    assert "Aïd el-Fitr" in sql
