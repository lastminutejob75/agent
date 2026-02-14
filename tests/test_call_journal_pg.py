# tests/test_call_journal_pg.py
"""
P0 Option B: Tests journal + checkpoints (Phase 1 dual-write).
T1: dual-write crée call_session et messages
T2: checkpoint écrit sur changement d'état
T3: PG down ne casse pas le flow (log WARN, continue)
T4 (optionnel): session_from_dict restaure les champs clés
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from backend.session_codec import session_to_dict, session_from_dict
from backend.session import Session, QualifData


# ========== T4: session_from_dict ==========
def test_session_from_dict_restores_key_fields():
    """Vérifie que session_from_dict restaure les champs essentiels."""
    conv_id = "test_conv_001"
    d = {
        "state": "WAIT_CONFIRM",
        "channel": "vocal",
        "qualif_step": "contact",
        "qualif_data": {
            "name": "Henri",
            "motif": "consultation",
            "pref": "matin",
            "contact": "0612345678",
            "contact_type": "phone",
        },
        "pending_slots_display": [
            {"idx": 1, "label": "Lundi 9h", "slot_id": 42, "start": "2026-02-16T09:00:00", "source": "sqlite"},
        ],
        "pending_slot_choice": 1,
        "transfer_budget_remaining": 2,
    }
    session = session_from_dict(conv_id, d)
    assert session.conv_id == conv_id
    assert session.state == "WAIT_CONFIRM"
    assert session.channel == "vocal"
    assert session.qualif_data.name == "Henri"
    assert session.qualif_data.contact == "0612345678"
    assert session.pending_slot_choice == 1
    assert len(session.pending_slots_display) == 1
    assert session.transfer_budget_remaining == 2


def test_session_to_dict_excludes_secrets():
    """Vérifie qu'aucun secret n'est dans state_json."""
    session = Session(conv_id="test")
    session.state = "QUALIF_NAME"
    session.qualif_data.name = "Jean"
    d = session_to_dict(session)
    assert "state" in d
    assert "qualif_data" in d
    # Pas de token, credentials, etc.
    for k, v in d.items():
        if isinstance(v, str) and v:
            assert "token" not in k.lower()
            assert "secret" not in k.lower()
            assert "password" not in k.lower()


# ========== T1, T2, T3: nécessitent PG ou mock ==========
@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL") and not os.environ.get("PG_EVENTS_URL"),
    reason="DATABASE_URL or PG_EVENTS_URL required for PG tests",
)
def test_dual_write_creates_call_session_and_messages():
    """T1: crée session, envoie 1 user + 1 agent, vérifie call_sessions et call_messages."""
    from backend.session_pg import (
        pg_ensure_call_session,
        pg_add_message,
        pg_list_messages_since,
    )

    tenant_id = 1
    call_id = f"test_dual_{__import__('uuid').uuid4().hex[:12]}"

    ok = pg_ensure_call_session(tenant_id, call_id, "START")
    assert ok is True

    seq1 = pg_add_message(tenant_id, call_id, "user", "Bonjour")
    assert seq1 == 1

    seq2 = pg_add_message(tenant_id, call_id, "agent", "Bonjour, comment puis-je vous aider ?")
    assert seq2 == 2

    msgs = pg_list_messages_since(tenant_id, call_id, 0)
    assert len(msgs) == 2
    assert msgs[0][1] == "user"
    assert msgs[0][2] == "Bonjour"
    assert msgs[1][1] == "agent"


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL") and not os.environ.get("PG_EVENTS_URL"),
    reason="DATABASE_URL or PG_EVENTS_URL required for PG tests",
)
def test_checkpoint_written_on_state_change():
    """T2: simule state START -> WAIT_CONFIRM, vérifie checkpoint."""
    from backend.session_pg import (
        pg_ensure_call_session,
        pg_add_message,
        pg_update_last_state,
        pg_write_checkpoint,
        pg_get_latest_checkpoint,
    )
    from backend.session_codec import session_to_dict

    tenant_id = 1
    call_id = f"test_cp_{__import__('uuid').uuid4().hex[:12]}"

    pg_ensure_call_session(tenant_id, call_id, "START")
    seq = pg_add_message(tenant_id, call_id, "agent", "Voici trois créneaux...")
    assert seq is not None

    session = Session(conv_id=call_id)
    session.state = "WAIT_CONFIRM"
    session.tenant_id = tenant_id
    session.pending_slots_display = [{"idx": 1, "label": "Lundi 9h", "slot_id": 1}]

    pg_update_last_state(tenant_id, call_id, "WAIT_CONFIRM")
    pg_write_checkpoint(tenant_id, call_id, seq, session_to_dict(session))

    cp = pg_get_latest_checkpoint(tenant_id, call_id)
    assert cp is not None
    cp_seq, state_json = cp
    assert cp_seq == seq
    assert state_json.get("state") == "WAIT_CONFIRM"


def test_pg_down_does_not_break_flow_phase1():
    """T3: PG non configuré (url=None) → pas de crash, retourne False/None."""
    with patch("backend.session_pg._pg_url", return_value=None):
        from backend.session_pg import pg_ensure_call_session, pg_add_message

        ok = pg_ensure_call_session(1, "test_no_pg", "START")
        assert ok is False

        seq = pg_add_message(1, "test_no_pg", "user", "test")
        assert seq is None


# ========== Phase 2: PG-first resume ==========
@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL") and not os.environ.get("PG_EVENTS_URL"),
    reason="DATABASE_URL or PG_EVENTS_URL required for PG tests",
)
def test_resume_session_from_pg_checkpoint():
    """T1 Phase 2: reprise session depuis checkpoint PG (Option A snapshot)."""
    from backend.session_pg import (
        pg_ensure_call_session,
        pg_add_message,
        pg_write_checkpoint,
        load_session_pg_first,
    )

    tenant_id = 1
    call_id = f"test_resume_{__import__('uuid').uuid4().hex[:12]}"

    pg_ensure_call_session(tenant_id, call_id, "START")
    pg_add_message(tenant_id, call_id, "user", "Bonjour")
    seq = pg_add_message(tenant_id, call_id, "agent", "Voici trois créneaux...")
    assert seq == 2

    state_json = {
        "state": "WAIT_CONFIRM",
        "channel": "vocal",
        "qualif_data": {"name": "Marie", "motif": "consultation", "pref": "matin", "contact": "0612345678", "contact_type": "phone"},
        "pending_slots_display": [
            {"idx": 1, "label": "Mardi 10h", "slot_id": 10, "start": "2026-02-18T10:00:00", "source": "google"},
        ],
        "awaiting_confirmation": "CONFIRM_SLOT",
    }
    pg_write_checkpoint(tenant_id, call_id, seq, state_json)

    result = load_session_pg_first(tenant_id, call_id)
    assert result is not None
    session, ck_seq, last_seq = result
    assert session.state == "WAIT_CONFIRM"
    assert session.awaiting_confirmation == "CONFIRM_SLOT"
    assert len(session.pending_slots_display) == 1
    assert session.pending_slots_display[0]["label"] == "Mardi 10h"
    assert ck_seq == seq


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL") and not os.environ.get("PG_EVENTS_URL"),
    reason="DATABASE_URL or PG_EVENTS_URL required for PG tests",
)
def test_resume_falls_back_to_memory_when_no_checkpoint():
    """T2 Phase 2: pas de checkpoint → load_session_pg_first returns None → get_or_create → START."""
    from backend.session_pg import load_session_pg_first

    tenant_id = 1
    call_id = f"test_no_ck_{__import__('uuid').uuid4().hex[:12]}"

    result = load_session_pg_first(tenant_id, call_id)
    assert result is None


def test_resume_pg_down_does_not_break():
    """T3 Phase 2: mock PG raise → fallback in-memory, log warn, pas de crash."""
    import uuid
    from backend.routes.voice import _get_or_resume_voice_session

    call_id = f"test_pg_down_{uuid.uuid4().hex[:12]}"
    with patch("backend.config.USE_PG_CALL_JOURNAL", True):
        with patch("backend.session_pg.load_session_pg_first", side_effect=Exception("connection refused")):
            session = _get_or_resume_voice_session(1, call_id)
    assert session is not None
    assert session.conv_id == call_id
    assert session.state == "START"
