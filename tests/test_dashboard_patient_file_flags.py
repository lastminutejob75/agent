"""Règle identité patient sur le dashboard — alignée agenda (`patient_has_file`) et journal."""

from __future__ import annotations


def test_dashboard_patient_file_has_validated_identity_pure():
    from backend.routes.tenant import _dashboard_patient_file_has_validated_identity

    assert _dashboard_patient_file_has_validated_identity(None) is False
    assert _dashboard_patient_file_has_validated_identity({}) is False
    assert _dashboard_patient_file_has_validated_identity({"validated_name": ""}) is False
    assert _dashboard_patient_file_has_validated_identity({"validated_name": " A "}) is False
    assert _dashboard_patient_file_has_validated_identity({"validated_name": "Jean M"}) is True


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

