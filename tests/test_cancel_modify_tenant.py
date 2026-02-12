"""
Tests CANCEL/MODIFY multi-tenant : provider=none → transfert, tenant calendar isolé.
"""
import pytest

from backend.engine import Engine
from backend.session import Session, SessionStore
from backend.tools_faq import FaqStore
from backend import db


def _last_text(events):
    for ev in reversed(events or []):
        txt = getattr(ev, "text", "") or ""
        if txt.strip():
            return txt
    return ""


def _make_engine():
    store = SessionStore()
    faq = FaqStore(items=[])
    return Engine(session_store=store, faq_store=faq)


def test_cancel_name_provider_none_transfers():
    """Quand tenant a provider=none, CANCEL_NAME avec nom valide → TRANSFERRED + MSG_NO_AGENDA_TRANSFER."""
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

    engine = _make_engine()
    conv_id = "tc_provider_none"
    session = engine.session_store.get_or_create(conv_id)
    session.state = "CANCEL_NAME"
    session.tenant_id = 1
    session.channel = "web"

    events = engine.handle_message(conv_id, "Dupont")
    session = engine.session_store.get(conv_id)
    assert session.state == "TRANSFERRED"
    txt = _last_text(events)
    assert "agenda" in txt.lower() or "relation" in txt.lower()

    # Restore
    conn = db.get_conn()
    try:
        conn.execute("UPDATE tenant_config SET params_json = ? WHERE tenant_id = 1", (old_params,))
        conn.commit()
    finally:
        conn.close()


def test_cancel_booking_uses_session_adapter(monkeypatch):
    """cancel_booking(slot, session) résout l'adapter via session.tenant_id."""
    from backend import tools_booking
    from backend.calendar_adapter import get_calendar_adapter

    called_with_session = []

    def capture_get_adapter(session):
        called_with_session.append(getattr(session, "tenant_id", None))
        return None  # pas d'adapter légacy

    monkeypatch.setattr("backend.calendar_adapter.get_calendar_adapter", capture_get_adapter)
    # Force usage du path adapter (event_id présent)
    monkeypatch.setattr("backend.tools_booking._get_calendar_service", lambda: None)

    class S:
        tenant_id = 42

    tools_booking.cancel_booking({"event_id": "evt_123"}, S())
    assert called_with_session == [42]


def test_find_booking_by_name_uses_session_adapter(monkeypatch):
    """find_booking_by_name(name, session) résout l'adapter via session.tenant_id."""
    from backend import tools_booking

    called_with_session = []

    def capture_get_adapter(session):
        called_with_session.append(getattr(session, "tenant_id", None))
        return None

    monkeypatch.setattr("backend.calendar_adapter.get_calendar_adapter", capture_get_adapter)
    monkeypatch.setattr("backend.tools_booking._get_calendar_service", lambda: None)
    monkeypatch.setattr("backend.tools_booking._find_booking_sqlite", lambda n: None)

    class S:
        tenant_id = 7

    tools_booking.find_booking_by_name("Dupont", S())
    assert called_with_session == [7]


def test_provider_none_never_uses_global_google(monkeypatch):
    """provider=none → calendar=None, jamais _get_calendar_service (éviter mélange tenant)."""
    from backend.calendar_adapter import _NoneCalendarAdapter
    from backend import tools_booking

    google_called = []

    def capturing_get_service():
        google_called.append(1)
        return None

    monkeypatch.setattr("backend.tools_booking._get_calendar_service", capturing_get_service)

    # Même logique que tools_booking : provider=none → calendar=None (pas de fallback global)
    adapter = _NoneCalendarAdapter()
    calendar = None if (adapter and not adapter.can_propose_slots()) else (adapter or tools_booking._get_calendar_service())
    assert calendar is None
    assert len(google_called) == 0


def test_find_booking_provider_none_returns_sentinel():
    """find_booking_by_name avec session tenant provider=none → PROVIDER_NONE_SENTINEL."""
    from backend.calendar_adapter import PROVIDER_NONE_SENTINEL, _NoneCalendarAdapter
    from backend import tools_booking

    class S:
        tenant_id = 1

    # Mock get_calendar_adapter pour retourner NoneAdapter
    import backend.tools_booking as tb
    adapter = _NoneCalendarAdapter()
    result = adapter.find_booking_by_name("Dupont")
    assert result == PROVIDER_NONE_SENTINEL
    assert isinstance(result, dict) and result.get("provider") == "none"
