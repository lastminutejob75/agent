# tests/test_call_resume_pg.py
"""
P0 Option B Phase 2: Tests PG-first read / resume.
T1: reprise session depuis checkpoint PG
T2: pas de checkpoint → fallback get_or_create (START)
T3: PG down → fallback in-memory, pas de crash
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from backend.session import Session
from backend.session_codec import session_to_dict


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL") and not os.environ.get("PG_EVENTS_URL"),
    reason="DATABASE_URL or PG_EVENTS_URL required for PG tests",
)
def test_resume_session_from_pg_checkpoint():
    """T1: écrit checkpoint WAIT_CONFIRM, simule restart, load_session_pg_first → session rehydratée."""
    from backend.session_pg import (
        pg_ensure_call_session,
        pg_add_message,
        pg_write_checkpoint,
        load_session_pg_first,
    )

    tenant_id = 1
    call_id = f"test_resume_{__import__('uuid').uuid4().hex[:12]}"

    pg_ensure_call_session(tenant_id, call_id, "START")
    seq = pg_add_message(tenant_id, call_id, "agent", "Voici trois créneaux...")
    assert seq is not None

    session = Session(conv_id=call_id)
    session.state = "WAIT_CONFIRM"
    session.tenant_id = tenant_id
    session.awaiting_confirmation = "CONFIRM_SLOT"
    session.pending_slots_display = [
        {"idx": 1, "label": "Lundi 9h", "slot_id": 42, "start": "2026-02-16T09:00:00", "source": "sqlite"},
        {"idx": 2, "label": "Mardi 10h", "slot_id": 43, "start": "2026-02-17T10:00:00", "source": "sqlite"},
    ]
    session.pending_slots = [
        type("SlotDisplay", (), {"idx": 1, "label": "Lundi 9h", "slot_id": 42, "start": "2026-02-16T09:00:00", "source": "sqlite"})(),
        type("SlotDisplay", (), {"idx": 2, "label": "Mardi 10h", "slot_id": 43, "start": "2026-02-17T10:00:00", "source": "sqlite"})(),
    ]

    state_json = session_to_dict(session)
    pg_write_checkpoint(tenant_id, call_id, seq, state_json)

    # Simuler restart: session_store vide, load depuis PG
    result = load_session_pg_first(tenant_id, call_id)
    assert result is not None
    s_pg, ck_seq, last_seq = result

    assert s_pg.state == "WAIT_CONFIRM"
    assert s_pg.awaiting_confirmation == "CONFIRM_SLOT"
    assert len(s_pg.pending_slots_display) == 2
    assert s_pg.conv_id == call_id
    assert s_pg.tenant_id == tenant_id
    assert s_pg.channel == "vocal"
    assert ck_seq == seq


def test_resume_falls_back_to_memory_when_no_checkpoint():
    """T2: pas de checkpoint en PG → load_session_pg_first returns None → get_or_create → START."""
    with patch("backend.session_pg._pg_url", return_value="postgres://fake") as _:
        with patch("backend.session_pg.pg_get_latest_checkpoint", return_value=None):
            from backend.session_pg import load_session_pg_first

            result = load_session_pg_first(1, "call_no_ck")
            assert result is None


def test_resume_pg_down_does_not_break():
    """T3: PG raise Exception → load_session_pg_first catch, fallback in-memory, pas de crash."""
    from backend.routes.voice import _get_or_resume_voice_session

    call_id = f"call_pg_down_{__import__('uuid').uuid4().hex[:12]}"

    with patch("backend.routes.voice.config") as mock_config:
        mock_config.USE_PG_CALL_JOURNAL = True
        with patch("backend.session_pg.load_session_pg_first", side_effect=Exception("connection refused")):
            # get(call_id) → None (nouveau call_id), load raise → except log warn → get_or_create
            session = _get_or_resume_voice_session(1, call_id)
            assert session is not None
            assert session.conv_id == call_id
            assert session.state == "START"
