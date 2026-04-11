# backend/vapi_tool_handlers.py
"""
Handlers pour le function_tool Vapi (OpenAI direct + tool obligatoire).
Actions : get_slots, validate_contact, book, cancel, modify, faq.
Réponses au format Vapi : results[{ toolCallId, result: string }].
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

from backend import prompts, tools_booking
from backend.slot_choice import detect_slot_choice_early
from backend.vapi_contact_state import get_contact_state, sync_contact_state, validate_contact as validate_contact_state

logger = logging.getLogger(__name__)
_VOICE_SYNC_FETCH_TIMEOUT_S = 8.5
AGENDA_UNAVAILABLE_MSG = "Je n'arrive pas à consulter l'agenda pour le moment. Souhaitez-vous qu'on vous rappelle ?"


def _slot_to_vocal_label(slot: Any) -> str:
    """Label vocal complet (jour + date + heure) pour un slot."""
    return tools_booking.slot_to_vocal_label(slot)


def _vapi_result_string(data: Dict[str, Any]) -> str:
    """Sérialise le résultat en une seule ligne (Vapi exige result = string)."""
    return json.dumps(data, ensure_ascii=False)


def build_book_tool_result(session: Any, payload: Optional[Dict[str, Any]]) -> str:
    """
    Retour tool Vapi pour `book`.
    - `confirmed` : renvoyer un statut structuré pour que le prompt pilote `endCall`
      sans relecture libre du texte.
    - autres statuts : conserver le JSON strict existant.
    """
    status = str((payload or {}).get("status") or "").strip().lower()
    return _vapi_result_string(payload or {})


def build_validate_contact_tool_result(payload: Optional[Dict[str, Any]]) -> str:
    """Retour tool Vapi pour `validate_contact`."""
    return _vapi_result_string(payload or {})


def _parse_preferred_time_to_minute(value: Optional[str]) -> Optional[int]:
    """Parse `HH:MM` ou `HHhMM` vers minute du jour."""
    raw = (value or "").strip().lower()
    if not raw:
        return None
    normalized = raw.replace("h", ":")
    parts = normalized.split(":", 1)
    try:
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
    except ValueError:
        return None
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return None
    return hh * 60 + mm


def _normalize_preferred_time_type(value: Optional[str]) -> str:
    """Mappe la sémantique tool vers la contrainte session interne."""
    raw = (value or "").strip().lower()
    if raw == "min":
        return "after"
    if raw == "max":
        return "before"
    if raw == "exact":
        return "exact"
    return "around"


def handle_get_slots(
    session: Any,
    preference: Optional[str],
    call_id: str,
    preferred_time: Optional[str] = None,
    preferred_time_type: Optional[str] = None,
    exclude_start_iso: Optional[str] = None,
    exclude_end_iso: Optional[str] = None,
) -> Tuple[Optional[List[str]], Optional[str], str, Optional[str]]:
    """
    Récupère les créneaux depuis Google Calendar (ou SQLite).
    exclude_start_iso / exclude_end_iso : créneau à exclure (ex. après slot_taken).
    Returns: (slots_list, source, error_message, error_reason).
    """
    try:
        pref = (preference or "").strip().lower()
        if pref not in ("matin", "après-midi", "apres-midi", "soir", ""):
            pref = None
        if pref == "apres-midi":
            pref = "après-midi"
        preferred_time_minute = _parse_preferred_time_to_minute(preferred_time)
        preferred_time_constraint = _normalize_preferred_time_type(preferred_time_type) if preferred_time_minute is not None else ""
        cache_disabled = preferred_time_minute is not None
        if preferred_time_minute is not None:
            session.time_constraint_type = preferred_time_constraint
            session.time_constraint_minute = preferred_time_minute
        else:
            session.time_constraint_type = ""
            session.time_constraint_minute = -1
        tenant_id = getattr(session, "tenant_id", None) or 1
        logger.info(
            "CALENDAR_FETCH",
            extra={
                "call_id": call_id[:24] if call_id else "",
                "tenant_id": tenant_id,
                "preference": pref or "any",
                "preferred_time": (preferred_time or "").strip() or None,
                "preferred_time_type": (preferred_time_type or "").strip().lower() or None,
                "preferred_time_parsed": preferred_time_minute,
                "time_constraint_type": preferred_time_constraint or None,
                "cache_disabled": cache_disabled,
                "exclude": bool(exclude_start_iso or exclude_end_iso),
                "sync_timeout_s": _VOICE_SYNC_FETCH_TIMEOUT_S,
            },
        )
        logger.info(
            "GET_SLOTS_ARGS call_id=%s tenant_id=%s pref=%s preferred_time=%s preferred_time_type=%s parsed=%s constraint=%s cache_disabled=%s",
            call_id[:24] if call_id else "",
            tenant_id,
            pref or "any",
            (preferred_time or "").strip() or None,
            (preferred_time_type or "").strip().lower() or None,
            preferred_time_minute,
            preferred_time_constraint or None,
            cache_disabled,
        )

        # Fast path vocal: répondre depuis le cache chaud pour rester sous les timeouts Vapi.
        # On tente pref demandée, puis fallback pref=None avant d'appeler Google.
        slots = None
        if not cache_disabled:
            slots = tools_booking._get_cached_slots(limit=3, tenant_id=tenant_id, pref=pref or None)
            if not slots and pref:
                slots = tools_booking._get_cached_slots(limit=3, tenant_id=tenant_id, pref=None)
                if slots:
                    logger.info(
                        "CALENDAR_FETCH_CACHE_FALLBACK",
                        extra={"call_id": call_id[:24] if call_id else "", "from_pref": pref, "to_pref": "none"},
                    )
        else:
            logger.info(
                "CALENDAR_FETCH_CACHE_SKIPPED call_id=%s tenant_id=%s pref=%s preferred_time=%s preferred_time_type=%s",
                call_id[:24] if call_id else "",
                tenant_id,
                pref or "any",
                (preferred_time or "").strip() or None,
                (preferred_time_type or "").strip().lower() or None,
            )

        if not slots:
            # Cache froid : tenter une lecture synchrone courte avant d'échouer.
            # Cela évite le faux négatif "agenda indisponible" au premier essai.
            def _load_slots_sync():
                return tools_booking.get_slots_for_display(
                    limit=3,
                    pref=pref or None,
                    session=session,
                    exclude_start_iso=exclude_start_iso or None,
                    exclude_end_iso=exclude_end_iso or None,
                )

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    # En prod, une lecture Google multi-jours peut prendre ~6s.
                    # On laisse plus de marge ici tout en restant sous le hard cap global du webhook.
                    slots = ex.submit(_load_slots_sync).result(timeout=_VOICE_SYNC_FETCH_TIMEOUT_S)
            except concurrent.futures.TimeoutError:
                slots = None
                logger.warning(
                    "CALENDAR_FETCH_SYNC_TIMEOUT call_id=%s tenant_id=%s pref=%s timeout_s=%.1f",
                    call_id[:24] if call_id else "",
                    tenant_id,
                    pref or "any",
                    _VOICE_SYNC_FETCH_TIMEOUT_S,
                )
            except Exception as e:
                slots = None
                logger.warning(
                    "CALENDAR_FETCH_SYNC_ERROR call_id=%s tenant_id=%s pref=%s err_type=%s err=%s",
                    call_id[:24] if call_id else "",
                    tenant_id,
                    pref or "any",
                    type(e).__name__,
                    str(e)[:120],
                )

        if slots is None:
            # On garde un refresh asynchrone pour les tours suivants si la tentative courte a échoué.
            def _refresh_cache_async() -> None:
                try:
                    tools_booking.get_slots_for_display(
                        limit=3,
                        pref=pref or None,
                        session=session,
                        exclude_start_iso=exclude_start_iso or None,
                        exclude_end_iso=exclude_end_iso or None,
                    )
                except Exception:
                    pass

            threading.Thread(target=_refresh_cache_async, daemon=True).start()
            logger.warning(
                "CALENDAR_FETCH_CACHE_MISS_FAST_FAIL call_id=%s tenant_id=%s pref=%s",
                call_id[:24] if call_id else "",
                tenant_id,
                pref or "any",
            )
            return (None, None, AGENDA_UNAVAILABLE_MSG, "timeout")

        # Voice path: do not re-fetch Google full slot objects synchronously.
        # pending_slots already contains enough canonical data to book.
        tools_booking.store_pending_slots(session, slots, enrich_google=False)
        labels = [_slot_to_vocal_label(s) for s in slots]
        _src = getattr(session, "_slots_source", None) or ""
        source = "google_calendar" if (_src == "google") else "sqlite"
        if not labels:
            logger.info(
                "CALENDAR_SLOTS_EMPTY call_id=%s tenant_id=%s pref=%s preferred_time=%s preferred_time_type=%s",
                call_id[:24] if call_id else "",
                tenant_id,
                pref or "any",
                (preferred_time or "").strip() or None,
                (preferred_time_type or "").strip().lower() or None,
            )
        logger.info(
            "CALENDAR_SLOTS_RETURNED",
            extra={
                "call_id": call_id[:24] if call_id else "",
                "tenant_id": tenant_id,
                "count": len(labels),
                "source": source,
            },
        )
        return (labels, source, "", None)
    except Exception as e:
        logger.exception(
            "CALENDAR_FETCH_FAILED call_id=%s tenant_id=%s err_type=%s err=%s",
            call_id[:24] if call_id else "",
            getattr(session, "tenant_id", None) or 1,
            type(e).__name__,
            str(e)[:160],
        )
        return (None, None, AGENDA_UNAVAILABLE_MSG, "technical")


def _slot_payloads_for_vapi(session: Any) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    pending = getattr(session, "pending_slots", None) or []
    for slot in tools_booking.to_canonical_slots(pending):
        start_iso = slot.get("start_iso") or slot.get("start") or ""
        end_iso = slot.get("end_iso") or slot.get("end") or ""
        payloads.append(
            {
                "start_iso": start_iso,
                "end_iso": end_iso,
                "label": tools_booking.slot_to_vocal_label(slot),
                "source": (slot.get("source") or getattr(session, "_slots_source", None) or "unknown"),
            }
        )
    return payloads


def build_get_slots_tool_result(
    session: Any,
    slots_list: Optional[List[str]],
    source: Optional[str],
    error_reason: Optional[str],
    *,
    preferred_time: Optional[str] = None,
    preferred_time_type: Optional[str] = None,
) -> str:
    payload: Dict[str, Any] = {
        "status": "agenda_unavailable" if error_reason else ("ok" if slots_list else "no_slots"),
        "slots": [],
    }
    if source:
        payload["source"] = source
    if preferred_time or preferred_time_type:
        payload["constraint"] = {
            "preferred_time": (preferred_time or "").strip() or None,
            "type": (preferred_time_type or "").strip().lower() or None,
        }
    if error_reason:
        payload["reason"] = error_reason
        return _vapi_result_string(payload)

    slot_payloads = _slot_payloads_for_vapi(session)
    if slot_payloads:
        payload["slots"] = slot_payloads
        return _vapi_result_string(payload)

    for label in slots_list or []:
        payload["slots"].append({"label": label})
    return _vapi_result_string(payload)


def _chosen_slot_iso(session: Any, choice: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
    """Retourne (start_iso, end_iso) du créneau choisi depuis session.pending_slots."""
    pending = getattr(session, "pending_slots", None) or []
    if not pending or choice is None or not (1 <= choice <= len(pending)):
        return None, None
    slots = tools_booking.to_canonical_slots(pending) if pending and not isinstance(pending[0], dict) else list(pending)
    chosen = slots[choice - 1] if choice <= len(slots) else {}
    start = chosen.get("start_iso") or chosen.get("start") or ""
    end = chosen.get("end_iso") or chosen.get("end") or ""
    return (start or None, end or None)


def _resolve_slot_choice(session: Any, selected_slot: Optional[str]) -> Optional[int]:
    raw = (selected_slot or "").strip().lower()
    if not raw:
        return None
    if raw in ("1", "un", "le premier", "le 1"):
        return 1
    if raw in ("2", "deux", "le deuxième", "le 2"):
        return 2
    if raw in ("3", "trois", "le troisième", "le 3"):
        return 3

    pending = getattr(session, "pending_slots", None) or []
    detected_choice = detect_slot_choice_early(selected_slot or "", pending_slots=pending)
    if detected_choice is not None:
        return detected_choice
    for i, slot in enumerate(pending):
        start_iso = (slot.get("start_iso") or slot.get("start") or "").strip().lower() if isinstance(slot, dict) else ""
        end_iso = (slot.get("end_iso") or slot.get("end") or "").strip().lower() if isinstance(slot, dict) else ""
        label = _slot_to_vocal_label(slot)
        if raw == start_iso or raw == end_iso:
            return i + 1
        if raw in label.lower() or label.lower() in raw:
            return i + 1
    return None


def _selected_slot_label(session: Any, choice: Optional[int]) -> Optional[str]:
    if not choice:
        return None
    try:
        return tools_booking.get_label_for_choice(session, choice) or None
    except Exception:
        return None


def _build_booking_event_context(
    session: Any,
    *,
    choice: int,
    call_id: str,
    start_iso: Optional[str],
    end_iso: Optional[str],
    event_id: Optional[str],
) -> str:
    slot_label = tools_booking.get_label_for_choice(session, choice) or ""
    payload = {
        "call_id": (call_id or "").strip(),
        "patient_name": (getattr(session.qualif_data, "name", None) or "").strip(),
        "patient_contact": (getattr(session.qualif_data, "contact", None) or getattr(session, "customer_phone", None) or "").strip(),
        "contact_type": (getattr(session.qualif_data, "contact_type", None) or "").strip(),
        "motif": (getattr(session.qualif_data, "motif", None) or "").strip(),
        "slot_label": slot_label,
        "start_iso": (start_iso or "").strip(),
        "end_iso": (end_iso or "").strip(),
        "event_id": (event_id or "").strip(),
        "booking_source": "google" if (event_id or "").strip() else "local",
    }
    return json.dumps(payload, ensure_ascii=False)


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
    Payload: status in ("confirmed", "failed").
    """
    if patient_name:
        session.qualif_data.name = patient_name.strip()
    if motif:
        session.qualif_data.motif = motif.strip()

    choice = _resolve_slot_choice(session, selected_slot)
    if choice is None:
        logger.warning(
            "BOOKING_INVALID_SELECTED_SLOT call_id=%s selected_slot=%s pending_len=%s",
            (call_id or "")[:24],
            (selected_slot or "")[:80],
            len(getattr(session, "pending_slots", None) or []),
        )
        return (
            {
                "status": "failed",
                "reason": "invalid_selected_slot",
            },
            None,
        )
    session.pending_slot_choice = choice
    start_iso, end_iso = _chosen_slot_iso(session, choice)
    selected_slot_label = _selected_slot_label(session, choice)
    known_phone = getattr(session, "customer_phone", None) or getattr(session.qualif_data, "contact", None)
    sync_contact_state(
        call_id,
        known_phone=known_phone,
        patient_name=getattr(session.qualif_data, "name", None),
        selected_slot_label=selected_slot_label,
    )
    contact_state = get_contact_state(call_id)
    if contact_state and contact_state.get("validation_required") and not contact_state.get("validated"):
        logger.info(
            "BOOKING_CONTACT_NOT_VALIDATED call_id=%s selected_slot=%s",
            (call_id or "")[:24],
            selected_slot_label or choice,
        )
        return (
            {
                "status": "failed",
                "reason": "contact_not_validated",
            },
            None,
        )

    success, reason = tools_booking.book_slot_from_session(session, choice)

    if success:
        session.booking_failures = 0
        event_id = getattr(session, "google_event_id", None) or ""
        if not start_iso or not end_iso:
            start_iso, end_iso = _chosen_slot_iso(session, choice)
        start_iso = start_iso or ""
        end_iso = end_iso or ""
        # Non bloquant: persistance analytics hors chemin critique de réponse tool.
        def _persist_booking_event_bg() -> None:
            try:
                from backend.engine import _persist_ivr_event

                _persist_ivr_event(
                    session,
                    "booking_confirmed",
                    context=_build_booking_event_context(
                        session,
                        choice=choice,
                        call_id=call_id,
                        start_iso=start_iso,
                        end_iso=end_iso,
                        event_id=event_id,
                    ),
                )
            except Exception as e:
                logger.warning("BOOKING_CONFIRMED_PERSIST_FAILED call_id=%s err=%s", (call_id or "")[:24], str(e)[:120])

        threading.Thread(target=_persist_booking_event_bg, daemon=True).start()
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
            return ({"status": "failed", "reason": "fallback_transfer"}, None)
        return (
            {
                "status": "failed",
                "reason": "slot_taken",
                "start_iso": start_iso or "",
                "end_iso": end_iso or "",
            },
            None,
        )

    if reason == "permission":
        return ({"status": "failed", "reason": "permission"}, None)
    # technical ou autre
    return ({"status": "failed", "reason": "technical"}, None)


def handle_validate_contact(
    session: Any,
    *,
    call_id: str,
    selected_slot: Optional[str],
    patient_name: Optional[str],
    phone_number: Optional[str],
    confirmation_last4: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Valide le contact vocal avant booking."""
    if patient_name:
        session.qualif_data.name = patient_name.strip()

    choice = None
    selected_slot_label = None
    if selected_slot:
        choice = _resolve_slot_choice(session, selected_slot)
        session.pending_slot_choice = choice
        selected_slot_label = _selected_slot_label(session, choice)

    known_phone = getattr(session, "customer_phone", None) or getattr(session.qualif_data, "contact", None)
    payload = validate_contact_state(
        call_id,
        known_phone=known_phone,
        phone_number=phone_number,
        confirmation_last4=confirmation_last4,
        patient_name=getattr(session.qualif_data, "name", None),
        selected_slot_label=selected_slot_label,
    )

    if payload.get("status") == "validated":
        normalized_phone = getattr(session, "customer_phone", None) or getattr(session.qualif_data, "contact", None)
        if phone_number:
            from backend import db

            normalized_phone = db.normalize_phone_number(phone_number)
            session.customer_phone = normalized_phone or session.customer_phone
        if normalized_phone:
            session.qualif_data.contact = normalized_phone
            session.qualif_data.contact_type = "phone"
        logger.info(
            "CONTACT_VALIDATED call_id=%s via=%s known_number=%s",
            (call_id or "")[:24],
            payload.get("validated_via") or "",
            bool(payload.get("known_number")),
        )
    else:
        logger.info(
            "CONTACT_VALIDATION_FAILED call_id=%s reason=%s",
            (call_id or "")[:24],
            payload.get("reason") or "",
        )

    return (payload, None)


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
