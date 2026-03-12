from __future__ import annotations

import re
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


def _looks_like_practitioner_request(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    return any(re.search(pattern, normalized) for pattern in _PRACTITIONER_PATTERNS)


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
    assistant_phone = str(params.get("transfer_assistant_phone") or "").strip()
    practitioner_phone = str(params.get("transfer_practitioner_phone") or "").strip()
    target_phone = practitioner_phone if target == "practitioner" else assistant_phone

    if channel == "vocal" and live_enabled and callback_enabled and target_phone:
        mode = "live_then_callback"

    return {
        "reason": reason,
        "target": target,
        "mode": mode if channel == "vocal" else "callback_only",
        "priority": priority,
    }
