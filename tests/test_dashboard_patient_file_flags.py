"""Règle identité patient sur le dashboard — alignée agenda (`patient_has_file`) et journal."""

from __future__ import annotations


def test_dashboard_patient_file_has_validated_identity_pure():
    from backend.routes.tenant import _dashboard_patient_file_has_validated_identity

    assert _dashboard_patient_file_has_validated_identity(None) is False
    assert _dashboard_patient_file_has_validated_identity({}) is False
    assert _dashboard_patient_file_has_validated_identity({"validated_name": ""}) is False
    assert _dashboard_patient_file_has_validated_identity({"validated_name": " A "}) is False
    assert _dashboard_patient_file_has_validated_identity({"validated_name": "Jean M"}) is True


def test_is_agenda_dummy_phone():
    from backend.routes.tenant import _is_agenda_dummy_phone

    assert _is_agenda_dummy_phone("") is True
    assert _is_agenda_dummy_phone("+00000000") is True
    assert _is_agenda_dummy_phone("+33000000000") is True
    assert _is_agenda_dummy_phone("+33612345678") is False


def test_decorate_agenda_slots_patient_has_file_by_name_when_dummy_phone(monkeypatch):
    from backend.routes.tenant import _decorate_agenda_slots_patient_has_file

    monkeypatch.setattr(
        "backend.routes.tenant.get_cabinet_client_by_phone",
        lambda tenant_id, phone: None,
    )
    monkeypatch.setattr(
        "backend.routes.tenant.search_cabinet_clients",
        lambda tenant_id, q, limit=8: [
            {
                "phone": "+33611111111",
                "display_name": "Napoleon Bonaparte",
                "validated_name": "Napoleon Bonaparte",
            }
        ],
    )

    slots = [{"patient_phone": "+00000000", "patient": "Napoleon Bonaparte", "hour": "09h"}]
    cache: dict = {}
    _decorate_agenda_slots_patient_has_file(1, slots, cache)
    assert slots[0]["patient_has_file"] is True


def test_decorate_agenda_slots_patient_has_file(monkeypatch):
    from backend.routes.tenant import _decorate_agenda_slots_patient_has_file

    def _cabinet_stub(tenant_id: int, phone: str):
        assert tenant_id == 1
        if phone == "+33600000002":
            return {"validated_name": "Marie Dupont", "display_name": "Marie Dupont"}
        return None

    monkeypatch.setattr(
        "backend.routes.tenant.get_cabinet_client_by_phone",
        _cabinet_stub,
    )

    slots = [{"patient_phone": "+33600000001", "hour": "10h"}, {"patient_phone": "+33600000002", "hour": "11h"}]
    cache: dict = {}
    _decorate_agenda_slots_patient_has_file(1, slots, cache)
    assert slots[0]["patient_has_file"] is False
    assert slots[1]["patient_has_file"] is True


def test_agenda_bulk_lightweight_still_decorates_patient_has_file(monkeypatch):
    """Le mode lightweight bulk doit quand même peupler patient_has_file (lookup batch)."""
    from backend.routes.tenant import (
        _decorate_agenda_slots_patient_has_file,
        _warm_agenda_profiles_from_slots_patient_phone,
    )

    slots = [{"patient_phone": "+33612345678", "hour": "10h"}]
    cache: dict = {}

    monkeypatch.setattr(
        "backend.routes.tenant.get_cabinet_clients_by_phones",
        lambda tenant_id, phones: {"+33612345678": {"phone": "+33612345678", "display_name": "Claire"}},
    )

    _warm_agenda_profiles_from_slots_patient_phone(1, slots, cache)
    _decorate_agenda_slots_patient_has_file(1, slots, cache)
    assert slots[0]["patient_has_file"] is True


def test_get_cabinet_client_by_phone_matches_national_stored_format(monkeypatch):
    """Une fiche stockée en 06xxxxxxxx doit matcher une recherche +33xxxxxxxxxx."""
    from backend import db

    stored = {"phone": "0612345678", "display_name": "Jean Dupont", "validated_name": ""}

    def _fake_pg(*args, **kwargs):
        return None

    monkeypatch.setattr(db, "_pg_events_url", lambda: "")
    conn = db.get_conn()
    try:
        db._ensure_cabinet_clients_table(conn)
        conn.execute("DELETE FROM cabinet_clients WHERE tenant_id = ? AND phone = ?", (99, "0612345678"))
        conn.execute(
            """
            INSERT INTO cabinet_clients (tenant_id, phone, display_name, validation_status)
            VALUES (99, '0612345678', 'Jean Dupont', 'pending')
            """,
        )
        conn.commit()
        profile = db.get_cabinet_client_by_phone(99, "+33612345678")
        assert profile is not None
        assert profile.get("display_name") == "Jean Dupont"
    finally:
        conn.close()

