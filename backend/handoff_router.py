from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict

from backend.tenant_config import get_params


_PRACTITIONER_PATTERNS = [
    r"\bmedecin\b",
    r"\bdocteur\b",
    r"\bpraticien\b",
    r"\bdr\b",
    r"\bson avis\b",
]

_MEDICAL_REASON_HINTS = {
    "medical_question_requires_practitioner",
    "urgent_non_vital_case",
    "medical_sensitive",
}

_DAY_NAMES = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def resolve_handoff_target_phone(params: Dict[str, Any], target: str) -> str:
    params = params or {}
    if target == "practitioner":
        practitioner_phone = str(params.get("transfer_practitioner_phone") or "").strip()
        if practitioner_phone:
            return practitioner_phone
        if _has_wizard_transfer_preferences(params):
            for key in ("transfer_assistant_phone", "transfer_number", "phone_number"):
                value = str(params.get(key) or "").strip()
                if value:
                    return value
        return ""
    for key in ("transfer_assistant_phone", "transfer_number", "phone_number"):
        value = str(params.get(key) or "").strip()
        if value:
            return value
    return ""


def _looks_like_practitioner_request(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    return any(re.search(pattern, normalized) for pattern in _PRACTITIONER_PATTERNS)


def _parse_string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, (list, tuple, set)):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []


def _parse_transfer_hours(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _has_wizard_transfer_preferences(params: Dict[str, Any]) -> bool:
    return bool(
        str(params.get("transfer_config_confirmed_signature") or "").strip()
        or _parse_string_list(params.get("transfer_cases"))
        or _parse_transfer_hours(params.get("transfer_hours"))
        or str(params.get("transfer_always_urgent") or "").strip()
        or str(params.get("transfer_no_consultation") or "").strip()
    )


def _reason_to_transfer_case(reason: str) -> str | None:
    if reason in {"urgent_non_vital_case", "medical_sensitive", "medical_question_requires_practitioner"}:
        return "urgent"
    if reason in {"explicit_transfer_request", "user_requested", "explicit_human_request", "explicit_practitioner_request"}:
        return "insists"
    if reason in {"technical_failure", "too_many_retries", "identity_uncertain"}:
        return "complex"
    if reason in {"fallback_transfer"}:
        return "other"
    return None


def _now_for_transfer_window() -> datetime:
    return datetime.now()


def _is_within_transfer_hours(params: Dict[str, Any]) -> bool:
    transfer_hours = _parse_transfer_hours(params.get("transfer_hours"))
    if not transfer_hours:
        return True
    now = _now_for_transfer_window()
    day_name = _DAY_NAMES[now.weekday()]
    slot = transfer_hours.get(day_name) or {}
    if not slot:
        return False
    if not bool(slot.get("enabled")):
        return False
    start_raw = str(slot.get("from") or "").strip()
    end_raw = str(slot.get("to") or "").strip()
    try:
        current_minutes = now.hour * 60 + now.minute
        start_hour, start_minute = [int(part) for part in start_raw.split(":", 1)]
        end_hour, end_minute = [int(part) for part in end_raw.split(":", 1)]
        start_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute
        return start_minutes <= current_minutes <= end_minutes
    except Exception:
        return True


def _live_transfer_allowed_by_preferences(params: Dict[str, Any], reason: str) -> bool:
    if not _has_wizard_transfer_preferences(params):
        return True
    if reason in {"explicit_transfer_request", "user_requested", "explicit_human_request", "explicit_practitioner_request"}:
        return True
    selected_cases = set(_parse_string_list(params.get("transfer_cases")))
    if not selected_cases:
        return False
    mapped_case = _reason_to_transfer_case(reason)
    if not mapped_case:
        return "other" in selected_cases
    return mapped_case in selected_cases or "other" in selected_cases


def resolve_handoff_decision(
    session: Any,
    *,
    trigger_reason: str,
    channel: str,
    user_text: str | None = None,
) -> Dict[str, str]:
    reason = (trigger_reason or "").strip().lower() or "fallback_transfer"
    target = "assistant"
    priority = "normal"
    mode = "callback_only"

    if reason in _MEDICAL_REASON_HINTS or _looks_like_practitioner_request(user_text or ""):
        target = "practitioner"
        priority = "high"
    elif reason in {"explicit_practitioner_request"}:
        target = "practitioner"
        priority = "high"
    elif reason in {"explicit_transfer_request", "user_requested"}:
        target = "practitioner" if _looks_like_practitioner_request(user_text or "") else "assistant"
        priority = "high" if target == "practitioner" else "normal"
        reason = "explicit_practitioner_request" if target == "practitioner" else "explicit_human_request"
    elif reason in {"technical_failure", "too_many_retries", "identity_uncertain", "fallback_transfer"}:
        target = "assistant"
        priority = "normal"

    if reason == "urgent_non_vital_case":
        priority = "urgent_non_vital"
        target = "practitioner"

    try:
        params = get_params(int(getattr(session, "tenant_id", 1) or 1))
    except Exception:
        params = {}

    live_enabled = str(params.get("transfer_live_enabled") or "").strip().lower() == "true"
    callback_enabled = str(params.get("transfer_callback_enabled") or "").strip().lower() != "false"
    target_phone = resolve_handoff_target_phone(params, target)
    urgent_override = reason == "urgent_non_vital_case" and str(params.get("transfer_always_urgent") or "").strip().lower() == "true"
    within_transfer_hours = urgent_override or _is_within_transfer_hours(params)
    live_allowed = _live_transfer_allowed_by_preferences(params, reason)

    if channel == "vocal" and live_enabled and callback_enabled and target_phone and within_transfer_hours and live_allowed:
        mode = "live_then_callback"

    return {
        "reason": reason,
        "target": target,
        "mode": mode if channel == "vocal" else "callback_only",
        "priority": priority,
    }
