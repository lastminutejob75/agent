# tests/test_tenant_config.py
"""Tests feature flags et config affichage par tenant."""
import pytest
from backend import config
from backend.tenant_config import (
    FLAG_KEYS,
    convert_opening_hours_to_booking_rules,
    derive_horaires_text,
    get_booking_rules,
    get_flags,
    get_params,
    get_tenant_display_config,
    set_flags,
    set_params,
)


def test_get_flags_returns_defaults():
    f = get_flags(999)  # tenant inexistant
    assert f == config.DEFAULT_FLAGS


def test_set_flags_merge():
    set_flags(1, {"ENABLE_BARGEIN_SLOT_CHOICE": False})
    f = get_flags(1)
    assert f["ENABLE_BARGEIN_SLOT_CHOICE"] is False
    assert f["ENABLE_SEQUENTIAL_SLOTS"] is True  # inchangé
    set_flags(1, {"ENABLE_BARGEIN_SLOT_CHOICE": True})  # restore


def test_get_flags_tenant_none_uses_default():
    """get_flags(None) utilise DEFAULT_TENANT_ID (1), merge avec config.DEFAULT_FLAGS."""
    f = get_flags(None)
    assert set(f.keys()) == set(config.DEFAULT_FLAGS.keys())
    assert all(isinstance(v, bool) for v in f.values())


def test_get_tenant_display_config_fallback_to_config(monkeypatch, tmp_path):
    """Sans params business_name/transfer_phone → fallback config.BUSINESS_NAME / config.TRANSFER_PHONE."""
    import backend.db as db
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    display = get_tenant_display_config(1)
    assert display["business_name"] == config.BUSINESS_NAME
    assert display["transfer_phone"] == config.TRANSFER_PHONE


def test_get_tenant_display_config_uses_params_when_set(monkeypatch, tmp_path):
    """Si params_json contient business_name/transfer_phone → utilisés."""
    import backend.db as db
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    set_params(1, {"business_name": "Cabinet Martin", "transfer_phone": "+33 6 12 34 56 78"})
    display = get_tenant_display_config(1)
    assert display["business_name"] == "Cabinet Martin"
    assert display["transfer_phone"] == "+33 6 12 34 56 78"


def test_get_tenant_display_config_horaires(monkeypatch, tmp_path):
    """horaires : repli OPENING_HOURS_DEFAULT puis params."""
    import backend.db as db
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    display = get_tenant_display_config(1)
    assert "horaires" in display
    assert display["horaires"] == getattr(config, "OPENING_HOURS_DEFAULT", "horaires d'ouverture") or "horaires d'ouverture"
    set_params(1, {"horaires": "Lun-Ven 8h-18h"})
    display2 = get_tenant_display_config(1)
    assert display2["horaires"] == "Lun-Ven 8h-18h"


def test_get_booking_rules_fallback_defaults(monkeypatch, tmp_path):
    """Sans params booking_* → fallbacks 15/9/18/0/[0..4]."""
    import backend.db as db
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    rules = get_booking_rules(1)
    assert rules["duration_minutes"] == 15
    assert rules["start_hour"] == 9
    assert rules["end_hour"] == 18
    assert rules["buffer_minutes"] == 0
    assert rules["booking_days"] == [0, 1, 2, 3, 4]


def test_get_booking_rules_uses_params(monkeypatch, tmp_path):
    """Si params_json contient booking_* → utilisés."""
    import backend.db as db
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    set_params(1, {
        "booking_duration_minutes": "30",
        "booking_start_hour": "8",
        "booking_end_hour": "19",
        "booking_buffer_minutes": "10",
        "booking_days": "[0, 1, 2, 3, 4, 5]",
    })
    rules = get_booking_rules(1)
    assert rules["duration_minutes"] == 30
    assert rules["start_hour"] == 8
    assert rules["end_hour"] == 19
    assert rules["buffer_minutes"] == 10
    assert rules["booking_days"] == [0, 1, 2, 3, 4, 5]


def test_derive_horaires_text_from_booking_params():
    text = derive_horaires_text({
        "booking_days": [0, 1, 2, 3, 4],
        "booking_start_hour": 9,
        "booking_end_hour": 18,
    })
    assert text == "Lun, Mar, Mer, Jeu, Ven · 9h–18h"


def test_convert_opening_hours_to_booking_rules():
    rules = convert_opening_hours_to_booking_rules({
        "monday": {"open": "09:00", "close": "18:00", "closed": False},
        "tuesday": {"open": "08:00", "close": "17:00", "closed": False},
        "sunday": {"open": "10:00", "close": "12:00", "closed": True},
    })
    assert rules == {
        "booking_days": [0, 1],
        "booking_start_hour": 8,
        "booking_end_hour": 18,
    }


def test_set_params_auto_derives_horaires(monkeypatch, tmp_path):
    import backend.db as db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    set_params(1, {
        "booking_days": [0, 2, 4],
        "booking_start_hour": 10,
        "booking_end_hour": 17,
    })
    params = get_params(1)
    assert params["horaires"] == "Lun, Mer, Ven · 10h–17h"
