# backend/vapi_tool_handlers.py
"""
Handlers pour le function_tool Vapi (OpenAI direct + tool obligatoire).
Actions : get_slots, book, cancel, modify, faq.
Réponses au format Vapi : results[{ toolCallId, result: string }].
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

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
) -> Tuple[Optional[List[str]], Optional[str], str]:
    """
    Récupère les créneaux depuis Google Calendar (ou SQLite).
    Returns: (slots_list, source, error_message).
    Si error_message non vide, slots_list peut être None.
    """
    logger.info("CALENDAR_FETCH", extra={"call_id": call_id[:24] if call_id else "", "preference": preference or "any"})
    try:
        pref = (preference or "").strip().lower()
        if pref not in ("matin", "après-midi", "apres-midi", "soir", ""):
            pref = None
        if pref == "apres-midi":
            pref = "après-midi"
        slots = tools_booking.get_slots_for_display(limit=3, pref=pref or None, session=session)
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


def handle_book(
    session: Any,
    selected_slot: Optional[str],
    patient_name: Optional[str],
    motif: Optional[str],
    call_id: str,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Réserve le créneau choisi (1, 2 ou 3, ou libellé).
    Returns: (success, result_dict, error_message).
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
    success, reason = tools_booking.book_slot_from_session(session, choice)
    slot_label = tools_booking.get_label_for_choice(session, choice) or (selected_slot or "")

    if success:
        patient = patient_name or session.qualif_data.name or "le patient"
        slot_str = str(slot_label) if slot_label else ""
        patient_str = str(patient).strip() or "le patient"
        motif_str = str(motif or session.qualif_data.motif or "consultation").strip()
        message = f"Rendez-vous confirmé pour {patient_str} le {slot_str}."
        logger.info(
            "BOOKING_CONFIRMED",
            extra={"call_id": call_id[:24] if call_id else "", "slot": slot_str[:40], "patient_name": patient_str[:20]},
        )
        return (
            True,
            {
                "status": "confirmed",
                "slot": slot_str,
                "patient": patient_str,
                "motif": motif_str,
                "message": message,
            },
            "",
        )
    if reason == "technical":
        return (False, None, "Impossible de consulter l'agenda pour le moment.")
    if reason == "permission":
        return (False, None, "Problème d'accès à l'agenda.")
    return (False, None, "Ce créneau n'est plus disponible.")


def build_vapi_tool_response(
    tool_call_id: Optional[str],
    result_body: Optional[Dict[str, Any]],
    error_message: Optional[str],
) -> Dict[str, Any]:
    """
    Construit la réponse au format Vapi.
    result et error doivent être des strings (Vapi).
    """
    if tool_call_id is None:
        tool_call_id = "call_default"
    if error_message:
        return {"results": [{"toolCallId": tool_call_id, "error": error_message}]}
    if result_body is not None:
        return {"results": [{"toolCallId": tool_call_id, "result": _vapi_result_string(result_body)}]}
    return {"results": [{"toolCallId": tool_call_id, "result": _vapi_result_string({"status": "ok"})}]}


def build_vapi_tool_response_legacy(result_text: str) -> Dict[str, Any]:
    """Réponse simple pour compat (sans action structurée)."""
    return {"result": result_text}
