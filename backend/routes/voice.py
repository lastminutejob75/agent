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
from backend.client_memory import get_client_memory
from backend.session_codec import session_to_dict
from backend.conversational_engine import ConversationalEngine, _is_canary
from backend.reports import get_report_generator
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
        if detected_state == "CONTACT_CONFIRM" and session.pending_slot_choice and not (getattr(session, "pending_slots", None) or []):
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


@router.post("/webhook")
async def vapi_webhook(request: Request):
    """
    Webhook Vapi — Option A : 200 immédiat, zéro traitement.
    Évite la saturation du worker Railway : pas de request.json(), pas de log, pas de DB.
    Les events Vapi sont fire-and-forget ; le flux conversationnel passe par /chat/completions.
    """
    return Response(status_code=200)


@router.post("/tool")
async def vapi_tool(request: Request):
    """
    Endpoint pour Vapi Tools/Functions.
    Claude appelle ce tool pour obtenir les réponses.
    """
    try:
        payload = await request.json()

        print(f"🔧🔧🔧 TOOL APPELÉ 🔧🔧🔧")
        print(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

        # Extraire le message utilisateur
        user_message = payload.get("parameters", {}).get("user_message", "")
        call_id = payload.get("call", {}).get("id", "unknown")

        print(f"📝 User message: '{user_message}'")
        print(f"📞 Call ID: {call_id}")

        if not user_message:
            return {"result": "Je n'ai pas compris. Pouvez-vous répéter ?"}

        # DID → tenant_id (tool utilise same payload)
        from backend.tenant_routing import (
            extract_to_number_from_vapi_payload,
            resolve_tenant_id_from_vocal_call,
        )
        to_number = extract_to_number_from_vapi_payload(payload)
        resolved_tenant_id, _ = resolve_tenant_id_from_vocal_call(to_number, channel="vocal")

        # Phase 2.1: lock PG anti webhooks simultanés
        if _pg_lock_ok():
            try:
                from backend.session_pg import pg_lock_call_session, LockTimeout
                _call_journal_ensure(resolved_tenant_id, call_id)
                with pg_lock_call_session(resolved_tenant_id, call_id, timeout_seconds=2):
                    session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
                    session.channel = "vocal"
                    session.tenant_id = resolved_tenant_id
                    if session.state in ("TRANSFERRED", "CONFIRMED"):
                        return {"result": prompts.VOCAL_RESUME_ALREADY_TERMINATED}
                    events = _get_engine(call_id).handle_message(call_id, user_message)
                    response_text = events[0].text if events else "Je n'ai pas compris"
                    print(f"✅ Tool response: '{response_text}'")
                    return {"result": response_text}
            except LockTimeout:
                logger.warning("[CALL_LOCK_TIMEOUT] tenant_id=%s call_id=%s -> fallback result (évite 204)", resolved_tenant_id, call_id[:20])
                try:
                    from backend.engine import _persist_ivr_event
                    _persist_ivr_event(
                        ENGINE.session_store.get_or_create(call_id),
                        "call_lock_timeout",
                        reason="concurrent_webhook",
                    )
                except Exception:
                    pass
                # Ne jamais renvoyer 204 à Vapi sur /tool → silence.
                return JSONResponse({"result": "Un instant, s'il vous plaît."}, status_code=200)
            except Exception as e:
                logger.warning("[CALL_LOCK_WARN] err=%s", e, exc_info=True)
                pass

        session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
        session.channel = "vocal"
        session.tenant_id = resolved_tenant_id
        if session.state in ("TRANSFERRED", "CONFIRMED"):
            return {"result": prompts.VOCAL_RESUME_ALREADY_TERMINATED}
        events = _get_engine(call_id).handle_message(call_id, user_message)
        response_text = events[0].text if events else "Je n'ai pas compris"
        print(f"✅ Tool response: '{response_text}'")
        return {"result": response_text}
        
    except Exception as e:
        print(f"❌ Tool error: {e}")
        import traceback
        traceback.print_exc()
        return {"result": "Désolé, une erreur est survenue."}


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
        messages = payload.get("messages", [])
        is_streaming = _parse_stream_flag(payload)
        logger.info(
            "[CHAT_COMPLETIONS] call_id=%s messages_count=%s stream=%s",
            call_id[:24] if call_id else "n/a", len(messages), is_streaming,
        )
        
        # 📱 Extraire le numéro de téléphone du client (Vapi le fournit)
        customer_phone = payload.get("call", {}).get("customer", {}).get("number")
        if not customer_phone:
            customer_phone = payload.get("customer", {}).get("number")

        # 🎯 DID → tenant_id (avant tout event, pour scoping correct)
        from backend.tenant_routing import (
            extract_to_number_from_vapi_payload,
            resolve_tenant_id_from_vocal_call,
        )
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
        
        if not user_message:
            # Premier message ou pas de message user
            response_text = prompts.get_vocal_greeting(config.BUSINESS_NAME)
        else:
            # Traiter via ENGINE
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
            if needs_reconstruct and reconstruct_count >= 1:
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
                    existing_client = client_memory.get_by_phone(customer_phone)
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
                                        session.state = "TRANSFERRED"
                                        response_text = (
                                            prompts.VOCAL_TRANSFER_COMPLEX
                                            if getattr(session, "channel", "") == "vocal"
                                            else prompts.MSG_TRANSFER
                                        )
                                        session.add_message("agent", response_text)
                                        action_taken = "unclear_3_transfer"
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
                    or state_after in ("QUALIF_CONTACT", "WAIT_CONFIRM", "CONTACT_CONFIRM")
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
                                    email=session.qualif_data.contact if session.qualif_data.contact_type == "email" else None
                                )
                                slot_label = tools_booking.get_label_for_choice(session, session.pending_slot_choice or 1) or "RDV"
                                client_memory.record_booking(
                                    client_id=client.id,
                                    slot_label=slot_label,
                                    motif=session.qualif_data.motif or "consultation"
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
                                    email=session_after.qualif_data.contact if getattr(session_after.qualif_data, "contact_type", None) == "email" else None
                                )
                                slot_label = tools_booking.get_label_for_choice(session_after, session_after.pending_slot_choice or 1) or "RDV"
                                client_memory.record_booking(client_id=client.id, slot_label=slot_label, motif=session_after.qualif_data.motif or "consultation")
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
