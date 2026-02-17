# backend/vapi_tool_handlers.py
"""
Handlers pour le function_tool Vapi (OpenAI direct + tool obligatoire).
Actions : get_slots, book, cancel, modify, faq.
Réponses au format Vapi : results[{ toolCallId, result: string }].
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from backend import tools_booking

logger = logging.getLogger(__name__)


def _slot_to_vocal_label(slot: Any) -> str:
    """Label vocal complet (jour + date + heure) pour un slot."""
    return tools_booking.slot_to_vocal_label(slot)


def _vapi_result_string(data: Dict[str, Any]) -> str:
    """Sérialise le résultat en une seule ligne (Vapi exige result = string)."""
    return json.dumps(data, ensure_ascii=False)


def handle_get_slots(
    session: Any,
    preference: Optional[str],
    call_id: str,
    exclude_start_iso: Optional[str] = None,
    exclude_end_iso: Optional[str] = None,
) -> Tuple[Optional[List[str]], Optional[str], str]:
    """
    Récupère les créneaux depuis Google Calendar (ou SQLite).
    exclude_start_iso / exclude_end_iso : créneau à exclure (ex. après slot_taken).
    Returns: (slots_list, source, error_message).
    """
    logger.info(
        "CALENDAR_FETCH",
        extra={
            "call_id": call_id[:24] if call_id else "",
            "preference": preference or "any",
            "exclude": bool(exclude_start_iso or exclude_end_iso),
        },
    )
    try:
        pref = (preference or "").strip().lower()
        if pref not in ("matin", "après-midi", "apres-midi", "soir", ""):
            pref = None
        if pref == "apres-midi":
            pref = "après-midi"
        slots = tools_booking.get_slots_for_display(
            limit=3,
            pref=pref or None,
            session=session,
            exclude_start_iso=exclude_start_iso or None,
            exclude_end_iso=exclude_end_iso or None,
        )
        tools_booking.store_pending_slots(session, slots)
        labels = [_slot_to_vocal_label(s) for s in slots]
        _src = getattr(session, "_slots_source", None) or ""
        source = "google_calendar" if (_src == "google") else "sqlite"
        logger.info(
            "CALENDAR_SLOTS_RETURNED",
            extra={"call_id": call_id[:24] if call_id else "", "count": len(labels), "source": source},
        )
        return (labels, source, "")
    except Exception as e:
        logger.exception("CALENDAR_FETCH failed: %s", e)
        return (None, None, "Impossible de consulter l'agenda pour le moment.")


def _chosen_slot_iso(session: Any, choice: int) -> Tuple[Optional[str], Optional[str]]:
    """Retourne (start_iso, end_iso) du créneau choisi depuis session.pending_slots."""
    pending = getattr(session, "pending_slots", None) or []
    if not pending or not (1 <= choice <= len(pending)):
        return None, None
    slots = tools_booking.to_canonical_slots(pending) if pending and not isinstance(pending[0], dict) else list(pending)
    chosen = slots[choice - 1] if choice <= len(slots) else {}
    start = chosen.get("start_iso") or chosen.get("start") or ""
    end = chosen.get("end_iso") or chosen.get("end") or ""
    return (start or None, end or None)


def handle_book(
    session: Any,
    selected_slot: Optional[str],
    patient_name: Optional[str],
    motif: Optional[str],
    call_id: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Réserve le créneau choisi. Retourne un payload standard V3 (JSON strict).
    Returns: (payload_dict, error_message).
    error_message utilisé uniquement pour réponse error côté Vapi si besoin; pour book on renvoie toujours payload.
    Payload: status in ("confirmed", "slot_taken", "technical_error", "fallback_transfer").
    """
    if patient_name:
        session.qualif_data.name = patient_name.strip()
    if motif:
        session.qualif_data.motif = motif.strip()

    choice = 1
    raw = (selected_slot or "").strip().lower()
    if raw in ("1", "un", "le premier", "le 1"):
        choice = 1
    elif raw in ("2", "deux", "le deuxième", "le 2"):
        choice = 2
    elif raw in ("3", "trois", "le troisième", "le 3"):
        choice = 3
    else:
        pending = getattr(session, "pending_slots", None) or []
        for i, s in enumerate(pending):
            label = _slot_to_vocal_label(s)
            if raw in label.lower() or label.lower() in raw:
                choice = i + 1
                break

    session.pending_slot_choice = choice
    start_iso, end_iso = _chosen_slot_iso(session, choice)

    success, reason = tools_booking.book_slot_from_session(session, choice)

    if success:
        session.booking_failures = 0
        event_id = getattr(session, "google_event_id", None) or ""
        if not start_iso or not end_iso:
            start_iso, end_iso = _chosen_slot_iso(session, choice)
        start_iso = start_iso or ""
        end_iso = end_iso or ""
        logger.info(
            "BOOKING_CONFIRMED",
            extra={"call_id": (call_id or "")[:24], "event_id": (event_id or "")[:24]},
        )
        return (
            {
                "status": "confirmed",
                "event_id": event_id,
                "start_iso": start_iso,
                "end_iso": end_iso,
            },
            None,
        )

    if reason == "slot_taken":
        failures = getattr(session, "booking_failures", 0) + 1
        session.booking_failures = failures
        if failures >= 2:
            return ({"status": "fallback_transfer"}, None)
        return (
            {
                "status": "slot_taken",
                "start_iso": start_iso or "",
                "end_iso": end_iso or "",
            },
            None,
        )

    if reason == "permission":
        return ({"status": "technical_error", "code": "permission"}, None)
    # technical ou autre
    return ({"status": "technical_error", "code": "calendar_unavailable"}, None)


def build_vapi_tool_response(
    tool_call_id: Optional[str],
    result_body: Optional[Union[Dict[str, Any], str]],
    error_message: Optional[str],
) -> Dict[str, Any]:
    """
    Construit la réponse au format Vapi.
    result et error doivent être des strings (Vapi).
    Si result_body est une str, elle est utilisée telle quelle (TTS lisible).
    Si c'est un dict, il est JSON stringifié (legacy).
    """
    if tool_call_id is None:
        tool_call_id = "call_default"
    if error_message:
        return {"results": [{"toolCallId": tool_call_id, "error": error_message}]}
    if result_body is not None:
        result = result_body if isinstance(result_body, str) else _vapi_result_string(result_body)
        return {"results": [{"toolCallId": tool_call_id, "result": result}]}
    return {"results": [{"toolCallId": tool_call_id, "result": _vapi_result_string({"status": "ok"})}]}


def build_vapi_tool_response_legacy(result_text: str) -> Dict[str, Any]:
    """Réponse simple pour compat (sans action structurée)."""
    return {"result": result_text}
