# backend/vapi_tool_handlers.py
"""
Handlers pour le function_tool Vapi (OpenAI direct + tool obligatoire).
Actions : get_slots, book, cancel, modify, faq.
Réponses au format Vapi : results[{ toolCallId, result: string }].
"""

from __future__ import annotations

import json
import logging
import concurrent.futures
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

from backend import prompts, tools_booking

logger = logging.getLogger(__name__)
_VOICE_SYNC_FETCH_TIMEOUT_S = 6.5


def _slot_to_vocal_label(slot: Any) -> str:
    """Label vocal complet (jour + date + heure) pour un slot."""
    return tools_booking.slot_to_vocal_label(slot)


def _vapi_result_string(data: Dict[str, Any]) -> str:
    """Sérialise le résultat en une seule ligne (Vapi exige result = string)."""
    return json.dumps(data, ensure_ascii=False)


def build_book_tool_result(session: Any, payload: Optional[Dict[str, Any]]) -> str:
    """
    Retour tool Vapi pour `book`.
    - `confirmed` : renvoyer un texte final court, déjà prêt à prononcer.
    - autres statuts : conserver le JSON strict existant.
    """
    status = str((payload or {}).get("status") or "").strip().lower()
    if status != "confirmed":
        return _vapi_result_string(payload or {})
    # Phrase de clôture figée pour éviter les variations LLM/TTS.
    return prompts.get_invariant_vocal_phrase("booking_confirmed_closing")


def handle_get_slots(
    session: Any,
    preference: Optional[str],
    call_id: str,
    user_message: Optional[str] = None,
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
        # Conserver la contrainte explicite de jour/date (ex: "demain", "mardi")
        # même si le modèle ne passe que "après-midi" dans `preference`.
        parse_source = " ".join(
            p for p in ((user_message or "").strip(), (preference or "").strip()) if p
        ).strip()
        if parse_source:
            try:
                from backend.entity_extraction import extract_pref, extract_target_date

                extracted_pref = extract_pref(parse_source)
                extracted_date = extract_target_date(parse_source)
                if extracted_pref:
                    session.qualif_data.pref = extracted_pref
                elif preference:
                    session.qualif_data.pref = preference.strip()
                if extracted_date:
                    session.qualif_data.target_date = extracted_date.isoformat()
            except Exception:
                # Ne jamais bloquer le tool pour un souci de parsing.
                if preference:
                    session.qualif_data.pref = preference.strip()
        elif preference:
            session.qualif_data.pref = preference.strip()

        raw_pref = (getattr(session.qualif_data, "pref", None) or preference or "").strip()
        pref = raw_pref.lower()
        if pref == "apres-midi":
            pref = "après-midi"
        cache_pref = pref if pref in ("matin", "après-midi", "soir", "") else None
        tenant_id = getattr(session, "tenant_id", None) or 1

        target_date_obj = None
        td_raw = getattr(session.qualif_data, "target_date", None)
        if td_raw:
            try:
                from datetime import date as _date

                target_date_obj = _date.fromisoformat(str(td_raw)[:10])
            except ValueError:
                target_date_obj = None

        # Fast path vocal: lire une fenêtre cache plus large, puis limiter à 3 après garde-fous.
        # Sinon, si les 3 premiers sont "aujourd'hui", on peut tomber à 0 alors que demain existe.
        cache_window = max(3, int(getattr(tools_booking, "SLOTS_POOL_SIZE", 9) or 9))
        slots = tools_booking._get_cached_slots(limit=cache_window, tenant_id=tenant_id, pref=cache_pref or None)
        if not slots and cache_pref:
            slots = tools_booking._get_cached_slots(limit=cache_window, tenant_id=tenant_id, pref=None)
            if slots:
                logger.info(
                    "CALENDAR_FETCH_CACHE_FALLBACK",
                    extra={"call_id": call_id[:24] if call_id else "", "from_pref": cache_pref, "to_pref": "none"},
                )

        # Garde-fous identiques à get_slots_for_display sur les slots cachés :
        # le cache peut avoir été rempli par le canal web (sans plancher "demain").
        if slots:
            from backend.entity_extraction import weekday_from_pref

            tz = tools_booking._tenant_zoneinfo(tenant_id)
            weekday_pref = weekday_from_pref(raw_pref) if not target_date_obj else None
            min_start = tools_booking._context_min_start_datetime(
                pref=raw_pref or None,
                target_date_obj=target_date_obj,
                weekday_pref=weekday_pref,
                session=session,
                channel=(getattr(session, "channel", "") or "vocal"),
                tenant_id=tenant_id,
            )
            before_guard = len(slots)
            slots = tools_booking._filter_slots_by_min_start(slots, min_start, tz=tz)
            if target_date_obj and slots:
                slots = tools_booking._filter_slots_by_target_date(slots, target_date_obj, tz=tz)
            elif weekday_pref is not None and slots:
                slots = tools_booking._filter_slots_by_weekday(slots, weekday_pref, tz=tz)
            if len(slots) != before_guard:
                logger.info(
                    "CALENDAR_FETCH_CACHE_GUARDRAIL call_id=%s kept=%d/%d min_start=%s",
                    call_id[:24] if call_id else "",
                    len(slots),
                    before_guard,
                    min_start.isoformat() if min_start else "none",
                )
            # Réponse tool bornée à 3 créneaux, mais seulement après filtrage.
            slots = (slots or [])[:3]

        sync_timed_out = False
        if not slots:
            # Cache froid : tenter une lecture synchrone courte avant d'échouer.
            # Cela évite le faux négatif "agenda indisponible" au premier essai.
            def _load_slots_sync():
                return tools_booking.get_slots_for_display(
                    limit=3,
                    pref=raw_pref or None,
                    session=session,
                    exclude_start_iso=exclude_start_iso or None,
                    exclude_end_iso=exclude_end_iso or None,
                )

            ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = None
            try:
                # En prod, une lecture Google multi-jours peut prendre ~6s.
                # On laisse plus de marge ici tout en restant sous le hard cap global du webhook.
                future = ex.submit(_load_slots_sync)
                slots = future.result(timeout=_VOICE_SYNC_FETCH_TIMEOUT_S)
            except concurrent.futures.TimeoutError:
                slots = None
                sync_timed_out = True
                if future is not None and hasattr(future, "cancel"):
                    future.cancel()
                logger.warning(
                    "CALENDAR_FETCH_SYNC_TIMEOUT call_id=%s pref=%s",
                    call_id[:24] if call_id else "",
                    raw_pref or "any",
                )
            except Exception as e:
                slots = None
                logger.warning(
                    "CALENDAR_FETCH_SYNC_ERROR call_id=%s pref=%s err=%s",
                    call_id[:24] if call_id else "",
                    raw_pref or "any",
                    str(e)[:120],
                )
            finally:
                try:
                    ex.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    ex.shutdown(wait=False)

        if not slots:
            # On garde un refresh asynchrone pour les tours suivants si la tentative courte a échoué.
            def _refresh_cache_async() -> None:
                try:
                    tools_booking.get_slots_for_display(
                        limit=3,
                        pref=raw_pref or None,
                        session=session,
                        exclude_start_iso=exclude_start_iso or None,
                        exclude_end_iso=exclude_end_iso or None,
                    )
                except Exception:
                    pass

            threading.Thread(target=_refresh_cache_async, daemon=True).start()
            logger.warning(
                "CALENDAR_FETCH_CACHE_MISS_FAST_FAIL call_id=%s pref=%s",
                call_id[:24] if call_id else "",
                raw_pref or "any",
            )
            if sync_timed_out:
                # Dégradation non bloquante : laisser la voix répondre "Aucun créneau..."
                # plutôt qu'un faux "agenda indisponible" quand c'est juste trop lent.
                return ([], None, "")
            return (None, None, prompts.get_invariant_vocal_phrase("agenda_unavailable"))

        # Voice path: do not re-fetch Google full slot objects synchronously.
        # pending_slots already contains enough canonical data to book.
        tools_booking.store_pending_slots(session, slots, enrich_google=False)
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
        return (None, None, prompts.get_invariant_vocal_phrase("agenda_unavailable"))


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

    from backend.booking_origin import VOICE as BO_VOICE

    setattr(session, "booking_origin", BO_VOICE)

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
        # Compat Vapi: certains runtimes lisent uniquement `result`.
        # On renvoie donc aussi `result` pour éviter "No result returned".
        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": error_message,
                    "error": error_message,
                }
            ]
        }
    if result_body is not None:
        result = result_body if isinstance(result_body, str) else _vapi_result_string(result_body)
        return {"results": [{"toolCallId": tool_call_id, "result": result}]}
    return {"results": [{"toolCallId": tool_call_id, "result": _vapi_result_string({"status": "ok"})}]}


def build_vapi_tool_response_legacy(result_text: str) -> Dict[str, Any]:
    """Réponse simple pour compat (sans action structurée)."""
    return {"result": result_text}
