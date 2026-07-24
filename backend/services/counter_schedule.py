"""Génération déterministe des créneaux du guichet consulaire."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Mapping, Optional, Sequence
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


VALID_VISA_CATEGORIES = frozenset({"A", "C", "D"})


@dataclass(frozen=True)
class CounterSchedule:
    post_id: UUID
    weekdays: tuple[int, ...]
    opens_at: time
    closes_at: time
    slot_minutes: int
    timezone: str
    horizon_days: int
    visa_category_filter: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.weekdays or any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("weekdays must contain values between 0 (Sunday) and 6")
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("weekdays must not contain duplicates")
        if self.opens_at >= self.closes_at:
            raise ValueError("opens_at must be before closes_at")
        if self.slot_minutes < 5 or self.slot_minutes > 180:
            raise ValueError("slot_minutes must be between 5 and 180")
        if self.horizon_days < 1 or self.horizon_days > 365:
            raise ValueError("horizon_days must be between 1 and 365")
        if (
            self.visa_category_filter is not None
            and self.visa_category_filter not in VALID_VISA_CATEGORIES
        ):
            raise ValueError("visa_category_filter must be A, C or D")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError(f"unknown timezone: {self.timezone}") from None


@dataclass(frozen=True)
class GeneratedCounterSlot:
    post_id: UUID
    start: datetime
    end: datetime
    visa_category_filter: Optional[str]

    @property
    def slot_start(self) -> str:
        return self.start.isoformat()

    @property
    def slot_end(self) -> str:
        return self.end.isoformat()


def _consular_weekday(day: date) -> int:
    """Convertit Monday=0 de Python vers Sunday=0 du schéma consulaire."""
    return (day.weekday() + 1) % 7


def schedule_from_row(row: Mapping[str, Any]) -> CounterSchedule:
    category = row.get("visa_category_filter")
    return CounterSchedule(
        post_id=UUID(str(row["post_id"])),
        weekdays=tuple(int(day) for day in row["weekdays"]),
        opens_at=row["opens_at"],
        closes_at=row["closes_at"],
        slot_minutes=int(row["slot_minutes"]),
        timezone=str(row["timezone"]),
        horizon_days=int(row["horizon_days"]),
        visa_category_filter=str(category) if category is not None else None,
    )


def generate_counter_slots(
    schedule: CounterSchedule,
    *,
    closure_dates: Iterable[date] = (),
    now: Optional[datetime] = None,
    visa_category: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[GeneratedCounterSlot]:
    """
    Génère les créneaux futurs sans les matérialiser.

    `weekdays` suit PostgreSQL EXTRACT(DOW) : dimanche=0. L'horizon contient
    exactement `horizon_days` dates civiles à partir de la date locale courante.
    """
    if visa_category is not None and visa_category not in VALID_VISA_CATEGORIES:
        raise ValueError("visa_category must be A, C or D")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    if schedule.visa_category_filter is not None:
        if visa_category is None or schedule.visa_category_filter != visa_category:
            return []

    zone = ZoneInfo(schedule.timezone)
    if now is None:
        local_now = datetime.now(zone)
    elif now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    else:
        local_now = now.astimezone(zone)

    closed = set(closure_dates)
    duration = timedelta(minutes=schedule.slot_minutes)
    generated: list[GeneratedCounterSlot] = []

    for offset in range(schedule.horizon_days):
        slot_date = local_now.date() + timedelta(days=offset)
        if slot_date in closed or _consular_weekday(slot_date) not in schedule.weekdays:
            continue

        cursor = datetime.combine(slot_date, schedule.opens_at, tzinfo=zone)
        closing = datetime.combine(slot_date, schedule.closes_at, tzinfo=zone)
        while cursor + duration <= closing:
            if cursor > local_now:
                generated.append(
                    GeneratedCounterSlot(
                        post_id=schedule.post_id,
                        start=cursor,
                        end=cursor + duration,
                        visa_category_filter=schedule.visa_category_filter,
                    )
                )
                if limit is not None and len(generated) >= limit:
                    return generated
            cursor += duration

    return generated


def generate_slots_for_schedules(
    schedules: Sequence[CounterSchedule],
    *,
    closure_dates: Iterable[date] = (),
    now: Optional[datetime] = None,
    visa_category: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[GeneratedCounterSlot]:
    slots: dict[tuple[UUID, datetime], GeneratedCounterSlot] = {}
    for schedule in schedules:
        for slot in generate_counter_slots(
            schedule,
            closure_dates=closure_dates,
            now=now,
            visa_category=visa_category,
        ):
            slots[(slot.post_id, slot.start)] = slot
    ordered = sorted(slots.values(), key=lambda slot: slot.start)
    return ordered[:limit] if limit is not None else ordered


def load_post_counter_slots(
    conn: Any,
    post_id: UUID,
    *,
    now: Optional[datetime] = None,
    visa_category: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[GeneratedCounterSlot]:
    """Charge la configuration sous RLS puis génère les créneaux en mémoire."""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT post_id, weekdays, opens_at, closes_at, slot_minutes,
                   timezone, horizon_days, visa_category_filter
            FROM counter_schedule
            WHERE post_id = %s
              AND (visa_category_filter IS NULL OR visa_category_filter = %s)
            ORDER BY visa_category_filter NULLS FIRST
            """,
            (post_id, visa_category),
        )
        schedules = [schedule_from_row(row) for row in cursor.fetchall()]

    if not schedules:
        return []

    zone = ZoneInfo(schedules[0].timezone)
    local_now = now.astimezone(zone) if now is not None else datetime.now(zone)
    max_horizon = max(schedule.horizon_days for schedule in schedules)
    last_date = local_now.date() + timedelta(days=max_horizon - 1)

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT date
            FROM counter_closures
            WHERE post_id = %s
              AND date BETWEEN %s AND %s
            """,
            (post_id, local_now.date(), last_date),
        )
        closures = {row["date"] for row in cursor.fetchall()}

    return generate_slots_for_schedules(
        schedules,
        closure_dates=closures,
        now=local_now,
        visa_category=visa_category,
        limit=limit,
    )
