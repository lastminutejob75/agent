# backend/recovery.py
"""
Fix #9: namespace recovery unifié (compteurs contact/slot/qualif).
Helpers rec_get, rec_set, rec_inc, rec_reset + migration legacy → recovery.
Sans dépendances lourdes (session uniquement).
"""
from __future__ import annotations

from typing import Any, Dict

_RECOVERY_DEFAULT = {
    "contact": {"fails": 0, "retry": 0, "mode": None},
    "phone": {"partial": "", "turns": 0},
    "confirm_contact": {"fails": 0, "intent_repeat": 0},
    "slot_choice": {"fails": 0},
    "name": {"fails": 0},
    "preference": {"fails": 0},
    "confirm_slot": {"retry": 0},
}


def _ensure_recovery(session) -> Dict[str, Any]:
    rec = getattr(session, "recovery", None)
    if not isinstance(rec, dict) or not rec:
        session.recovery = {k: dict(v) if isinstance(v, dict) else v for k, v in _RECOVERY_DEFAULT.items()}
    return session.recovery


def rec_get(session, path: str, default=None):
    """Ex: rec_get(session, 'phone.partial', '')"""
    rec = _ensure_recovery(session)
    cur = rec
    parts = path.split(".")
    for k in parts:
        if not isinstance(cur, dict):
            return default
        if k not in cur:
            return default
        cur = cur[k]
    return cur if cur is not None else default


def rec_set(session, path: str, value):
    """Ex: rec_set(session, 'phone.partial', '0612')"""
    rec = _ensure_recovery(session)
    parts = path.split(".")
    cur = rec
    for k in parts[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[parts[-1]] = value
    return value


def rec_inc(session, path: str, delta: int = 1):
    """Ex: rec_inc(session, 'contact.fails'). Returns new value."""
    v = rec_get(session, path, 0)
    try:
        v2 = int(v) + int(delta)
    except (TypeError, ValueError):
        v2 = int(delta)
    rec_set(session, path, v2)
    return v2


def rec_reset(session, top_key: str):
    """Réinitialise tout un sous-objet. Ex: rec_reset(session, 'contact')."""
    rec = _ensure_recovery(session)
    if top_key in _RECOVERY_DEFAULT:
        rec[top_key] = dict(_RECOVERY_DEFAULT[top_key]) if isinstance(_RECOVERY_DEFAULT[top_key], dict) else _RECOVERY_DEFAULT[top_key]
    else:
        rec[top_key] = {}
    return rec[top_key]


def migrate_recovery_from_legacy(session):
    """
    Remplit session.recovery depuis les champs legacy si recovery est vide.
    À appeler au chargement SQLite (pickle ou colonnes) et après session_from_dict (Postgres).
    """
    rec = _ensure_recovery(session)

    def _set_if_empty(path: str, legacy_val):
        cur = rec_get(session, path, None)
        if cur in (None, "", 0) and legacy_val not in (None, "", 0):
            rec_set(session, path, legacy_val)

    _set_if_empty("contact.fails", getattr(session, "contact_fails", 0))
    _set_if_empty("contact.retry", getattr(session, "contact_retry_count", 0))
    _set_if_empty("contact.mode", getattr(session, "contact_mode", None))
    _set_if_empty("phone.partial", getattr(session, "partial_phone_digits", ""))
    _set_if_empty("confirm_contact.fails", getattr(session, "contact_confirm_fails", 0))
    _set_if_empty("confirm_contact.intent_repeat", getattr(session, "contact_confirm_intent_repeat_count", 0))
    _set_if_empty("slot_choice.fails", getattr(session, "slot_choice_fails", 0))
    _set_if_empty("name.fails", getattr(session, "name_fails", 0))
    _set_if_empty("preference.fails", getattr(session, "preference_fails", 0))
    _set_if_empty("confirm_slot.retry", getattr(session, "confirm_retry_count", 0))
    pf = getattr(session, "phone_fails", 0)
    if rec_get(session, "phone.turns", 0) == 0 and pf:
        rec_set(session, "phone.turns", pf)
    return rec
