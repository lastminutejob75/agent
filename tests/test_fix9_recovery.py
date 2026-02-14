# tests/test_fix9_recovery.py
"""
Fix #9: tests recovery unifié — migration legacy, codec roundtrip, vocal partial après perte de session.
"""
import pytest
from backend.session import Session
from backend.recovery import (
    rec_get,
    rec_set,
    rec_inc,
    rec_reset,
    migrate_recovery_from_legacy,
    _ensure_recovery,
)


# ---------- Helpers ----------
def test_rec_get_set_inc_reset():
    """rec_get, rec_set, rec_inc, rec_reset sur une session avec recovery vide puis rempli."""
    s = Session(conv_id="test")
    assert rec_get(s, "phone.partial", "") == ""
    assert rec_get(s, "contact.fails", 0) == 0

    rec_set(s, "phone.partial", "0612")
    assert rec_get(s, "phone.partial", "") == "0612"

    rec_inc(s, "contact.fails")
    rec_inc(s, "contact.fails")
    assert rec_get(s, "contact.fails", 0) == 2

    rec_reset(s, "contact")
    assert rec_get(s, "contact.fails", 0) == 0
    assert rec_get(s, "contact.retry", 0) == 0
    assert rec_get(s, "contact.mode", None) is None


def test_migrate_recovery_from_legacy():
    """Session sans recovery (ou recovery={}) + champs legacy → migrate → recovery remplie."""
    s = Session(conv_id="legacy")
    # Simuler une session legacy (pas de recovery, ou recovery vide)
    s.recovery = {}
    s.partial_phone_digits = "0612"
    s.contact_fails = 1
    s.contact_retry_count = 2
    s.contact_mode = "phone"
    s.contact_confirm_fails = 1
    s.slot_choice_fails = 1
    s.confirm_retry_count = 1

    migrate_recovery_from_legacy(s)

    assert rec_get(s, "phone.partial", "") == "0612"
    assert rec_get(s, "contact.fails", 0) == 1
    assert rec_get(s, "contact.retry", 0) == 2
    assert rec_get(s, "contact.mode", None) == "phone"
    assert rec_get(s, "confirm_contact.fails", 0) == 1
    assert rec_get(s, "slot_choice.fails", 0) == 1
    assert rec_get(s, "confirm_slot.retry", 0) == 1


def test_migrate_recovery_does_not_overwrite_filled():
    """Si recovery est déjà remplie, la migration n'écrase pas."""
    s = Session(conv_id="filled")
    rec_set(s, "phone.partial", "0699")
    rec_set(s, "contact.fails", 3)
    s.partial_phone_digits = "0612"  # legacy
    s.contact_fails = 1

    migrate_recovery_from_legacy(s)

    # On garde les valeurs déjà dans recovery (phone.partial et contact.fails déjà non vides)
    assert rec_get(s, "phone.partial", "") == "0699"
    assert rec_get(s, "contact.fails", 0) == 3


def test_codec_roundtrip_recovery():
    """session_to_dict → session_from_dict → recovery identique."""
    from backend.session_codec import session_to_dict, session_from_dict

    s = Session(conv_id="roundtrip")
    rec_set(s, "phone.partial", "061234")
    rec_set(s, "contact.mode", "phone")
    rec_inc(s, "contact.fails")
    rec_inc(s, "slot_choice.fails")

    d = session_to_dict(s)
    assert "recovery" in d
    assert d["recovery"].get("phone", {}).get("partial") == "061234"
    assert d["recovery"].get("contact", {}).get("mode") == "phone"

    s2 = session_from_dict("roundtrip", d)
    assert rec_get(s2, "phone.partial", "") == "061234"
    assert rec_get(s2, "contact.mode", None) == "phone"
    assert rec_get(s2, "contact.fails", 0) == 1
    assert rec_get(s2, "slot_choice.fails", 0) == 1


def test_vocal_partial_after_codec_roundtrip():
    """Bug réel Postgres: après checkpoint, partial_phone_digits ne doit pas être perdu."""
    from backend.session_codec import session_to_dict, session_from_dict

    s = Session(conv_id="vocal-call")
    s.channel = "vocal"
    s.state = "QUALIF_CONTACT"
    rec_set(s, "phone.partial", "06")

    d = session_to_dict(s)
    s2 = session_from_dict("vocal-call", d)

    assert rec_get(s2, "phone.partial", "") == "06"
    # Simuler accumulation après reprise
    partial = rec_get(s2, "phone.partial", "") + "1234"
    rec_set(s2, "phone.partial", partial)
    assert rec_get(s2, "phone.partial", "") == "061234"


def test_ensure_recovery_creates_structure():
    """_ensure_recovery crée la structure si absente ou vide."""
    s = Session(conv_id="empty")
    s.recovery = None
    rec = _ensure_recovery(s)
    assert isinstance(rec, dict)
    assert "contact" in rec
    assert "phone" in rec
    assert rec.get("phone", {}).get("partial") == ""
