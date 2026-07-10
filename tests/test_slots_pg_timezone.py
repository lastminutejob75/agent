from contextlib import contextmanager
from datetime import datetime, timezone
import sys
from types import ModuleType


def test_start_ts_to_date_time_converts_to_tenant_timezone():
    from backend.slots_pg import _start_ts_to_date_time

    assert _start_ts_to_date_time(
        datetime(2026, 7, 15, 14, 0, tzinfo=timezone.utc),
        "America/Montreal",
    ) == ("2026-07-15", "10:00")


def test_pg_slot_lookup_uses_tenant_timezone_parameter(monkeypatch):
    from backend import slots_pg

    executed = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            executed.append((sql, params))

        def fetchone(self):
            return None

    class Conn:
        def cursor(self):
            return Cursor()

    @contextmanager
    def fake_connect(url, tenant_id=None, **kwargs):
        assert tenant_id == 12
        yield Conn()

    fake_psycopg = ModuleType("psycopg")
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr(slots_pg, "_pg_url", lambda: "postgresql://test")
    monkeypatch.setattr(slots_pg, "_connect_pg", fake_connect)

    result = slots_pg.pg_find_slot_id_by_datetime(
        "2026-07-15",
        "10:00",
        tenant_id=12,
        tz_name="America/Montreal",
    )

    assert result is None
    assert executed[0][1] == (
        12,
        "America/Montreal",
        "2026-07-15",
        "America/Montreal",
        "10:00",
    )
