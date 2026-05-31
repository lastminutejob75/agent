"""Tests changement de numéro patient (identifiant fiche)."""

from __future__ import annotations

import pytest

from backend.db import (
    PatientPhoneChangeError,
    change_cabinet_client_phone,
    get_cabinet_client_by_phone,
    get_conn,
    insert_patient_note,
    upsert_cabinet_client,
)
from backend.patient_v2_db import ensure_patient_v2_schema


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.db.DB_PATH", str(tmp_path / "phone_change.db"))
    monkeypatch.setattr("backend.db._pg_events_url", lambda: None)
    monkeypatch.setattr("backend.patient_v2_db._pg_events_url", lambda: None)
    import backend.db as db

    db.init_db()
    ensure_patient_v2_schema()
    return db


def test_change_cabinet_client_phone_updates_profile_and_notes(sqlite_db):
    tenant_id = 1
    old_phone = "+33611111111"
    new_phone = "+33622222222"
    upsert_cabinet_client(tenant_id, old_phone, raw_name="Alice")
    insert_patient_note(tenant_id, old_phone, note_text="Note test", author="Praticien")

    updated = change_cabinet_client_phone(tenant_id, old_phone, new_phone)

    assert updated is not None
    assert updated["phone"] == new_phone
    assert get_cabinet_client_by_phone(tenant_id, old_phone) is None
    assert get_cabinet_client_by_phone(tenant_id, new_phone) is not None

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT patient_phone FROM patient_notes WHERE tenant_id = ? AND patient_phone = ?",
            (tenant_id, new_phone),
        ).fetchone()
        assert row is not None
    finally:
        conn.close()


def test_change_cabinet_client_phone_propagates_v2_events(sqlite_db):
    tenant_id = 1
    old_phone = "+33633334444"
    new_phone = "+33655556666"
    upsert_cabinet_client(tenant_id, old_phone, raw_name="Bob")
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO patient_events (id, tenant_id, patient_phone, type, payload_json, occurred_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            ("evt-test-1", tenant_id, old_phone, "call", "{}"),
        )
        conn.commit()
    finally:
        conn.close()

    change_cabinet_client_phone(tenant_id, old_phone, new_phone)

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT patient_phone FROM patient_events WHERE tenant_id = ? AND patient_phone = ?",
            (tenant_id, new_phone),
        ).fetchone()
        assert row is not None
    finally:
        conn.close()


def test_change_cabinet_client_phone_same_number_noop(sqlite_db):
    tenant_id = 1
    phone = "+33677778888"
    upsert_cabinet_client(tenant_id, phone, raw_name="Claire")

    result = change_cabinet_client_phone(tenant_id, phone, phone)

    assert result["phone"] == phone


def test_change_cabinet_client_phone_conflict(sqlite_db):
    tenant_id = 1
    upsert_cabinet_client(tenant_id, "+33610101010", raw_name="Paul")
    upsert_cabinet_client(tenant_id, "+33620202020", raw_name="Marie")

    with pytest.raises(PatientPhoneChangeError) as exc:
        change_cabinet_client_phone(tenant_id, "+33610101010", "+33620202020")

    assert exc.value.code == "phone_conflict"


def test_change_cabinet_client_phone_invalid(sqlite_db):
    tenant_id = 1
    upsert_cabinet_client(tenant_id, "+33630303030", raw_name="Luc")

    with pytest.raises(PatientPhoneChangeError) as exc:
        change_cabinet_client_phone(tenant_id, "+33630303030", "abc")

    assert exc.value.code == "invalid_phone"
