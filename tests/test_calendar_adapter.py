"""Tests CalendarAdapter (provider par tenant)."""
import pytest
from backend.calendar_adapter import get_calendar_adapter, _NoneCalendarAdapter, _GoogleCalendarAdapter
from backend.tenant_config import get_params, set_flags


def _make_session(tenant_id=1):
    class S:
        pass
    s = S()
    s.tenant_id = tenant_id
    return s


def test_none_adapter_returns_empty_slots():
    """provider=none → 0 créneaux."""
    adapter = _NoneCalendarAdapter()
    from datetime import datetime
    slots = adapter.get_free_slots(datetime.now(), limit=3)
    assert slots == []
    assert adapter.can_propose_slots() is False


def test_none_adapter_book_returns_none():
    adapter = _NoneCalendarAdapter()
    assert adapter.book_appointment("2026-01-15T10:00:00", "2026-01-15T10:15:00", "Test", "", "Consult") is None


def test_get_adapter_provider_none():
    """Tenant avec calendar_provider=none → NoneAdapter."""
    from backend import db
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        cur = conn.execute("SELECT params_json FROM tenant_config WHERE tenant_id = 1")
        row = cur.fetchone()
        old_params = row[0] if row else "{}"
        conn.execute(
            "UPDATE tenant_config SET params_json = ? WHERE tenant_id = 1",
            ('{"calendar_provider": "none"}',)
        )
        conn.commit()
    finally:
        conn.close()

    session = _make_session(1)
    adapter = get_calendar_adapter(session)
    assert adapter is not None
    assert isinstance(adapter, _NoneCalendarAdapter)
    assert adapter.can_propose_slots() is False

    # Restore
    conn = db.get_conn()
    try:
        conn.execute("UPDATE tenant_config SET params_json = ? WHERE tenant_id = 1", (old_params,))
        conn.commit()
    finally:
        conn.close()


def test_get_adapter_default_uses_global():
    """Pas de params ou provider vide → fallback config global (GoogleAdapter ou None)."""
    session = _make_session(1)
    adapter = get_calendar_adapter(session)
    # Si GOOGLE_CALENDAR_ID configuré → GoogleAdapter, sinon None
    if adapter is not None:
        assert isinstance(adapter, (_GoogleCalendarAdapter, _NoneCalendarAdapter))
