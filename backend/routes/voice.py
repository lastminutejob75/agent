# backend/routes/voice.py
"""
Route pour le canal Voix (Vapi) - DEBUG COMPLET + TIMERS
Avec mémoire client et stats pour rapports.
"""

from fastapi import APIRouter, Request
from fastapi.responses import Response, JSONResponse, StreamingResponse
import asyncio
import logging
import json
import re
import time
import uuid
from typing import Optional, TYPE_CHECKING

from backend.engine import ENGINE
from backend import prompts, config
from backend.tenant_config import get_tenant_display_config
from backend.client_memory import get_client_memory
from backend.session_codec import session_to_dict
from backend.conversational_engine import ConversationalEngine, _is_canary
from backend.reports import get_report_generator
from backend.validation import validate_response as validate_response_tts
from backend.stt_utils import normalize_transcript, is_filler_only
from backend.stt_common import (
    classify_text_only,
    estimate_tts_duration,
    is_critical_overlap,
    is_critical_token,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instances singleton
client_memory = get_client_memory()
report_generator = get_report_generator()

# Mode conversationnel P0 (lazy)
_conversational_engine = None

def _get_or_resume_voice_session(tenant_id: int, call_id: str):
    """
    Phase 2: PG-first read pour reprise après restart/multi-instance.
    Si session absente en mémoire → tenter load depuis PG, sinon get_or_create.
    """
    session = ENGINE.session_store.get(call_id)
    if session is None and config.USE_PG_CALL_JOURNAL:
        try:
            from backend.session_pg import load_session_pg_first
            result = load_session_pg_first(tenant_id, call_id)
            if result:
                s_pg, ck_seq, last_seq = result
                if hasattr(ENGINE.session_store, "set_for_resume"):
                    ENGINE.session_store.set_for_resume(s_pg)
                else:
                    cache = getattr(ENGINE.session_store, "_memory_cache", None)
                    if cache is not None:
                        cache[call_id] = s_pg
                logger.info(
                    "[CALL_RESUME] source=pg tenant_id=%s call_id=%s state=%s ck_seq=%s last_seq=%s",
                    tenant_id, call_id[:20], s_pg.state, ck_seq, last_seq,
                )
                try:
                    from backend.engine import _persist_ivr_event
                    _persist_ivr_event(s_pg, "resume_from_pg", reason=f"ck_seq={ck_seq}")
                except Exception:
                    pass
                session = s_pg
        except Exception as e:
            logger.warning("[CALL_RESUME_WARN] pg_down/err=%s", e, exc_info=True)
    if session is None:
        session = ENGINE.session_store.get_or_create(call_id)
    return session


def _looks_like_booking_request(text: str) -> bool:
    """True si le message ressemble à une demande de RDV (évite transfert à tort)."""
    if not text or not text.strip():
        return False
    t = text.strip().lower()
    return "rendez" in t or " rdv" in t or t.startswith("rdv") or "je voudrais un" in t or "je veux un" in t


def _get_engine(call_id: str):
    """Retourne l'engine à utiliser : conversationnel (si flag + canary) ou FSM."""
    if config.CONVERSATIONAL_MODE_ENABLED and _is_canary(call_id):
        global _conversational_engine
        if _conversational_engine is None:
            from backend.cabinet_data import CabinetData
            from backend.llm_conversation import get_default_conv_llm_client
            _conversational_engine = ConversationalEngine(
                cabinet_data=CabinetData.default(config.BUSINESS_NAME),
                faq_store=ENGINE.faq_store,
                llm_client=get_default_conv_llm_client(),
                fsm_engine=ENGINE,
            )
        return _conversational_engine
    return ENGINE


def _parse_stream_flag(payload: dict) -> bool:
    """
    Détection robuste de stream: true (Vapi Custom LLM).
    - bool → ok
    - string "true"/"1"/"yes" (case-insensitive) → True
    - string "false"/"0"/"no" → False
    - int 1 → True, 0 → False
    - sinon → bool(val) pour compat
    """
    for key in ("stream", "streaming"):
        val = payload.get(key)
        if val is None:
            continue
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            low = val.strip().lower()
            if low in ("true", "1", "yes"):
                return True
            if low in ("false", "0", "no"):
                return False
        if isinstance(val, int):
            return val != 0
        return bool(val)
    return False


def _make_chat_response(call_id: str, text: str, is_streaming: bool):
    """
    Point de sortie unique pour /chat/completions : SSE si stream demandé, sinon JSON.
    Contrat Vapi : stream=true → Content-Type text/event-stream + data: ... + data: [DONE].
    """
    if is_streaming:
        return StreamingResponse(
            _sse_stream_for_text(call_id, text or ""),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    return _chat_completion_response(call_id, text, _stream_requested=False)


def _sse_stream_for_text(call_id: str, text: str):
    """
    Générateur SSE au format OpenAI chat.completion.chunk pour un texte complet.
    Utilisé quand stream=true pour LockTimeout, erreur, ou réponse courte.
    """
    chunk_role = {
        "id": f"chatcmpl-{call_id}",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    }
    yield f"data: {json.dumps(chunk_role)}\n\n"
    words = (text or "").strip().split()
    for i, word in enumerate(words):
        content = f" {word}" if i > 0 else word
        chunk = {
            "id": f"chatcmpl-{call_id}",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    chunk_final = {
        "id": f"chatcmpl-{call_id}",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(chunk_final)}\n\n"
    yield "data: [DONE]\n\n"


def _reconstruct_session_from_history(session, messages: list, call_id: str = ""):
    """
    Reconstruit l'état de la session depuis l'historique des messages.
    Nécessaire si la session en mémoire a été perdue (redémarrage Railway).
    
    STRATÉGIE: Extraire TOUTES les données depuis l'historique
    Traçabilité: log WARN, ivr_event session_reconstruct_used
    """
    from backend.guards import clean_name_from_vocal
    from backend.engine import _persist_ivr_event

    logger.warning(
        "[SESSION_RECONSTRUCT] conv_id=%s reason=session_lost messages=%s",
        call_id or getattr(session, "conv_id", ""),
        len(messages),
    )
    try:
        _persist_ivr_event(session, "session_reconstruct_used", reason="session_lost")
    except Exception:
        pass

    # Patterns pour détecter l'état
    patterns = {
        "QUALIF_NAME": ["c'est à quel nom", "quel nom", "votre nom"],
        "QUALIF_PREF": ["matin ou l'après-midi", "matin ou après-midi", "préférez"],
        "QUALIF_CONTACT": ["numéro de téléphone", "téléphone pour vous rappeler", "redonner votre numéro"],
        "CONTACT_CONFIRM": ["votre numéro est bien", "j'ai noté le", "je confirme", "c'est bien ça", "est-ce correct"],
        "CONTACT_CONFIRM_CALLERID": ["numéro qui s'affiche", "se termine par", "est-ce bien le vôtre"],
        "WAIT_CONFIRM": ["j'ai trois créneaux", "voici trois créneaux", "j'ai deux créneaux", "j'ai un créneau", "dites un, deux ou trois", "dites simplement", "dites un ou deux"],
        "CONFIRMED": ["rendez-vous est confirmé", "c'est confirmé"],
        "POST_FAQ": ["puis-je vous aider pour autre chose", "autre chose pour vous", "souhaitez-vous autre chose"],
        "POST_FAQ_CHOICE": [
            "rendez-vous ou",
            "souhaitez-vous prendre rendez-vous",
            "ou avez-vous une autre question",
            "rdv ou question",
        ],
    }
    
    # Parcourir TOUS les messages pour extraire les données
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "").lower()
            
            # Extraire le nom
            if any(p in content for p in patterns["QUALIF_NAME"]):
                if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                    potential_name = messages[i + 1].get("content", "").strip()
                    if (len(potential_name) >= 2 and 
                        len(potential_name) <= 50 and
                        "matin" not in potential_name.lower() and
                        "après" not in potential_name.lower()):
                        cleaned_name = clean_name_from_vocal(potential_name)
                        if len(cleaned_name) >= 2:
                            session.qualif_data.name = cleaned_name
                            logger.debug("reconstruct name: %r -> %r", potential_name, cleaned_name)
            
            # Extraire la préférence
            if any(p in content for p in patterns["QUALIF_PREF"]):
                if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                    potential_pref = messages[i + 1].get("content", "").strip()
                    if potential_pref and len(potential_pref) <= 50:
                        session.qualif_data.pref = potential_pref
                        logger.debug("reconstruct pref: %r", potential_pref)
            
            # Extraire le contact
            if any(p in content for p in patterns["QUALIF_CONTACT"]):
                if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                    potential_contact = messages[i + 1].get("content", "").strip()
                    if potential_contact:
                        session.qualif_data.contact = potential_contact
                        logger.debug("reconstruct contact: %r", potential_contact)

            # Extraire le choix de créneau (1/2/3) après proposition de slots
            if any(p in content for p in patterns["WAIT_CONFIRM"]):
                if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                    choice_text = (messages[i + 1].get("content", "") or "").strip().lower()
                    choice_map = {"un": 1, "1": 1, "une": 1, "deux": 2, "2": 2, "trois": 3, "3": 3}
                    for k, v in choice_map.items():
                        if k in choice_text or choice_text == k:
                            session.pending_slot_choice = v
                            logger.debug("reconstruct pending_slot_choice: %r -> %s", choice_text, v)
                            break
    
    # Déterminer l'état ACTUEL basé sur le dernier message assistant
    last_assistant_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            last_assistant_msg = msg.get("content", "").lower()
            break
    
    detected_state = None
    for state, state_patterns in patterns.items():
        if any(p in last_assistant_msg for p in state_patterns):
            detected_state = state
            break
    
    # Si état détecté
    if detected_state:
        session.state = detected_state
        logger.debug("reconstruct state: %s", detected_state)
        if detected_state == "WAIT_CONFIRM":
            logger.debug("reconstruct WAIT_CONFIRM - slots will be re-fetched on next handler call")
        # P0: CONTACT_CONFIRM sans slots → re-fetch pour éviter "problème technique"
        if detected_state in ("CONTACT_CONFIRM", "CONTACT_CONFIRM_CALLERID") and session.pending_slot_choice and not (getattr(session, "pending_slots", None) or []):
            try:
                from backend import tools_booking
                from backend.calendar_adapter import get_calendar_adapter
                fresh_slots = tools_booking.get_slots_for_display(limit=3, pref=getattr(session.qualif_data, "pref", None), session=session)
                if fresh_slots:
                    adapter = get_calendar_adapter(session)
                    source = "google" if (adapter and adapter.can_propose_slots()) else "sqlite"
                    session.pending_slots = tools_booking.to_canonical_slots(fresh_slots, source)
                    logger.info("[RECONSTRUCT_SLOTS] conv_id=%s re-fetched %s slots for CONTACT_CONFIRM", call_id or getattr(session, "conv_id", ""), len(fresh_slots))
            except Exception as e:
                logger.warning("[RECONSTRUCT_SLOTS] failed: %s", e)
    else:
        logger.warning("reconstruct could not detect state from last assistant msg")
    logger.debug("reconstruct complete: state=%s name=%s pref=%s", session.state, session.qualif_data.name, session.qualif_data.pref)
    
    return session


def _pg_lock_ok() -> bool:
    """Phase 2.1: PG journal activé et URL présente."""
    if not getattr(config, "USE_PG_CALL_JOURNAL", True):
        return False
    try:
        from backend.session_pg import _pg_url
        return _pg_url() is not None
    except Exception:
        return False


def _call_journal_ensure(tenant_id: int, call_id: str, initial_state: str = "START") -> None:
    """Phase 1 dual-write: assure call_sessions existe. Si PG down: log WARN, continue."""
    if not getattr(config, "USE_PG_CALL_JOURNAL", True):
        return
    try:
        from backend.session_pg import pg_ensure_call_session
        ok = pg_ensure_call_session(tenant_id, call_id, initial_state)
        if not ok:
            logger.debug("[CALL_JOURNAL] pg_ensure_call_session skipped (no PG)")
    except Exception as e:
        logger.warning("[CALL_JOURNAL_WARN] pg_down reason=ensure %s", e)


def _call_journal_user_message(tenant_id: int, call_id: str, text: str) -> None:
    """Phase 1 dual-write: log message user. Si PG down: log WARN, continue."""
    if not getattr(config, "USE_PG_CALL_JOURNAL", True):
        return
    try:
        from backend.session_pg import pg_ensure_call_session, pg_add_message
        pg_ensure_call_session(tenant_id, call_id)
        pg_add_message(tenant_id, call_id, "user", text or "")
    except Exception as e:
        logger.warning("[CALL_JOURNAL_WARN] pg_down reason=user_msg %s", e)


def _call_journal_agent_response(
    tenant_id: int,
    call_id: str,
    session,
    response_text: str,
    state_before: str,
    should_checkpoint: bool,
) -> None:
    """
    Phase 1 dual-write: log message agent, update state, optionnel checkpoint.
    should_checkpoint: True si state changé OU pending_slots critique OU toutes les N écritures.
    """
    if not getattr(config, "USE_PG_CALL_JOURNAL", True):
        return
    try:
        from backend.session_pg import (
            pg_ensure_call_session,
            pg_add_message,
            pg_update_last_state,
            pg_write_checkpoint,
        )
        from backend.session_codec import session_to_dict
        pg_ensure_call_session(tenant_id, call_id)
        seq = pg_add_message(tenant_id, call_id, "agent", response_text or "")
        pg_update_last_state(tenant_id, call_id, getattr(session, "state", "START"))
        if should_checkpoint and seq is not None:
            state_json = session_to_dict(session)
            pg_write_checkpoint(tenant_id, call_id, seq, state_json)
    except Exception as e:
        logger.warning("[CALL_JOURNAL_WARN] pg_down reason=agent_response %s", e)


def log_timer(label: str, start: float) -> float:
    """Log le temps écoulé et retourne le nouveau timestamp."""
    now = time.time()
    elapsed_ms = (now - start) * 1000
    logger.debug("%s: %.0fms", label, elapsed_ms)
    return now


def _looks_like_name_for_cancel(text: str) -> bool:
    """True si le message ressemble à un nom (annulation) : non vide, >= 2 car., pas que des chiffres."""
    if not text or not text.strip():
        return False
    t = text.strip()
    if len(t) < 2:
        return False
    if t.isdigit():
        return False
    return True


router = APIRouter(prefix="/api/vapi", tags=["voice"])


@router.get("/test-calendar")
async def test_calendar_connection():
    """Test de connexion Google Calendar"""
    from backend import tools_booking
    import os
    
    try:
        # Test 1: Variables d'environnement (lecture directe)
        env_var = os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "6fd8676f...")
        
        # Vérifier quel fichier est réellement utilisé
        from backend import config
        
        result = {
            "calendar_id": calendar_id,
            "service_account_file_from_config": config.SERVICE_ACCOUNT_FILE,
            "env_var_present": bool(env_var),
            "env_var_length": len(env_var) if env_var else 0,
            "file_exists": False,
            "slots_available": False,
            "error": None
        }
        
        # Test 2: Fichier existe ?
        import os
        result["service_account_file"] = config.SERVICE_ACCOUNT_FILE
        if config.SERVICE_ACCOUNT_FILE and os.path.exists(config.SERVICE_ACCOUNT_FILE):
            result["file_exists"] = True
        else:
            result["file_exists"] = False
            result["file_path_checked"] = config.SERVICE_ACCOUNT_FILE
        
        # Test 3: Récupérer des créneaux
        slots = tools_booking.get_slots_for_display(limit=3)
        if slots and len(slots) > 0:
            result["slots_available"] = True
            result["slots"] = [{"idx": s.idx, "label": s.label} for s in slots]
        
        return result
        
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }




def _is_agent_speaking(session) -> bool:
    """Vrai si l'agent est en train de parler (TTS en cours, selon estimation)."""
    now = time.time()
    until = getattr(session, "speaking_until_ts", 0) or 0
    return now < until


def _parse_stream_flag(payload: dict) -> bool:
    """
    Détection robuste de stream/streaming dans le payload Vapi.
    - bool → tel quel
    - string → "true"/"1"/"yes" (case-insensitive) = True, "false"/"0"/"no" = False
    - int → 1 = True, 0 = False
    - sinon → bool(val) pour éviter "false" string → True
    """
    for key in ("stream", "streaming"):
        val = payload.get(key)
        if val is None:
            continue
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            if val.strip().lower() in ("true", "1", "yes"):
                return True
            if val.strip().lower() in ("false", "0", "no"):
                return False
        if isinstance(val, int):
            return val != 0
    return False


def _make_chat_response(call_id: str, text: str, is_streaming: bool):
    """
    Point de sortie unique pour /chat/completions : SSE si stream demandé, sinon JSON.
    Contrat Vapi : stream=true → Content-Type: text/event-stream + data: ... + data: [DONE].
    """
    if is_streaming:
        return StreamingResponse(
            _sse_stream_for_text(call_id, text),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    return _chat_completion_response(call_id, text, _stream_requested=False)


def _chat_completion_response(call_id: str, content: str, _stream_requested: bool = False):
    """
    Réponse OpenAI-like robuste pour /api/vapi/chat/completions (JSON uniquement).
    Compatibilité max : id, object, created, model, usage, content à la racine, choices[0].text.
    Si VAPI_DEBUG_TEST_AUDIO=1 : force content = "TEST AUDIO 123" pour tester le pipeline TTS.
    _stream_requested: si True, log [STREAM_MISMATCH_GUARD] (chemin aurait dû renvoyer du SSE).
    """
    if _stream_requested:
        logger.warning(
            "[STREAM_MISMATCH_GUARD] call_id=%s route=chat/completions reason=json_returned_while_stream_requested",
            call_id[:24] if call_id else "n/a",
        )
    if getattr(config, "VAPI_DEBUG_TEST_AUDIO", False):
        content = "TEST AUDIO 123"
        logger.info("[VAPI_DEBUG] TEST AUDIO 123 forced for TTS check")
    text = (content or "").strip() or "Pouvez-vous répéter, s'il vous plaît ?"
    body = {
        "id": f"chatcmpl-{call_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "uwi-agent",
        "content": text,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "text": text,
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
    logger.info("[VAPI_OUT] chat/completions content_len=%s", len(text))
    return JSONResponse(
        body,
        status_code=200,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


def _vapi_content_response(
    call_id: str,
    response_text: str,
    debug_trace: Optional[str] = None,
    session=None,
):
    """
    Réponse JSON explicite pour Vapi : strip/fallback, log [VAPI_OUT], Content-Type application/json.
    Si session fourni : _debug = call_id[:6]|state (pour vérifier dans les logs Vapi que c'est cette route).
    """
    text = (response_text or "").strip()
    if not text:
        text = "Pouvez-vous répéter, s'il vous plaît ?"
    payload = {"content": text}
    if session is not None:
        payload["_debug"] = f"{call_id[:8]}|{getattr(session, 'state', '?')}"
    elif debug_trace:
        payload["_debug"] = debug_trace
    logger.info(
        "[VAPI_OUT] status=200 content_type=application/json content_len=%s call_id=%s _debug=%s",
        len(text), call_id[:20] if call_id else "n/a", payload.get("_debug", ""),
    )
    return JSONResponse(payload, status_code=200)


def _log_decision_out(
    call_id: str,
    session,
    action_taken: str,
    reply_text: str = "",
    session_key: Optional[str] = None,
) -> None:
    """Log décisionnel sortie (sans PII). session_key = clé de session stable (pour debug boucle)."""
    logger.info(
        "decision_out",
        extra={
            "call_id": call_id,
            "session_key": session_key or call_id,
            "action": action_taken,
            "state_after": getattr(session, "state", "") if session else "",
            "reply_len": len(reply_text or ""),
        },
    )


def _maybe_reset_noise_on_terminal(session, events) -> None:
    """P1-1 : Reset compteurs noise + unclear quand on entre en état terminal (session propre)."""
    if not session or not events:
        return
    conv_state = getattr(events[0], "conv_state", None)
    if conv_state in ("CONFIRMED", "TRANSFERRED"):
        session.noise_detected_count = 0
        session.last_noise_ts = None
        session.unclear_text_count = 0


def _compute_voice_response_sync(
    resolved_tenant_id: int,
    call_id: str,
    user_message: str,
    customer_phone: Optional[str],
    messages: list,
) -> tuple[str, bool]:
    """
    Exécute le tour vocal complet (session, classify, engine) de façon synchrone.
    Retourne (response_text, cancel_lookup_streaming).
    Utilisé pour streaming : permet d'émettre le premier token SSE immédiatement puis de calculer la réponse en thread.
    """
    from backend import tools_booking
    t_start = time.time()
    _call_journal_ensure(resolved_tenant_id, call_id)
    session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
    state_before_turn = getattr(session, "state", "START")
    session.channel = "vocal"
    session.tenant_id = resolved_tenant_id
    response_text = ""
    action_taken = ""
    overlap_handled = False
    cancel_lookup_streaming = False

    if session.state in ("TRANSFERRED", "CONFIRMED"):
        response_text = prompts.VOCAL_RESUME_ALREADY_TERMINATED
        action_taken = "resume_terminal_guard"
        overlap_handled = True
    else:
        _call_journal_ensure(resolved_tenant_id, call_id, state_before_turn)
        _call_journal_user_message(resolved_tenant_id, call_id, user_message or "")
        if customer_phone:
            session.customer_phone = customer_phone
        needs_reconstruct = session.state == "START" and len(messages) > 1 and not session.qualif_data.name
        reconstruct_count = getattr(session, "reconstruct_count", 0)
        last_user_content = next((m.get("content") or "" for m in reversed(messages) if m.get("role") == "user"), "")
        if needs_reconstruct and reconstruct_count >= 1:
            if not _looks_like_booking_request(last_user_content or user_message or ""):
                session.state = "TRANSFERRED"
                response_text = prompts.VOCAL_TRANSFER_COMPLEX
                session.add_message("agent", response_text)
                action_taken = "reconstruct_loop_guard"
                overlap_handled = True
            else:
                logger.info("[SESSION_RECONSTRUCT] conv_id=%s booking-like -> skip transfer", call_id)
        if not overlap_handled and needs_reconstruct and reconstruct_count < 1:
            session = _reconstruct_session_from_history(session, messages, call_id=call_id)
            session.reconstruct_count = 1
        if customer_phone:
            try:
                existing_client = client_memory.get_by_phone(customer_phone, tenant_id=getattr(session, "tenant_id", None))
                if existing_client and existing_client.total_bookings > 0:
                    greeting = client_memory.get_personalized_greeting(existing_client, channel="vocal")
                    if greeting:
                        logger.debug("returning client detected: %s", existing_client.name)
            except Exception:
                pass
        kind, normalized = classify_text_only(user_message or "")
        if kind == "UNCLEAR" and _looks_like_booking_request(user_message or ""):
            kind, normalized = "TEXT", (normalized or normalize_transcript(user_message or ""))
        unclear_count = getattr(session, "unclear_text_count", 0)
        if action_taken not in ("reconstruct_loop_guard", "resume_terminal_guard"):
            overlap_handled = False
            response_text = ""
            action_taken = ""
            if _is_agent_speaking(session):
                if session.state == "WAIT_CONFIRM" and is_critical_token(normalized):
                    pass
                elif is_critical_overlap(user_message or ""):
                    pass
                elif kind in ("UNCLEAR", "SILENCE"):
                    response_text = prompts.MSG_VOCAL_CROSSTALK_ACK
                    action_taken = "overlap_ignored"
                    overlap_handled = True
                elif kind == "TEXT" and len((user_message or "").strip()) < 10:
                    response_text = getattr(prompts, "MSG_OVERLAP_REPEAT_SHORT", "Pardon, pouvez-vous répéter ?")
                    session.add_message("agent", response_text)
                    action_taken = "overlap_repeat"
                    overlap_handled = True
        cancel_lookup_streaming = (
            session.state == "CANCEL_NAME"
            and _looks_like_name_for_cancel(user_message)
        )
        if cancel_lookup_streaming:
            response_text = ""
        elif not overlap_handled:
            try:
                if kind == "SILENCE":
                    events = _get_engine(call_id).handle_message(call_id, "")
                    response_text = events[0].text if events else prompts.MSG_EMPTY_MESSAGE
                    action_taken = "silence"
                    _maybe_reset_noise_on_terminal(session, events or [])
                elif kind == "TEXT":
                    events = _get_engine(call_id).handle_message(call_id, normalized)
                    response_text = events[0].text if events else "Je n'ai pas compris"
                    action_taken = "text"
                    _maybe_reset_noise_on_terminal(session, events or [])
                else:
                    now = time.time()
                    last_reply_ts = getattr(session, "last_agent_reply_ts", 0) or 0
                    overlap_window = getattr(config, "OVERLAP_WINDOW_SEC", 1.2)
                    recent_agent = (now - last_reply_ts) < overlap_window
                    if recent_agent:
                        response_text = getattr(
                            prompts, "MSG_OVERLAP_REPEAT",
                            "Je vous ai entendu en même temps. Pouvez-vous répéter maintenant ?",
                        )
                        session.add_message("agent", response_text)
                        action_taken = "overlap_guard"
                    else:
                        raw_len = len((user_message or ""))
                        last_ts = getattr(session, "last_assistant_ts", 0) or 0
                        within_crosstalk_window = (now - last_ts) < getattr(config, "CROSSTALK_WINDOW_SEC", 5.0)
                        max_crosstalk_len = getattr(config, "CROSSTALK_MAX_RAW_LEN", 40)
                        if within_crosstalk_window and raw_len <= max_crosstalk_len:
                            response_text = prompts.MSG_VOCAL_CROSSTALK_ACK
                            action_taken = "ignore_crosstalk"
                        else:
                            session.unclear_text_count = getattr(session, "unclear_text_count", 0) + 1
                            count = session.unclear_text_count
                            if count == 1:
                                response_text = prompts.MSG_UNCLEAR_1
                                session.add_message("agent", response_text)
                                action_taken = "unclear_1"
                            elif count == 2:
                                events = ENGINE._trigger_intent_router(session, "unclear_text_2", user_message or "")
                                response_text = events[0].text if events else prompts.MSG_UNCLEAR_1
                                action_taken = "unclear_2_intent_router"
                            else:
                                session.state = "TRANSFERRED"
                                response_text = (
                                    prompts.VOCAL_TRANSFER_COMPLEX
                                    if getattr(session, "channel", "") == "vocal"
                                    else prompts.MSG_TRANSFER
                                )
                                session.add_message("agent", response_text)
                                action_taken = "unclear_3_transfer"
            except Exception as e:
                logger.exception("ENGINE ERROR in _compute_voice_response_sync: %s", e)
                response_text = "Excusez-moi, j'ai un petit souci technique. Je vous transfère à un collègue."
        _log_decision_out(call_id, session, action_taken, response_text)
        if hasattr(ENGINE.session_store, "save"):
            ENGINE.session_store.save(session)
        state_after = getattr(session, "state", "START")
        should_cp = (
            state_before_turn != state_after
            or bool(getattr(session, "pending_slots", None))
            or getattr(session, "awaiting_confirmation", None) is not None
            or state_after in ("QUALIF_CONTACT", "WAIT_CONFIRM", "CONTACT_CONFIRM", "CONTACT_CONFIRM_CALLERID")
        )
        _call_journal_agent_response(
            resolved_tenant_id, call_id, session, response_text, state_before_turn, should_checkpoint=should_cp,
        )
        if not cancel_lookup_streaming and response_text:
            session.last_assistant_ts = time.time()
            session.last_agent_reply_ts = time.time()
            if response_text.strip():
                tts_duration = estimate_tts_duration(response_text)
                session.speaking_until_ts = time.time() + tts_duration
        if not cancel_lookup_streaming and session.state in ("CONFIRMED", "TRANSFERRED"):
            try:
                intent = "BOOKING" if session.state == "CONFIRMED" else "TRANSFER"
                report_generator.record_interaction(
                    call_id=call_id,
                    intent=intent,
                    outcome="confirmed" if session.state == "CONFIRMED" else "transferred",
                    channel="vocal",
                    duration_ms=int((time.time() - t_start) * 1000),
                    motif=getattr(session.qualif_data, "motif", None),
                    client_name=getattr(session.qualif_data, "name", None),
                    client_phone=customer_phone,
                )
                if session.state == "CONFIRMED" and getattr(session.qualif_data, "name", None):
                    client = client_memory.get_or_create(
                        phone=customer_phone,
                        name=session.qualif_data.name,
                        email=session.qualif_data.contact if getattr(session.qualif_data, "contact_type", None) == "email" else None,
                        tenant_id=getattr(session, "tenant_id", None),
                    )
                    slot_label = tools_booking.get_label_for_choice(session, session.pending_slot_choice or 1) or "RDV"
                    client_memory.record_booking(
                        client_id=client.id,
                        slot_label=slot_label,
                        motif=session.qualif_data.motif or "consultation",
                        tenant_id=getattr(session, "tenant_id", None),
                    )
            except Exception:
                pass
    return (response_text or "", cancel_lookup_streaming)


def _classify_stt_input(
    raw_text: str,
    confidence: Optional[float],
    transcript_type: str,
    message_type: Optional[str] = None,
) -> tuple[str, str]:
    """
    Classifie l'entrée STT pour nova-2-phonecall.
    Returns: ("NOISE" | "SILENCE" | "TEXT", text_to_use)
    """
    if transcript_type == "partial":
        return "TEXT", raw_text  # fallback (ne devrait pas arriver ici si on filtre en amont)

    normalized = normalize_transcript(raw_text)

    # Whitelist : tokens critiques = TEXT même si confidence très basse
    if is_critical_token(normalized):
        return "TEXT", normalized

    # Transcript vide
    if not normalized or not normalized.strip():
        if confidence is not None and confidence < config.NOISE_CONFIDENCE_THRESHOLD:
            return "NOISE", ""
        # P1 : Parole détectée mais pas transcrite (pas de confidence) → bruit probable
        if message_type:
            mt_lower = message_type.lower()
            if any(x in mt_lower for x in ("user-message", "audio", "speech", "detected")):
                return "NOISE", ""
        return "SILENCE", ""

    # Transcript très court ou filler seul
    if len(normalized) < config.MIN_TEXT_LENGTH or is_filler_only(normalized):
        if confidence is not None and confidence < config.SHORT_TEXT_MIN_CONFIDENCE:
            return "NOISE", normalized
    return "TEXT", normalized


def _webhook_extract_call_id(payload: dict) -> Optional[str]:
    """Extrait call_id depuis un payload webhook Vapi (message.call.id)."""
    message = payload.get("message") or {}
    call = message.get("call") or {}
    return call.get("id") or payload.get("call", {}).get("id")


@router.post("/webhook")
async def vapi_webhook(request: Request):
    """
    Webhook Vapi — Réception assistant.started, status-update, conversation-update, etc.
    On persiste le caller ID (message.call.customer.number) dès assistant.started ou
    status-update in-progress pour que /chat/completions ait session.customer_phone.
    """
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=200)
    message = payload.get("message") or {}
    msg_type = message.get("type") or message.get("event") or ""
    # Persister customer_phone uniquement sur les webhooks qui contiennent call.customer.number
    # (conversation-update / speech-update ne le contiennent pas — source: rapport Vapi)
    from backend.tenant_routing import (
        extract_customer_phone_from_vapi_payload,
        extract_to_number_from_vapi_payload,
        resolve_tenant_id_from_vocal_call,
        current_tenant_id,
    )
    call_id = _webhook_extract_call_id(payload)
    customer_phone = extract_customer_phone_from_vapi_payload(payload)
    if call_id and customer_phone:
        status = message.get("status") or message.get("call", {}).get("status") or ""
        should_persist = (
            (msg_type == "status-update" and status == "in-progress")
            or msg_type in ("assistant.started", "assistant-request", "status_update")
            or (msg_type == "end-of-call-report")
        )
        if should_persist:
            try:
                to_number = extract_to_number_from_vapi_payload(payload)
                resolved_tenant_id, _ = resolve_tenant_id_from_vocal_call(to_number or "", channel="vocal")
                request.state.tenant_id = resolved_tenant_id
                current_tenant_id.set(str(resolved_tenant_id))
                session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
                if not session.customer_phone:
                    session.customer_phone = customer_phone
                    session.channel = "vocal"
                    session.tenant_id = resolved_tenant_id
                    if hasattr(ENGINE.session_store, "save"):
                        ENGINE.session_store.save(session)
                    # Masquer numéro en log (RGPD) : garder 2 derniers chiffres
                    _digits = "".join(c for c in str(customer_phone) if c.isdigit())
                    _masked = f"+33XXXXXX{_digits[-2:]}" if len(_digits) >= 10 else "+33XXXX"
                    logger.info(
                        "CALLER_ID_PERSISTED",
                        extra={"call_id": call_id[:24] if call_id else "", "msg_type": msg_type, "phone_masked": _masked},
                    )
            except Exception as e:
                logger.warning("CALLER_ID_WEBHOOK_SAVE_FAILED call_id=%s err=%s", call_id[:24] if call_id else "", str(e)[:80])
    return Response(status_code=200)


def _tool_extract_call_id(payload: dict) -> str:
    """Extrait call_id depuis payload tool Vapi."""
    call = payload.get("call") or {}
    if call.get("id"):
        return str(call["id"])
    msg = payload.get("message") or {}
    call = msg.get("call") or {}
    if call.get("id"):
        return str(call["id"])
    return payload.get("conversation_id") or "unknown"


def _tool_extract_tool_call_id(payload: dict) -> Optional[str]:
    """Extrait toolCallId pour la réponse Vapi (message.toolCalls[0].id ou message.toolCallList[0].id)."""
    msg = payload.get("message") or {}
    calls = msg.get("toolCalls") or msg.get("toolCallList") or payload.get("toolCalls") or payload.get("toolCallList") or []
    if calls and isinstance(calls, list) and len(calls) > 0 and isinstance(calls[0], dict):
        return calls[0].get("id")
    return payload.get("toolCallId")


def _tool_extract_parameters(payload: dict) -> dict:
    """
    Extrait les paramètres du tool-call depuis le payload Vapi.
    Vapi peut envoyer :
    - payload.parameters (legacy)
    - message.toolCallList[0].function.arguments (objet ou JSON string)
    - message.toolCalls[0].function.arguments (objet ou JSON string)
    """
    params = payload.get("parameters")
    if isinstance(params, dict) and params:
        return params

    msg = payload.get("message") or {}
    for key in ("toolCalls", "toolCallList"):
        calls = msg.get(key) or payload.get(key) or []
        if not calls or not isinstance(calls, list) or len(calls) == 0:
            continue
        first = calls[0]
        if not isinstance(first, dict):
            continue
        fn = first.get("function") or first.get("functionCall") or {}
        raw = fn.get("arguments")
        if raw is None:
            continue
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                continue
            try:
                return json.loads(raw)
            except Exception:
                pass
    return {}


@router.post("/tool")
async def vapi_tool(request: Request):
    """
    Endpoint pour Vapi function_tool (OpenAI direct + tool obligatoire).
    Actions : get_slots, book, cancel, modify, faq.
    Réponse Vapi : { "results": [ { "toolCallId", "result" | "error": string } ] }.
    """
    try:
        payload = await request.json()
        params = _tool_extract_parameters(payload)
        action = (params.get("action") or "").strip().lower()
        user_message = (params.get("user_message") or "").strip()
        patient_name = (params.get("patient_name") or "").strip() or None
        motif = (params.get("motif") or "").strip() or None
        preference = (params.get("preference") or "").strip() or None
        selected_slot = (params.get("selected_slot") or "").strip() or None
        exclude_start_iso = (params.get("exclude_start_iso") or "").strip() or None
        exclude_end_iso = (params.get("exclude_end_iso") or "").strip() or None

        call_id = _tool_extract_call_id(payload)
        tool_call_id = _tool_extract_tool_call_id(payload)

        logger.info(
            "TOOL_CALL",
            extra={"call_id": call_id[:24] if call_id else "", "action": action or "(legacy)", "tool_call_id": (tool_call_id or "")[:24]},
        )

        from backend.tenant_routing import (
            extract_to_number_from_vapi_payload,
            resolve_tenant_id_from_vocal_call,
            current_tenant_id,
        )
        from backend import vapi_tool_handlers as th

        to_number = extract_to_number_from_vapi_payload(payload)
        resolved_tenant_id, _ = resolve_tenant_id_from_vocal_call(to_number or "", channel="vocal")
        request.state.tenant_id = resolved_tenant_id
        current_tenant_id.set(str(resolved_tenant_id))

        def _get_session():
            return _get_or_resume_voice_session(resolved_tenant_id, call_id)

        # --- get_slots : créneaux 100% backend (Google Calendar) ---
        if action == "get_slots":
            session = _get_session()
            session.channel = "vocal"
            session.tenant_id = resolved_tenant_id
            if patient_name:
                session.qualif_data.name = patient_name
            if motif:
                session.qualif_data.motif = motif
            if preference:
                session.qualif_data.pref = preference
            slots_list, source, err = th.handle_get_slots(
                session, preference, call_id,
                exclude_start_iso=exclude_start_iso,
                exclude_end_iso=exclude_end_iso,
            )
            if hasattr(ENGINE.session_store, "save"):
                ENGINE.session_store.save(session)
            if err:
                return JSONResponse(
                    th.build_vapi_tool_response(tool_call_id, None, err),
                    status_code=200,
                )
            slots = slots_list or []
            if slots:
                if len(slots) == 1:
                    slots_text = slots[0]
                else:
                    slots_text = ", ".join(slots[:-1]) + " et " + slots[-1]
                result_text = f"Créneaux disponibles : {slots_text}."
            else:
                result_text = "Aucun créneau disponible pour le moment."
            return JSONResponse(
                th.build_vapi_tool_response(tool_call_id, result_text, None),
                status_code=200,
            )

        # --- book : réservation (payload JSON strict V3) ---
        if action == "book":
            session = _get_session()
            session.channel = "vocal"
            session.tenant_id = resolved_tenant_id
            payload, err = th.handle_book(session, selected_slot, patient_name, motif, call_id)
            if err:
                return JSONResponse(
                    th.build_vapi_tool_response(tool_call_id, None, err),
                    status_code=200,
                )
            try:
                if hasattr(ENGINE.session_store, "save"):
                    ENGINE.session_store.save(session)
            except Exception as save_err:
                logger.warning("Tool book: save session failed (booking already done): %s", save_err)
            result_str = json.dumps(payload or {}, ensure_ascii=False)
            logger.info("[VAPI_TOOL_RESPONSE] payload=%s result=%s", payload, result_str)
            body = th.build_vapi_tool_response(tool_call_id, result_str, None)
            return JSONResponse(body, status_code=200)

        # --- cancel / modify : déléguer à l'engine avec user_message ---
        if action in ("cancel", "modify"):
            text = user_message or ("Je souhaite annuler mon rendez-vous" if action == "cancel" else "Je souhaite modifier mon rendez-vous")
            session = _get_session()
            session.channel = "vocal"
            session.tenant_id = resolved_tenant_id
            events = _get_engine(call_id).handle_message(call_id, text)
            response_text = events[0].text if events else "Je n'ai pas compris."
            if tool_call_id:
                return JSONResponse(th.build_vapi_tool_response(tool_call_id, response_text, None), status_code=200)
            return JSONResponse({"result": response_text}, status_code=200)

        # --- faq ou legacy : message utilisateur → engine ---
        if not user_message and not action:
            return JSONResponse({"result": "Je n'ai pas compris. Pouvez-vous répéter ?"}, status_code=200)

        session = _get_session()
        session.channel = "vocal"
        session.tenant_id = resolved_tenant_id
        if session.state in ("TRANSFERRED", "CONFIRMED"):
            out = prompts.VOCAL_RESUME_ALREADY_TERMINATED
            if tool_call_id:
                return JSONResponse(th.build_vapi_tool_response(tool_call_id, out, None), status_code=200)
            return JSONResponse({"result": out}, status_code=200)

        message_to_use = user_message or ""
        if _pg_lock_ok():
            try:
                from backend.session_pg import pg_lock_call_session, LockTimeout
                _call_journal_ensure(resolved_tenant_id, call_id)
                with pg_lock_call_session(resolved_tenant_id, call_id, timeout_seconds=2):
                    session = _get_session()
                    session.channel = "vocal"
                    session.tenant_id = resolved_tenant_id
                    events = _get_engine(call_id).handle_message(call_id, message_to_use)
                    response_text = events[0].text if events else "Je n'ai pas compris"
                    if hasattr(ENGINE.session_store, "save"):
                        ENGINE.session_store.save(session)
                    if tool_call_id:
                        return JSONResponse(th.build_vapi_tool_response(tool_call_id, response_text, None), status_code=200)
                    return JSONResponse({"result": response_text}, status_code=200)
            except LockTimeout:
                logger.warning("[CALL_LOCK_TIMEOUT] tenant_id=%s call_id=%s", resolved_tenant_id, call_id[:20])
                fallback = "Un instant, s'il vous plaît."
                if tool_call_id:
                    return JSONResponse(th.build_vapi_tool_response(tool_call_id, fallback, None), status_code=200)
                return JSONResponse({"result": fallback}, status_code=200)
            except Exception as e:
                logger.warning("[CALL_LOCK_WARN] err=%s", e, exc_info=True)

        session = _get_session()
        session.channel = "vocal"
        session.tenant_id = resolved_tenant_id
        events = _get_engine(call_id).handle_message(call_id, message_to_use)
        response_text = events[0].text if events else "Je n'ai pas compris"
        if hasattr(ENGINE.session_store, "save"):
            ENGINE.session_store.save(session)
        if tool_call_id:
            return JSONResponse(th.build_vapi_tool_response(tool_call_id, response_text, None), status_code=200)
        return JSONResponse({"result": response_text}, status_code=200)

    except Exception as e:
        logger.exception("Tool error: %s", e)
        err_msg = "Désolé, une erreur est survenue."
        payload = locals().get("payload")
        tid = _tool_extract_tool_call_id(payload) if payload else None
        if tid:
            from backend import vapi_tool_handlers as th
            return JSONResponse(
                th.build_vapi_tool_response(tid, None, err_msg),
                status_code=200,
            )
        return JSONResponse({"result": err_msg}, status_code=200)


@router.get("/_health")
async def vapi_internal_health():
    """Health check dédié Vapi (vérifier déploiement)."""
    return {"status": "ok", "service": "vapi"}


@router.post("/chat/completions")
async def vapi_custom_llm(request: Request):
    """
    Vapi Custom LLM endpoint
    Vapi envoie les messages ici au lieu d'utiliser Claude/GPT
    Supporte le streaming (SSE) quand stream=true
    
    Intégrations:
    - Mémoire client (reconnaissance clients récurrents)
    - Stats pour rapports quotidiens
    """
    t_start = time.time()
    try:
        payload = await request.json()
        headers = request.headers

        # ✅ EXTRACTION STABLE call_id (ordre de priorité)
        call_id = None
        if payload.get("call") and payload["call"].get("id"):
            call_id = payload["call"]["id"]
        if not call_id:
            call_id = headers.get("x-vapi-call-id")
        if not call_id:
            call_id = payload.get("conversation_id")
        if not call_id:
            call_id = f"chat-{payload.get('id', 'unknown')}"

        _req_id = str(uuid.uuid4())[:8]
        _source = "body.call.id" if (payload.get("call") and payload["call"].get("id")) else ("header" if headers.get("x-vapi-call-id") else "conversation_id_or_fallback")
        logger.info("session_key_debug", extra={"call_id": call_id, "source": _source})
        logger.info("CHAT_HIT", extra={"call_id": call_id, "request_id": _req_id})
        t1 = log_timer("Payload parsed", t_start)

        print(f"🤖 CUSTOM LLM | session_key={call_id} | source={_source}")
        
        # Vapi envoie un tableau de messages (stream: true = SSE obligatoire côté backend)
        # ⚠️ NE JAMAIS ajouter pg_lock_call_session ici : Vapi envoie les tours séquentiellement,
        # un lock bloquerait le 2e tour → LockTimeout → greeting au lieu de la vraie réponse.
        messages = payload.get("messages", [])
        is_streaming = _parse_stream_flag(payload)
        logger.info(
            "[CHAT_COMPLETIONS_ENTER] NO_LOCK call_id=%s messages=%s stream=%s",
            call_id[:24] if call_id else "n/a", len(messages), is_streaming,
        )
        logger.info(
            "[CHAT_COMPLETIONS] call_id=%s messages_count=%s stream=%s",
            call_id[:24] if call_id else "n/a", len(messages), is_streaming,
        )
        
        # 📱 Reconnaissance du numéro : extraire le caller ID (Vapi) pour proposer "Votre numéro est bien le X ?"
        from backend.tenant_routing import (
            extract_to_number_from_vapi_payload,
            extract_customer_phone_from_vapi_payload,
            resolve_tenant_id_from_vocal_call,
        )
        customer_phone = extract_customer_phone_from_vapi_payload(payload)
        # Diagnostic : structure du payload (sans PII) pour savoir où Vapi envoie le caller ID
        _call = payload.get("call") or {}
        logger.info(
            "CUSTOMER_PHONE_RECOGNITION",
            extra={
                "call_id": call_id[:24] if call_id else "n/a",
                "has_number": bool(customer_phone),
                "payload_has_call": "call" in payload,
                "call_has_customer": "customer" in _call,
                "call_has_from": "from" in _call,
                "call_keys": list(_call.keys()) if _call else [],
            },
        )
        if not customer_phone:
            logger.debug("CUSTOMER_PHONE_MISSING call_id=%s (Vapi peut envoyer call.customer.number ou call.from)", call_id[:24] if call_id else "n/a")

        # 🎯 DID → tenant_id (avant tout event, pour scoping correct)
        to_number = extract_to_number_from_vapi_payload(payload)
        resolved_tenant_id, route_source = resolve_tenant_id_from_vocal_call(to_number, channel="vocal")
        logger.info(
            "[TENANT_ROUTE] to=%s tenant_id=%s source=%s",
            to_number or "(none)",
            resolved_tenant_id,
            route_source,
        )
        if config.ENABLE_TENANT_ROUTE_MISS_GUARD and to_number and route_source == "default":
            logger.warning("[TENANT_ROUTE_MISS] to=%s tenant_id=%s numéro non onboardé", to_number, resolved_tenant_id)

        print(f"📞 Call ID: {call_id} | Messages: {len(messages)} | Stream: {is_streaming}")
        if customer_phone:
            print(f"📱 Customer phone: {customer_phone}")
        
        # Récupère le dernier message utilisateur (content peut être string ou liste OpenAI)
        user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                raw = msg.get("content")
                if isinstance(raw, str):
                    user_message = raw
                elif isinstance(raw, list):
                    user_message = ""
                    for part in raw:
                        if isinstance(part, dict) and part.get("type") == "text":
                            user_message = part.get("text") or ""
                            break
                else:
                    user_message = str(raw) if raw is not None else ""
                break

        t2 = log_timer("Message extracted", t1)
        logger.info(
            "[CHAT_COMPLETIONS] user_message len=%s preview=%s",
            len(user_message or ""), (user_message or "")[:80],
        )
        logger.debug("user message: %r", (user_message or "")[:80])
        cancel_lookup_streaming = False
        if not user_message:
            # Premier message ou pas de message user (greeting) : persister le Caller ID dès maintenant
            # pour que les tours suivants aient session.customer_phone même si le payload ne le renvoie plus
            session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
            session.channel = "vocal"
            session.tenant_id = resolved_tenant_id
            if customer_phone:
                session.customer_phone = customer_phone
                logger.info("[CALLER_ID] conv_id=%s persisted_on_greeting", call_id[:24] if call_id else "n/a")
            if hasattr(ENGINE.session_store, "save"):
                ENGINE.session_store.save(session)
            display = get_tenant_display_config(resolved_tenant_id)
            response_text = prompts.get_vocal_greeting(display["business_name"])
        elif is_streaming:
            # Streaming : retour HTTP immédiat, premier token dans le corps < 1s. Pas de journal/DB avant return
            # (sinon Vapi ne reçoit pas la connexion à temps → silence). Journal fait dans _compute_voice_response_sync.
            t0 = t_start  # request reçue

            async def _stream_with_early_token():
                chunk_role = {
                    "id": f"chatcmpl-{call_id}",
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk_role)}\n\n"
                # Premier contenu immédiat (< 1s) pour éviter HANG Vapi (~5s)
                first_content = getattr(prompts, "VOCAL_HOLDING_FIRST_TOKEN", "Un instant.") or "Un instant."
                chunk_first = {
                    "id": f"chatcmpl-{call_id}",
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"content": first_content}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk_first)}\n\n"
                t1 = time.time()
                latency_first_token_ms = (t1 - t0) * 1000
                logger.info(
                    "LATENCY_FIRST_TOKEN_MS",
                    extra={
                        "call_id": call_id[:24] if call_id else "",
                        "t1_minus_t0_ms": round(latency_first_token_ms, 0),
                        "target_max_ms": 3000,
                    },
                )
                print(f"⏱️ First SSE content token: {latency_first_token_ms:.0f}ms (target <3000ms)")
                try:
                    response_text, cancel_lookup_streaming = await asyncio.to_thread(
                        _compute_voice_response_sync,
                        resolved_tenant_id,
                        call_id,
                        user_message,
                        customer_phone,
                        messages,
                    )
                except Exception as e:
                    logger.exception("_compute_voice_response_sync failed in stream: %s", e)
                    response_text = getattr(
                        prompts, "MSG_VOCAL_TECHNICAL_FALLBACK",
                        "Excusez-moi, un problème est survenu. Je vous transfère à un collègue.",
                    ) or "Excusez-moi, un problème est survenu."
                    cancel_lookup_streaming = False
                if cancel_lookup_streaming:
                    holding = getattr(prompts, "VOCAL_CANCEL_LOOKUP_HOLDING", "Je cherche votre rendez-vous...")
                    for i, word in enumerate(holding.split()):
                        content = f" {word}" if i > 0 else word
                        yield f"data: {json.dumps({'id': f'chatcmpl-{call_id}', 'object': 'chat.completion.chunk', 'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': None}]})}\n\n"
                    events = await asyncio.to_thread(_get_engine(call_id).handle_message, call_id, user_message)
                    session_after = ENGINE.session_store.get(call_id)
                    response_text = events[0].text if events else "Je n'ai pas compris"
                # Validation avant TTS (pare-feu) : si échec → fallback technical_transfer
                session_for_validation = ENGINE.session_store.get(call_id)
                state_after = getattr(session_for_validation, "state", "START")
                valid, text_to_stream = validate_response_tts(
                    state_after, response_text or "", channel="vocal"
                )
                response_text = text_to_stream if not valid else (response_text or "")
                words = (response_text or "").strip().split()
                for i, word in enumerate(words):
                    content = f" {word}" if i > 0 else word
                    yield f"data: {json.dumps({'id': f'chatcmpl-{call_id}', 'object': 'chat.completion.chunk', 'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': None}]})}\n\n"
                yield f"data: {json.dumps({'id': f'chatcmpl-{call_id}', 'object': 'chat.completion.chunk', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
                yield "data: [DONE]\n\n"
                t2 = time.time()
                total_ms = (t2 - t0) * 1000
                logger.info(
                    "LATENCY_STREAM_END_MS",
                    extra={"call_id": call_id[:24] if call_id else "", "t2_minus_t0_ms": round(total_ms, 0)},
                )
                print(f"✅ STREAMING END total: {total_ms:.0f}ms")

            total_ms = (time.time() - t_start) * 1000
            print(f"✅ STREAMING START (first token < 3s) latency: {total_ms:.0f}ms")
            return StreamingResponse(
                _stream_with_early_token(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            # Traiter via ENGINE (non-streaming)
            overlap_handled = False
            response_text = ""
            action_taken = ""

            # Phase 2: PG-first read — pas de lock sur /chat/completions.
            # Vapi envoie les tours de façon séquentielle (attend la réponse avant le tour suivant).
            # Un lock bloquait le 2e tour (LockTimeout → greeting au lieu de la vraie réponse).
            _call_journal_ensure(resolved_tenant_id, call_id)
            session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
            state_before_turn = getattr(session, "state", "START")

            session.channel = "vocal"
            session.tenant_id = resolved_tenant_id

            # Garde-fou Phase 2: session déjà terminée (CONFIRMED/TRANSFERRED) → ne pas rouvrir
            if session.state in ("TRANSFERRED", "CONFIRMED"):
                response_text = prompts.VOCAL_RESUME_ALREADY_TERMINATED
                action_taken = "resume_terminal_guard"
                overlap_handled = True

            # P0 Option B: dual-write journal PG (Phase 1)
            _call_journal_ensure(resolved_tenant_id, call_id, state_before_turn)
            _call_journal_user_message(resolved_tenant_id, call_id, user_message or "")

            # 🧠 Stocker le téléphone dans la session pour plus tard
            if customer_phone:
                session.customer_phone = customer_phone
            
            # 🔄 RECONSTRUCTION DE L'ÉTAT depuis l'historique des messages
            # NOTE: Avec SQLite, cette reconstruction ne devrait plus être nécessaire
            # On la garde en fallback si SQLite échoue
            # Guard: si on VA reconstruire ET qu'on a déjà reconstruit 1 fois → transfert (évite boucle)
            needs_reconstruct = session.state == "START" and len(messages) > 1 and not session.qualif_data.name
            reconstruct_count = getattr(session, "reconstruct_count", 0)
            last_user_content = next((m.get("content") or "" for m in reversed(messages) if m.get("role") == "user"), "")
            if needs_reconstruct and reconstruct_count >= 1:
                # Ne pas transférer si le message utilisateur ressemble à une demande de RDV
                if _looks_like_booking_request(last_user_content or user_message or ""):
                    logger.info("[SESSION_RECONSTRUCT] conv_id=%s booking-like message -> skip transfer, pass to engine", call_id)
                else:
                    logger.warning("[SESSION_RECONSTRUCT] conv_id=%s reconstruct_count=%s -> transfer", call_id, reconstruct_count)
                    session.state = "TRANSFERRED"
                    response_text = prompts.VOCAL_TRANSFER_COMPLEX
                    session.add_message("agent", response_text)
                    action_taken = "reconstruct_loop_guard"
                    overlap_handled = True  # skip engine processing
            elif needs_reconstruct:
                logger.debug("session in START with history but no data -> reconstruction")
                session = _reconstruct_session_from_history(session, messages, call_id=call_id)
                session.reconstruct_count = 1
            else:
                logger.debug("session loaded OK: state=%s name=%s", session.state, session.qualif_data.name)
            
            t3 = log_timer("Session loaded", t2)
            
            # 🧠 Check si client récurrent (avant le premier message traité)
            if customer_phone:
                try:
                    existing_client = client_memory.get_by_phone(customer_phone, tenant_id=getattr(session, "tenant_id", None))
                    if existing_client:
                        session.client_id = existing_client.id  # pour ivr_events / rapport quotidien
                        if existing_client.total_bookings > 0:
                            greeting = client_memory.get_personalized_greeting(existing_client, channel="vocal")
                            if greeting:
                                logger.debug("returning client detected: %s", existing_client.name)
                except Exception as e:
                    logger.debug("client memory error: %s", e)

            # Input firewall (text-only) : SILENCE / UNCLEAR / TEXT — avant tout traitement
            kind, normalized = classify_text_only(user_message or "")
            # Ne pas traiter "Je voudrais un rendez-vous" comme UNCLEAR → passer à l'engine (flow RDV)
            if kind == "UNCLEAR" and _looks_like_booking_request(user_message or ""):
                kind, normalized = "TEXT", (normalized or normalize_transcript(user_message or ""))
            unclear_count = getattr(session, "unclear_text_count", 0)
            logger.info(
                "decision_in",
                extra={
                    "call_id": call_id,
                    "state_before": session.state,
                    "kind": kind,
                    "raw_len": len((user_message or "")),
                    "normalized_len": len(normalized or ""),
                    "unclear_count": unclear_count,
                },
            )
            logger.info(
                "decision_in_chat",
                extra={
                    "call_id": call_id,
                    "state_before": session.state,
                    "turn_count": getattr(session, "turn_count", 0),
                },
            )

            # Semi-sourd : overlap guard (UNCLEAR/SILENCE pendant TTS = ignoré ; mots critiques passent)
            # Ne pas réinitialiser si déjà géré (reconstruct_loop_guard, resume_terminal_guard)
            if action_taken not in ("reconstruct_loop_guard", "resume_terminal_guard"):
                overlap_handled = False
                response_text = ""
                action_taken = ""
                if _is_agent_speaking(session):
                    # Interruption pendant énonciation des créneaux (WAIT_CONFIRM) : "un", "1", "deux" = choix valide
                    if session.state == "WAIT_CONFIRM" and is_critical_token(normalized):
                        overlap_handled = False
                    elif is_critical_overlap(user_message or ""):
                        logger.info(
                            "critical_overlap_allowed",
                            extra={"call_id": call_id, "text_len": len((user_message or "")[:20])},
                        )
                    elif kind in ("UNCLEAR", "SILENCE"):
                        response_text = prompts.MSG_VOCAL_CROSSTALK_ACK
                        action_taken = "overlap_ignored"
                        overlap_handled = True
                        logger.info(
                            "overlap_ignored",
                            extra={"call_id": call_id, "classification": kind, "reason": "agent_speaking"},
                        )
                    elif kind == "TEXT" and len((user_message or "").strip()) < 10:
                        response_text = getattr(
                            prompts, "MSG_OVERLAP_REPEAT_SHORT", "Pardon, pouvez-vous répéter ?"
                        )
                        session.add_message("agent", response_text)
                        action_taken = "overlap_repeat"
                        overlap_handled = True
                        logger.info(
                            "overlap_repeat",
                            extra={"call_id": call_id, "text_len": len((user_message or "").strip())},
                        )

            # En annulation : si on va chercher le RDV par nom, envoyer d'abord un message de tenue
            # en stream pour éviter le "mmm" TTS pendant la latence (recherche Google Calendar).
            cancel_lookup_streaming = (
                is_streaming
                and session.state == "CANCEL_NAME"
                and _looks_like_name_for_cancel(user_message)
            )
            if cancel_lookup_streaming:
                response_text = ""
            else:
                if not overlap_handled:
                    try:
                        if kind == "SILENCE":
                            events = _get_engine(call_id).handle_message(call_id, "")
                            response_text = events[0].text if events else prompts.MSG_EMPTY_MESSAGE
                            action_taken = "silence"
                            _maybe_reset_noise_on_terminal(session, events or [])
                        elif kind == "TEXT":
                            events = _get_engine(call_id).handle_message(call_id, normalized)
                            response_text = events[0].text if events else "Je n'ai pas compris"
                            action_taken = "text"
                            _maybe_reset_noise_on_terminal(session, events or [])
                        else:  # UNCLEAR — overlap guard puis crosstalk : ne pas compter overlap comme échec
                            now = time.time()
                            last_reply_ts = getattr(session, "last_agent_reply_ts", 0) or 0
                            overlap_window = getattr(config, "OVERLAP_WINDOW_SEC", 1.2)
                            recent_agent = (now - last_reply_ts) < overlap_window
                            if recent_agent:
                                response_text = getattr(
                                    prompts, "MSG_OVERLAP_REPEAT", "Je vous ai entendu en même temps. Pouvez-vous répéter maintenant ?"
                                )
                                session.add_message("agent", response_text)
                                action_taken = "overlap_guard"
                            else:
                                raw_len = len((user_message or ""))
                                last_ts = getattr(session, "last_assistant_ts", 0) or 0
                                within_crosstalk_window = (now - last_ts) < getattr(
                                    config, "CROSSTALK_WINDOW_SEC", 5.0
                                )
                                max_crosstalk_len = getattr(config, "CROSSTALK_MAX_RAW_LEN", 40)
                                if within_crosstalk_window and raw_len <= max_crosstalk_len:
                                    response_text = prompts.MSG_VOCAL_CROSSTALK_ACK
                                    action_taken = "ignore_crosstalk"
                                else:
                                    session.unclear_text_count = getattr(session, "unclear_text_count", 0) + 1
                                    count = session.unclear_text_count
                                    if count == 1:
                                        response_text = prompts.MSG_UNCLEAR_1
                                        session.add_message("agent", response_text)
                                        action_taken = "unclear_1"
                                    elif count == 2:
                                        events = ENGINE._trigger_intent_router(
                                            session, "unclear_text_2", user_message or ""
                                        )
                                        response_text = events[0].text if events else prompts.MSG_UNCLEAR_1
                                        action_taken = "unclear_2_intent_router"
                                    else:
                                        state_before = getattr(session, "state", "START")
                                        session.state = "TRANSFERRED"
                                        response_text = (
                                            prompts.VOCAL_TRANSFER_COMPLEX
                                            if getattr(session, "channel", "") == "vocal"
                                            else prompts.MSG_TRANSFER
                                        )
                                        session.add_message("agent", response_text)
                                        action_taken = "unclear_3_transfer"
                                        logger.info(
                                            "DECISION_TRACE state_before=%s intent_detected=n/a guard_triggered=unclear_3_transfer state_after=TRANSFERRED text=%r",
                                            state_before,
                                            (user_message or "")[:200],
                                            extra={
                                                "call_id": call_id[:24] if call_id else "",
                                                "state_before": state_before,
                                                "guard_triggered": "unclear_3_transfer",
                                                "state_after": "TRANSFERRED",
                                            },
                                        )
                    except Exception as e:
                        print(f"❌ ENGINE ERROR: {e}")
                        import traceback
                        traceback.print_exc()
                        response_text = "Excusez-moi, j'ai un petit souci technique. Je vous transfère à un collègue."
                t4 = log_timer("ENGINE processed", t3)
                _log_decision_out(call_id, session, action_taken, response_text)
                if hasattr(ENGINE.session_store, "save"):
                    ENGINE.session_store.save(session)
                # P0 Option B: dual-write — message agent + checkpoint
                state_after = getattr(session, "state", "START")
                # Checkpoint sur: changement état, pending_slots, awaiting_confirmation, états critiques
                should_cp = (
                    state_before_turn != state_after
                    or bool(getattr(session, "pending_slots", None))
                    or getattr(session, "awaiting_confirmation", None) is not None
                    or state_after in ("QUALIF_CONTACT", "WAIT_CONFIRM", "CONTACT_CONFIRM", "CONTACT_CONFIRM_CALLERID")
                )
                _call_journal_agent_response(
                    resolved_tenant_id,
                    call_id,
                    session,
                    response_text,
                    state_before_turn,
                    should_checkpoint=should_cp,
                )
                logger.info(
                    "decision_out_chat",
                    extra={"call_id": call_id, "state_after": getattr(session, "state", "")},
                )
            if not cancel_lookup_streaming:
                print(f"✅ Response: '{response_text[:50]}...' ({len(response_text)} chars)")
                session.last_assistant_ts = time.time()
                session.last_agent_reply_ts = time.time()
                if response_text and response_text.strip():
                    tts_duration = estimate_tts_duration(response_text)
                    session.speaking_until_ts = time.time() + tts_duration
                    logger.info(
                        "agent_speaking",
                        extra={
                            "call_id": call_id,
                            "tts_duration": round(tts_duration, 2),
                            "speaking_until_ts": session.speaking_until_ts,
                        },
                    )
            
            # 📊 Enregistrer stats pour rapport (si conversation terminée) — pas en cancel_lookup_streaming (fait dans le stream)
            if not cancel_lookup_streaming:
                try:
                    if session.state in ["CONFIRMED", "TRANSFERRED"]:
                        intent = "BOOKING" if session.state == "CONFIRMED" else "TRANSFER"
                        outcome = "confirmed" if session.state == "CONFIRMED" else "transferred"
                        duration_ms = int((time.time() - t_start) * 1000)
                        report_generator.record_interaction(
                            call_id=call_id,
                            intent=intent,
                            outcome=outcome,
                            channel="vocal",
                            duration_ms=duration_ms,
                            motif=session.qualif_data.motif if hasattr(session, 'qualif_data') else None,
                            client_name=session.qualif_data.name if hasattr(session, 'qualif_data') else None,
                            client_phone=customer_phone
                        )
                        print(f"📊 Stats recorded: {intent} → {outcome}")
                        if session.state == "CONFIRMED" and session.qualif_data.name:
                            try:
                                client = client_memory.get_or_create(
                                    phone=customer_phone,
                                    name=session.qualif_data.name,
                                    email=session.qualif_data.contact if session.qualif_data.contact_type == "email" else None,
                                    tenant_id=getattr(session, "tenant_id", None),
                                )
                                slot_label = tools_booking.get_label_for_choice(session, session.pending_slot_choice or 1) or "RDV"
                                client_memory.record_booking(
                                    client_id=client.id,
                                    slot_label=slot_label,
                                    motif=session.qualif_data.motif or "consultation",
                                    tenant_id=getattr(session, "tenant_id", None),
                                )
                                print(f"🧠 Client saved: {client.name} (id={client.id})")
                            except Exception as e:
                                print(f"⚠️ Client save error: {e}")
                except Exception as e:
                    print(f"⚠️ Stats recording error: {e}")
        
        # ⏱️ TIMING TOTAL
        total_ms = (time.time() - t_start) * 1000
        print(f"✅ TOTAL LATENCY: {total_ms:.0f}ms")
        
        # Si streaming demandé, retourner SSE
        if is_streaming:
            async def generate_stream():
                import asyncio
                
                chunk_role = {
                    "id": f"chatcmpl-{call_id}",
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]
                }
                yield f"data: {json.dumps(chunk_role)}\n\n"
                
                stream_response_text = response_text
                if cancel_lookup_streaming:
                    # Envoyer d'abord le message de tenue pour éviter le "mmm" pendant la recherche du RDV
                    holding = prompts.VOCAL_CANCEL_LOOKUP_HOLDING
                    for i, word in enumerate(holding.split()):
                        content = f" {word}" if i > 0 else word
                        chunk = {
                            "id": f"chatcmpl-{call_id}",
                            "object": "chat.completion.chunk",
                            "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
                    # Recherche du RDV (bloquant → en thread)
                    events = await asyncio.to_thread(_get_engine(call_id).handle_message, call_id, user_message)
                    session_after = ENGINE.session_store.get(call_id)
                    stream_response_text = events[0].text if events else "Je n'ai pas compris"
                    # Stats (même logique qu'en non-streaming)
                    if session_after and session_after.state in ["CONFIRMED", "TRANSFERRED"]:
                        try:
                            intent = "BOOKING" if session_after.state == "CONFIRMED" else "TRANSFER"
                            outcome = "confirmed" if session_after.state == "CONFIRMED" else "transferred"
                            report_generator.record_interaction(
                                call_id=call_id, intent=intent, outcome=outcome, channel="vocal",
                                duration_ms=int((time.time() - t_start) * 1000),
                                motif=getattr(session_after.qualif_data, "motif", None),
                                client_name=getattr(session_after.qualif_data, "name", None),
                                client_phone=customer_phone
                            )
                            if session_after.state == "CONFIRMED" and session_after.qualif_data.name:
                                client = client_memory.get_or_create(
                                    phone=customer_phone,
                                    name=session_after.qualif_data.name,
                                    email=session_after.qualif_data.contact if getattr(session_after.qualif_data, "contact_type", None) == "email" else None,
                                    tenant_id=getattr(session_after, "tenant_id", None),
                                )
                                slot_label = tools_booking.get_label_for_choice(session_after, session_after.pending_slot_choice or 1) or "RDV"
                                client_memory.record_booking(
                                    client_id=client.id,
                                    slot_label=slot_label,
                                    motif=session_after.qualif_data.motif or "consultation",
                                    tenant_id=getattr(session_after, "tenant_id", None),
                                )
                        except Exception:
                            pass
                
                # Envoyer le contenu (réponse réelle) mot par mot
                words = stream_response_text.split()
                for i, word in enumerate(words):
                    content = f" {word}" if i > 0 else word
                    chunk = {
                        "id": f"chatcmpl-{call_id}",
                        "object": "chat.completion.chunk",
                        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                
                chunk_final = {
                    "id": f"chatcmpl-{call_id}",
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(chunk_final)}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            )
        
        # Format OpenAI-compatible (non-streaming), compatibilité max + Content-Type strict
        return _make_chat_response(call_id, response_text, is_streaming)

    except Exception as e:
        print(f"❌ Custom LLM error: {e}")
        import traceback
        traceback.print_exc()
        try:
            _err_cid = (payload.get("call") or {}).get("id") or "unknown"
        except NameError:
            _err_cid = "unknown"
        try:
            _err_stream = _parse_stream_flag(payload)
        except Exception:
            _err_stream = False
        logger.warning(
            "[CHAT_COMPLETIONS] exception call_id=%s stream=%s err=%s",
            _err_cid[:24] if _err_cid else "n/a", _err_stream, str(e),
        )
        _err_msg = "Désolé, une erreur est survenue."
        return _make_chat_response(_err_cid, _err_msg, _err_stream)


@router.get("/health")
async def vapi_health():
    return {"status": "ok", "service": "voice"}


@router.get("/test")
async def vapi_test():
    try:
        events = _get_engine("test").handle_message("test", "bonjour")
        if events:
            return {"status": "ok", "response": events[0].text}
        return {"status": "error"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
