from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.public_bookings_pg import (
    _handoff_reason_to_callback_reason,
    _handoff_status_to_callback_status,
    sync_callback_status_from_handoff,
    upsert_callback_from_handoff,
)


def test_handoff_reason_mapping():
    assert _handoff_reason_to_callback_reason("urgent_non_vital_case") == "admin"
    assert _handoff_reason_to_callback_reason("explicit_human_request") == "other"
    assert _handoff_reason_to_callback_reason("unknown_reason") == "other"


def test_handoff_status_mapping():
    assert _handoff_status_to_callback_status("processed") == "processed"
    assert _handoff_status_to_callback_status("live_connected") == "new"
    assert _handoff_status_to_callback_status("callback_created") == "new"


def test_upsert_callback_from_handoff_uses_handoff_fields():
    handoff = {
        "id": 42,
        "call_id": "call_abc",
        "patient_phone": "+33612345678",
        "display_name": "Jean Dupont",
        "reason": "explicit_human_request",
        "status": "callback_created",
        "summary": "Le patient demande explicitement à parler à un humain.",
        "transcript_excerpt": "Patient: Je veux parler à quelqu'un.",
    }
    conn = MagicMock()
    cursor = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False
    cursor.fetchone.side_effect = [None]
    conn.cursor.return_value = cursor

    with patch("backend.public_bookings_pg.pg_connection", return_value=conn), patch(
        "backend.public_bookings_pg.set_tenant_id_on_connection"
    ):
        req_id = upsert_callback_from_handoff(12, handoff)

    assert req_id
    insert_sql = cursor.execute.call_args_list[-1][0][0]
    assert "INSERT INTO callback_requests" in insert_sql
    assert "'vocal_agent'" in insert_sql
    insert_params = cursor.execute.call_args_list[-1][0][1]
    assert insert_params[2] == "Jean Dupont"
    assert insert_params[3] == "+33612345678"
    assert insert_params[-2] == "call_abc"
    assert insert_params[-1] == 42


def test_sync_callback_status_from_handoff_updates_linked_row():
    handoff = {"id": 7, "status": "processed"}
    conn = MagicMock()
    cursor = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False
    conn.cursor.return_value = cursor

    with patch("backend.public_bookings_pg.pg_connection", return_value=conn), patch(
        "backend.public_bookings_pg.set_tenant_id_on_connection"
    ):
        sync_callback_status_from_handoff(12, handoff)

    update_sql = cursor.execute.call_args[0][0]
    update_params = cursor.execute.call_args[0][1]
    assert "UPDATE callback_requests" in update_sql
    assert update_params[0] == "processed"
    assert update_params[2] == 12
    assert update_params[3] == 7
