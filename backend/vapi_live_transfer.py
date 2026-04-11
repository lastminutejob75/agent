from __future__ import annotations

import logging
import os
import re
import threading
import time
from urllib.parse import urlparse
from typing import Any, Dict, Optional

import httpx

from backend.handoff_router import resolve_handoff_decision, resolve_handoff_target_phone
from backend.handoffs import ensure_transfer_handoff, update_handoff_status
from backend.tenant_config import get_params

logger = logging.getLogger(__name__)

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
_VAPI_API_URL = "https://api.vapi.ai"
_TRANSFER_CONFIRMATION_TIMEOUT_SECONDS = 20
_TRANSFER_CONFIRMATION_POLL_SECONDS = 1
_BOOKING_END_CONTROL_TIMEOUT_SECONDS = 5.0
_BOOKING_END_MESSAGE = "Votre rendez-vous est confirmé. Merci pour votre appel. Bonne journée."


def mask_phone_last4(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) >= 4:
        return f"***{digits[-4:]}"
    return "***"


def normalize_transfer_destination_phone(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("00"):
        digits = f"+{digits[2:]}"
    elif digits.startswith("0") and len(re.sub(r"\D", "", digits)) == 10:
        digits = f"+33{digits[1:]}"
    elif not digits.startswith("+") and len(re.sub(r"\D", "", digits)) == 9:
        digits = f"+33{digits}"
    return digits if _E164_RE.match(digits) else ""


def _vapi_api_key() -> str:
    return str(os.environ.get("VAPI_API_KEY") or "").strip()


def _update_handoff_if_needed(tenant_id: int, handoff_id: int, next_status: str) -> None:
    current = None
    try:
        from backend.handoffs import get_handoff_by_id

        current = get_handoff_by_id(tenant_id, handoff_id)
    except Exception:
        current = None
    current_status = str((current or {}).get("status") or "").strip().lower()
    if current_status == next_status:
        return
    if current_status == "live_connected" and next_status != "live_connected":
        return
    update_handoff_status(tenant_id, handoff_id, status=next_status)


def poll_transfer_confirmation(call_id: str, tenant_id: int, handoff_id: int) -> None:
    api_key = _vapi_api_key()
    if not api_key or not call_id or not handoff_id:
        return
    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = time.time() + _TRANSFER_CONFIRMATION_TIMEOUT_SECONDS
    saw_forwarding = False
    try:
        with httpx.Client(timeout=5.0) as client:
            while time.time() < deadline:
                response = client.get(f"{_VAPI_API_URL}/call/{call_id}", headers=headers)
                response.raise_for_status()
                payload = response.json() if response.content else {}
                status = str(payload.get("status") or "").strip().lower()
                ended_reason = str(payload.get("endedReason") or "").strip()
                if status == "forwarding" and not saw_forwarding:
                    saw_forwarding = True
                    _update_handoff_if_needed(tenant_id, handoff_id, "live_forwarding_confirmed")
                    logger.info(
                        "LIVE_TRANSFER_POLL_FORWARDING call_id=%s tenant_id=%s handoff_id=%s",
                        call_id[:24],
                        tenant_id,
                        handoff_id,
                    )
                if status == "ended":
                    if ended_reason == "assistant-forwarded-call":
                        _update_handoff_if_needed(tenant_id, handoff_id, "live_connected")
                        logger.info(
                            "LIVE_TRANSFER_POLL_CONNECTED call_id=%s tenant_id=%s handoff_id=%s",
                            call_id[:24],
                            tenant_id,
                            handoff_id,
                        )
                    else:
                        _update_handoff_if_needed(tenant_id, handoff_id, "live_failed")
                        logger.warning(
                            "LIVE_TRANSFER_POLL_ENDED_UNEXPECTED call_id=%s tenant_id=%s handoff_id=%s ended_reason=%s",
                            call_id[:24],
                            tenant_id,
                            handoff_id,
                            ended_reason,
                        )
                    return
                time.sleep(_TRANSFER_CONFIRMATION_POLL_SECONDS)
        _update_handoff_if_needed(tenant_id, handoff_id, "live_unconfirmed_timeout")
        logger.warning(
            "LIVE_TRANSFER_POLL_TIMEOUT call_id=%s tenant_id=%s handoff_id=%s timeout_s=%s",
            call_id[:24],
            tenant_id,
            handoff_id,
            _TRANSFER_CONFIRMATION_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning(
            "LIVE_TRANSFER_POLL_FAILED call_id=%s tenant_id=%s handoff_id=%s err=%s",
            call_id[:24],
            tenant_id,
            handoff_id,
            str(exc)[:160],
        )


def schedule_transfer_confirmation(call_id: str, tenant_id: int, handoff_id: int) -> None:
    if not call_id or not handoff_id or not _vapi_api_key():
        return
    thread = threading.Thread(
        target=poll_transfer_confirmation,
        args=(call_id, tenant_id, handoff_id),
        daemon=True,
        name=f"uwi-live-transfer-{call_id[:8]}",
    )
    thread.start()


def extract_control_url(payload: Optional[dict]) -> str:
    payload = payload or {}
    candidates = [
        payload.get("call") or {},
        (payload.get("message") or {}).get("call") or {},
    ]
    for call in candidates:
        monitor = call.get("monitor") or {}
        raw = str(monitor.get("controlUrl") or monitor.get("controlURL") or "").strip()
        if raw:
            return raw if raw.endswith("/control") else f"{raw.rstrip('/')}/control"
    return ""


def maybe_start_terminal_booking_end(
    payload: Optional[dict],
    session: Any,
    *,
    message: str = _BOOKING_END_MESSAGE,
) -> Dict[str, Any]:
    if not session or getattr(session, "channel", "") != "vocal":
        return {"attempted": False, "ok": False, "reason": "not_vocal"}
    if getattr(session, "booking_end_control_requested", False):
        return {"attempted": False, "ok": True, "reason": "already_requested"}

    control_url = extract_control_url(payload)
    if not control_url:
        logger.warning(
            "BOOKING_END_CONTROL_SKIPPED call_id=%s reason=missing_control_url",
            str(getattr(session, "conv_id", "") or "")[:24],
        )
        return {"attempted": False, "ok": False, "reason": "missing_control_url"}

    started_at = time.perf_counter()
    control_host = urlparse(control_url).netloc or ""
    _SETTLE_SECONDS = 8.0
    final_text = (message or _BOOKING_END_MESSAGE).strip() or _BOOKING_END_MESSAGE
    body_add_msg = {
        "type": "add-message",
        "message": {
            "role": "system",
            "content": (
                f"INSTRUCTION PRIORITAIRE — Dis EXACTEMENT cette phrase, mot pour mot, "
                f"sans rien ajouter, modifier ou reformuler : "
                f"« {final_text} » "
                f"Puis raccroche immédiatement."
            ),
        },
        "triggerResponseEnabled": True,
    }
    body_end = {"type": "end-call"}

    try:
        with httpx.Client(timeout=_BOOKING_END_CONTROL_TIMEOUT_SECONDS) as client:
            t0 = time.perf_counter()
            add_resp = client.post(
                control_url,
                json=body_add_msg,
                headers={"Content-Type": "application/json"},
            )
            add_resp.raise_for_status()
            t_add_ms = round((time.perf_counter() - t0) * 1000, 0)

            time.sleep(_SETTLE_SECONDS)

            try:
                client.post(
                    control_url,
                    json=body_end,
                    headers={"Content-Type": "application/json"},
                )
            except Exception:
                pass

        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 0)
        setattr(session, "booking_end_control_requested", True)
        logger.info(
            "BOOKING_END_CONTROL_TRIGGERED call_id=%s tenant_id=%s control_host=%s t_add_msg_ms=%s settle_s=%.1f elapsed_ms=%s message=%s",
            str(getattr(session, "conv_id", "") or "")[:24],
            int(getattr(session, "tenant_id", 1) or 1),
            control_host,
            t_add_ms,
            _SETTLE_SECONDS,
            elapsed_ms,
            final_text[:120],
        )
        return {
            "attempted": True,
            "ok": True,
            "message": final_text,
        }
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        response_text = ""
        if getattr(exc, "response", None) is not None:
            try:
                response_text = str(exc.response.text or "")[:800]
            except Exception:
                response_text = ""
        logger.warning(
            "BOOKING_END_CONTROL_FAILED call_id=%s tenant_id=%s control_host=%s status_code=%s err_type=%s err=%s body=%s",
            str(getattr(session, "conv_id", "") or "")[:24],
            int(getattr(session, "tenant_id", 1) or 1),
            control_host,
            status_code,
            exc.__class__.__name__,
            str(exc)[:160],
            response_text,
        )
        return {
            "attempted": True,
            "ok": False,
            "reason": "control_request_failed",
        }


def _destination_phone(session: Any, target: str) -> str:
    params = get_params(int(getattr(session, "tenant_id", 1) or 1))
    return normalize_transfer_destination_phone(resolve_handoff_target_phone(params, target))


def maybe_start_live_transfer(
    payload: Optional[dict],
    session: Any,
    *,
    response_text: str,
    user_text: str = "",
) -> Dict[str, Any]:
    if not session or getattr(session, "channel", "") != "vocal":
        return {"attempted": False, "ok": False, "reason": "not_vocal"}
    if getattr(session, "state", "") != "TRANSFERRED":
        return {"attempted": False, "ok": False, "reason": "not_transferred"}
    if getattr(session, "live_transfer_requested", False):
        return {"attempted": False, "ok": True, "reason": "already_requested"}

    trigger_reason = str(getattr(session, "last_transfer_reason", "") or "fallback_transfer").strip()
    decision = resolve_handoff_decision(
        session,
        trigger_reason=trigger_reason,
        channel="vocal",
        user_text=user_text or "",
    )
    if decision.get("mode") != "live_then_callback":
        return {"attempted": False, "ok": False, "reason": "mode_not_live"}

    destination_phone = _destination_phone(session, decision.get("target", "assistant"))
    if not destination_phone:
        return {"attempted": False, "ok": False, "reason": "missing_destination"}

    control_url = extract_control_url(payload)
    if not control_url:
        logger.warning(
            "LIVE_TRANSFER_SKIPPED call_id=%s reason=missing_control_url",
            str(getattr(session, "conv_id", "") or "")[:24],
        )
        return {"attempted": False, "ok": False, "reason": "missing_control_url"}

    handoff = None
    try:
        handoff = ensure_transfer_handoff(session, trigger_reason=trigger_reason, user_text=user_text or "")
    except Exception as exc:
        logger.warning("LIVE_TRANSFER_HANDOFF_ENSURE_FAILED conv_id=%s err=%s", getattr(session, "conv_id", ""), exc)

    body = {
        "type": "transfer",
        "destination": {
            "type": "number",
            "number": destination_phone,
        },
        "content": (response_text or "").strip(),
    }
    control_host = urlparse(control_url).netloc or ""
    started_at = time.perf_counter()

    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(
                control_url,
                json=body,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 0)
        setattr(session, "live_transfer_requested", True)
        if handoff and handoff.get("id"):
            tenant_id = int(getattr(session, "tenant_id", 1) or 1)
            handoff_id = int(handoff["id"])
            update_handoff_status(tenant_id, handoff_id, status="live_attempted")
            schedule_transfer_confirmation(str(getattr(session, "conv_id", "") or ""), tenant_id, handoff_id)
        logger.info(
            "LIVE_TRANSFER_TRIGGERED call_id=%s tenant_id=%s target=%s destination=%s control_host=%s status_code=%s elapsed_ms=%s body=%s",
            str(getattr(session, "conv_id", "") or "")[:24],
            int(getattr(session, "tenant_id", 1) or 1),
            decision.get("target", "assistant"),
            mask_phone_last4(destination_phone),
            control_host,
            response.status_code,
            elapsed_ms,
            (response.text or "")[:800],
        )
        return {
            "attempted": True,
            "ok": True,
            "target": decision.get("target", "assistant"),
            "number": destination_phone,
        }
    except Exception as exc:
        if handoff and handoff.get("id"):
            try:
                update_handoff_status(int(getattr(session, "tenant_id", 1) or 1), int(handoff["id"]), status="live_failed")
            except Exception:
                pass
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        response_text = ""
        if getattr(exc, "response", None) is not None:
            try:
                response_text = str(exc.response.text or "")[:800]
            except Exception:
                response_text = ""
        logger.warning(
            "LIVE_TRANSFER_FAILED call_id=%s tenant_id=%s target=%s destination=%s control_host=%s status_code=%s err_type=%s err=%s body=%s",
            str(getattr(session, "conv_id", "") or "")[:24],
            int(getattr(session, "tenant_id", 1) or 1),
            decision.get("target", "assistant"),
            mask_phone_last4(destination_phone),
            control_host,
            status_code,
            exc.__class__.__name__,
            str(exc)[:160],
            response_text,
        )
        return {
            "attempted": True,
            "ok": False,
            "reason": "control_request_failed",
            "target": decision.get("target", "assistant"),
            "number": destination_phone,
        }
