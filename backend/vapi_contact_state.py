from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

import re

from backend import db

_CONTACT_STATE_TTL_S = 30 * 60
_CONTACT_STATE_LOCK = threading.Lock()
_CONTACT_STATES: Dict[str, Dict[str, Any]] = {}


def _now_ts() -> float:
    return time.time()


def _digits(value: Optional[str]) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _last4(value: Optional[str]) -> str:
    digits = _digits(value)
    return digits[-4:] if len(digits) >= 4 else ""


def _is_valid_phone_number(value: Optional[str]) -> bool:
    normalized = db.normalize_phone_number(value)
    if not normalized:
        return False
    if re.fullmatch(r"0[1-9]\d{8}", normalized):
        return True
    if re.fullmatch(r"\+33[1-9]\d{8}", normalized):
        return True
    return False


def _base_state(call_id: str) -> Dict[str, Any]:
    now = _now_ts()
    return {
        "call_id": call_id,
        "known_number": False,
        "last4": "",
        "phone_number": "",
        "validated": False,
        "validated_at": None,
        "validation_required": False,
        "validated_via": "",
        "selected_slot_label": "",
        "patient_name": "",
        "created_at": now,
        "updated_at": now,
    }


def _public_view(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "call_id": state.get("call_id") or "",
        "known_number": bool(state.get("known_number")),
        "last4": state.get("last4") or "",
        "validated": bool(state.get("validated")),
        "validated_at": state.get("validated_at"),
        "validation_required": bool(state.get("validation_required")),
        "validated_via": state.get("validated_via") or "",
        "selected_slot_label": state.get("selected_slot_label") or "",
        "patient_name": state.get("patient_name") or "",
        "created_at": state.get("created_at"),
        "updated_at": state.get("updated_at"),
    }


def _purge_expired_locked(now: float) -> None:
    expired = [
        call_id
        for call_id, state in _CONTACT_STATES.items()
        if now - float(state.get("updated_at") or state.get("created_at") or 0) > _CONTACT_STATE_TTL_S
    ]
    for call_id in expired:
        _CONTACT_STATES.pop(call_id, None)


def get_contact_state(call_id: Optional[str]) -> Optional[Dict[str, Any]]:
    key = str(call_id or "").strip()
    if not key:
        return None
    now = _now_ts()
    with _CONTACT_STATE_LOCK:
        _purge_expired_locked(now)
        state = _CONTACT_STATES.get(key)
        if state is None:
            return None
        return _public_view(state)


def sync_contact_state(
    call_id: Optional[str],
    *,
    known_phone: Optional[str] = None,
    patient_name: Optional[str] = None,
    selected_slot_label: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    key = str(call_id or "").strip()
    if not key:
        return None
    now = _now_ts()
    normalized_phone = db.normalize_phone_number(known_phone)
    with _CONTACT_STATE_LOCK:
        _purge_expired_locked(now)
        state = _CONTACT_STATES.get(key) or _base_state(key)
        state["updated_at"] = now
        if patient_name:
            state["patient_name"] = str(patient_name).strip()
        if selected_slot_label:
            state["selected_slot_label"] = str(selected_slot_label).strip()
        if normalized_phone:
            state["known_number"] = True
            if not state.get("phone_number"):
                state["phone_number"] = normalized_phone
            if not state.get("last4"):
                state["last4"] = _last4(normalized_phone)
        _CONTACT_STATES[key] = state
        return _public_view(state)


def validate_contact(
    call_id: Optional[str],
    *,
    known_phone: Optional[str] = None,
    phone_number: Optional[str] = None,
    confirmation_last4: Optional[str] = None,
    patient_name: Optional[str] = None,
    selected_slot_label: Optional[str] = None,
) -> Dict[str, Any]:
    key = str(call_id or "").strip()
    if not key:
        return {"status": "failed", "reason": "missing_call_id"}

    sync_contact_state(
        key,
        known_phone=known_phone,
        patient_name=patient_name,
        selected_slot_label=selected_slot_label,
    )
    now = _now_ts()
    normalized_phone = db.normalize_phone_number(phone_number)
    provided_last4 = _last4(confirmation_last4)

    with _CONTACT_STATE_LOCK:
        _purge_expired_locked(now)
        state = _CONTACT_STATES.get(key) or _base_state(key)
        state["validation_required"] = True
        state["updated_at"] = now
        if patient_name:
            state["patient_name"] = str(patient_name).strip()
        if selected_slot_label:
            state["selected_slot_label"] = str(selected_slot_label).strip()

        if phone_number:
            if not _is_valid_phone_number(phone_number):
                _CONTACT_STATES[key] = state
                return {"status": "failed", "reason": "invalid_phone_number"}
        if normalized_phone:
            state["phone_number"] = normalized_phone
            state["last4"] = _last4(normalized_phone)
            state["validated"] = True
            state["validated_at"] = now
            state["validated_via"] = "phone_number"
            _CONTACT_STATES[key] = state
            return {
                "status": "validated",
                "validated_via": "phone_number",
                "known_number": bool(state.get("known_number")),
                "last4": state.get("last4") or "",
            }

        expected_last4 = state.get("last4") or _last4(state.get("phone_number"))
        if expected_last4 and provided_last4:
            if provided_last4 == expected_last4:
                state["validated"] = True
                state["validated_at"] = now
                state["validated_via"] = "confirmation_last4"
                _CONTACT_STATES[key] = state
                return {
                    "status": "validated",
                    "validated_via": "confirmation_last4",
                    "known_number": bool(state.get("known_number")),
                    "last4": expected_last4,
                }
            _CONTACT_STATES[key] = state
            return {"status": "failed", "reason": "last4_mismatch"}

        _CONTACT_STATES[key] = state
        if expected_last4:
            return {"status": "failed", "reason": "missing_confirmation_last4"}
        return {"status": "failed", "reason": "missing_phone_number"}
