# backend/routes/voice.py
"""
Route pour le canal Voix (Vapi) - DEBUG COMPLET + TIMERS
Avec mémoire client et stats pour rapports.
"""

from fastapi import APIRouter, Request
from fastapi.responses import Response, JSONResponse
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


def _vapi_content_response(call_id: str, response_text: str, debug_trace: Optional[str] = None):
    """
    Réponse JSON explicite pour Vapi : strip/fallback, log [VAPI_OUT], Content-Type application/json.
    """
    text = (response_text or "").strip()
    if not text:
        text = "Pouvez-vous répéter, s'il vous plaît ?"
    payload = {"content": text}
    if debug_trace:
        payload["_debug"] = debug_trace
    logger.info(
        "[VAPI_OUT] status=200 content_type=application/json content_len=%s call_id=%s",
        len(text), call_id[:20] if call_id else "n/a",
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
    Webhook Vapi - DEBUG COMPLET + TIMERS
    Nova-2-phonecall : ignore partial, distingue NOISE vs SILENCE, normalise fillers.
    """
    t_start = time.time()
    try:
        payload = await request.json()
        _call_id = (payload.get("call") or {}).get("id") or "unknown"
        logger.info("WEBHOOK_HIT", extra={"call_id": _call_id})
        t1 = log_timer("Payload parsed", t_start)

        message = payload.get("message") or {}
        message_type = message.get("type") or "NO_TYPE"
        message_role = message.get("role")
        call_id = (payload.get("call") or {}).get("id") or "unknown"
        raw_text_for_log = message.get("transcript") or message.get("content") or message.get("text") or ""

        # [VAPI_IN] un seul endroit en haut (tenant résolu pour diagnostic call_id/tenant mismatch)
        from backend.tenant_routing import extract_to_number_from_vapi_payload, resolve_tenant_id_from_vocal_call
        _to_number = extract_to_number_from_vapi_payload(payload)
        _resolved_tenant_id, _ = resolve_tenant_id_from_vocal_call(_to_number or "", channel="vocal")
        logger.info(
            "[VAPI_IN] type=%s role=%s call_id=%s tenant=%s text_len=%s",
            message_type, message_role, call_id[:20] if call_id else "n/a", _resolved_tenant_id, len(raw_text_for_log or ""),
        )

        # assistant-request AVANT la garde message_role (Vapi envoie role != user → sinon on renvoyait 204 et "plus rien")
        if message_type == "assistant-request":
            try:
                to_number = extract_to_number_from_vapi_payload(payload)
                resolved_tenant_id, _ = resolve_tenant_id_from_vocal_call(to_number or "", channel="vocal")
                session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
                last_agent_len = len(getattr(session, "last_agent_message", "") or "")
                last_q_len = len(getattr(session, "last_question_asked", "") or "")
                logger.info(
                    "[ASSISTANT_REQUEST] call_id=%s tenant=%s last_agent_len=%s last_q_len=%s state=%s",
                    call_id[:20] if call_id else "n/a", resolved_tenant_id, last_agent_len, last_q_len, getattr(session, "state", None),
                )
                last = getattr(session, "last_agent_message", None) or getattr(session, "last_question_asked", None)
                if last and str(last).strip():
                    logger.info("[VAPI] assistant-request -> last_agent_message (len=%s)", len(last))
                    return _vapi_content_response(call_id, last.strip(), debug_trace=f"assistant-request|last|{call_id[:8]}")
                # START sans contenu → greeting complet (évite silence au début d'appel)
                greeting = prompts.get_vocal_greeting(config.BUSINESS_NAME)
                session.last_agent_message = greeting
                session.add_message("agent", greeting)
                if hasattr(ENGINE.session_store, "save"):
                    ENGINE.session_store.save(session)
                    logger.info("[SESSION_SAVED] call_id=%s state=%s last_agent_len=%s", call_id[:20], getattr(session, "state", ""), len(session.last_agent_message or ""))
                logger.info("[VAPI] assistant-request -> greeting (START)")
                return _vapi_content_response(call_id, greeting, debug_trace=f"assistant-request|greeting|{call_id[:8]}")
            except Exception as e:
                logger.warning("[VAPI] assistant-request fallback: %s", e)
            logger.info("[VAPI] assistant-request -> fallback (no session/last)")
            return _vapi_content_response(call_id, prompts.get_vocal_greeting(config.BUSINESS_NAME), debug_trace=f"assistant-request|fallback|{call_id[:8]}")

        # Garde : ne traiter que les messages user (transcripts utilisateur)
        # En START, ne pas renvoyer 204 → renvoyer le greeting pour éviter silence au début d'appel
        if message_role is not None and message_role != "user":
            try:
                to_number = extract_to_number_from_vapi_payload(payload)
                resolved_tenant_id, _ = resolve_tenant_id_from_vocal_call(to_number or "", channel="vocal")
                session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
                if session.state == "START":
                    last = getattr(session, "last_agent_message", None) or getattr(session, "last_question_asked", None)
                    if not (last and str(last).strip()):
                        greeting = prompts.get_vocal_greeting(config.BUSINESS_NAME)
                        session.last_agent_message = greeting
                        session.add_message("agent", greeting)
                        if hasattr(ENGINE.session_store, "save"):
                            ENGINE.session_store.save(session)
                            logger.info("[SESSION_SAVED] call_id=%s state=%s last_agent_len=%s", call_id[:20], getattr(session, "state", ""), len(session.last_agent_message or ""))
                        logger.info("[VAPI] non_user_message in START -> greeting (evite silence)")
                        return _vapi_content_response(call_id, greeting)
            except Exception as e:
                logger.debug("[VAPI] non_user_message session check: %s", e)
            logger.warning(
                "non_user_message",
                extra={"role": message_role, "type": message_type, "call_id": call_id},
            )
            return Response(status_code=204)

        # P0-2 : fallback multi-champs pour transcriptType (certains providers envoient type / isFinal)
        _tt = message.get("transcriptType") or message.get("transcript_type")
        if _tt is None and message.get("type"):
            _t = (message.get("type") or "").lower()
            _tt = "partial" if "partial" in _t else ("final" if "final" in _t else None)
        if _tt is None and "isFinal" in message:
            _tt = "final" if message.get("isFinal") else "partial"
        if _tt is None and "final" in message:
            _tt = "final" if message.get("final") else "partial"
        transcript_type = (_tt or "final").lower()
        raw_text = message.get("transcript") or message.get("content") or message.get("text") or ""
        confidence = message.get("confidence")
        if confidence is not None and not isinstance(confidence, (int, float)):
            confidence = None

        logger.debug("webhook type=%s transcriptType=%s call_id=%s", message_type, transcript_type, call_id)

        # DID → tenant_id (avant tout event)
        from backend.tenant_routing import (
            extract_to_number_from_vapi_payload,
            resolve_tenant_id_from_vocal_call,
        )
        to_number = extract_to_number_from_vapi_payload(payload)
        resolved_tenant_id, route_source = resolve_tenant_id_from_vocal_call(to_number, channel="vocal")
        logger.info("[TENANT_ROUTE] to=%s tenant_id=%s source=%s", to_number or "(none)", resolved_tenant_id, route_source)

        # Garde-fou : numéro présent mais non routé → log (transfert via ENABLE_TENANT_ROUTE_MISS_GUARD si besoin)
        if config.ENABLE_TENANT_ROUTE_MISS_GUARD and to_number and route_source == "default":
            logger.warning("[TENANT_ROUTE_MISS] to=%s tenant_id=%s numéro non onboardé", to_number, resolved_tenant_id)
            # TODO: transfert immédiat via tool/response si souhaité

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
                        return _vapi_content_response(call_id, prompts.VOCAL_RESUME_ALREADY_TERMINATED)

                    if transcript_type == "partial":
                        logger.debug("partial transcript, skipping")
                        _norm_len = len(normalize_transcript(raw_text or ""))
                        logger.info("decision_in", extra={"call_id": call_id, "state_before": getattr(session, "state", ""), "transcript_type": transcript_type or "unknown", "confidence": confidence, "raw_len": len(raw_text or ""), "normalized_len": _norm_len, "stt_class": "PARTIAL", "noise_count": getattr(session, "noise_detected_count", 0), "empty_count": getattr(session, "empty_message_count", 0), "turn_count": getattr(session, "turn_count", 0)})
                        _log_decision_out(call_id, session, "http_204", "")
                        return Response(status_code=204)

                    t2 = log_timer("Message extracted", t1)
                    kind, text_to_use = _classify_stt_input(raw_text, confidence, transcript_type, message_type=message_type)
                    normalized = normalize_transcript(raw_text or "")
                    logger.info("decision_in", extra={"call_id": call_id, "state_before": getattr(session, "state", ""), "transcript_type": transcript_type or "unknown", "confidence": confidence, "raw_len": len(raw_text or ""), "normalized_len": len(normalized or ""), "stt_class": kind, "noise_count": getattr(session, "noise_detected_count", 0), "empty_count": getattr(session, "empty_message_count", 0), "turn_count": getattr(session, "turn_count", 0)})

                    if kind == "NOISE":
                        events = ENGINE.handle_noise(session)
                        if not events:
                            _log_decision_out(call_id, session, "http_204", "")
                            return Response(status_code=204)
                        if hasattr(ENGINE.session_store, "save"):
                            ENGINE.session_store.save(session)
                            logger.info("[SESSION_SAVED] call_id=%s state=%s last_agent_len=%s", call_id[:20], getattr(session, "state", ""), len(getattr(session, "last_agent_message", "") or ""))
                        reply_text = events[0].text
                        _action = "reply"
                        if getattr(session, "state", "") == "INTENT_ROUTER": _action = "router"
                        elif getattr(session, "state", "") == "TRANSFERRED": _action = "transfer"
                        elif getattr(session, "state", "") == "CONFIRMED": _action = "confirmed"
                        _log_decision_out(call_id, session, _action, reply_text)
                        return _vapi_content_response(call_id, reply_text)

                    if kind == "SILENCE":
                        events = _get_engine(call_id).handle_message(call_id, "")
                        _maybe_reset_noise_on_terminal(session, events)
                        if hasattr(ENGINE.session_store, "save"):
                            ENGINE.session_store.save(session)
                            logger.info("[SESSION_SAVED] call_id=%s state=%s last_agent_len=%s", call_id[:20], getattr(session, "state", ""), len(getattr(session, "last_agent_message", "") or ""))
                        response_text = events[0].text if events else "Je n'ai pas compris"
                        _action = "reply"
                        if "INTENT_ROUTER" in getattr(session, "state", ""): _action = "router"
                        elif getattr(session, "state", "") == "TRANSFERRED": _action = "transfer"
                        elif getattr(session, "state", "") == "CONFIRMED": _action = "confirmed"
                        _log_decision_out(call_id, session, _action, response_text)
                        return _vapi_content_response(call_id, response_text)

                    if text_to_use and text_to_use.strip():
                        from backend.tenant_config import get_consent_mode
                        if not getattr(session, "_consent_obtained_persisted", False) and get_consent_mode(getattr(session, "tenant_id", None)) == "implicit":
                            try:
                                from backend.engine import persist_consent_obtained
                                persist_consent_obtained(session, channel="vocal")
                                session._consent_obtained_persisted = True
                            except Exception:
                                pass
                        events = _get_engine(call_id).handle_message(call_id, text_to_use)
                        _maybe_reset_noise_on_terminal(session, events)
                        if hasattr(ENGINE.session_store, "save"):
                            ENGINE.session_store.save(session)
                            logger.info("[SESSION_SAVED] call_id=%s state=%s last_agent_len=%s", call_id[:20], getattr(session, "state", ""), len(getattr(session, "last_agent_message", "") or ""))
                        response_text = events[0].text if events else "Je n'ai pas compris"
                        _action = "reply"
                        if "INTENT_ROUTER" in getattr(session, "state", ""): _action = "router"
                        elif getattr(session, "state", "") == "TRANSFERRED": _action = "transfer"
                        elif getattr(session, "state", "") == "CONFIRMED": _action = "confirmed"
                        _log_decision_out(call_id, session, _action, response_text)
                        return _vapi_content_response(call_id, response_text)

                    # Pas de texte utilisable → traiter comme silence (évite "plus ne se passe" après accueil)
                    events = _get_engine(call_id).handle_message(call_id, "")
                    _maybe_reset_noise_on_terminal(session, events)
                    if hasattr(ENGINE.session_store, "save"):
                        ENGINE.session_store.save(session)
                        logger.info("[SESSION_SAVED] call_id=%s state=%s last_agent_len=%s", call_id[:20], getattr(session, "state", ""), len(getattr(session, "last_agent_message", "") or ""))
                    response_text = events[0].text if events else "Je n'ai pas bien compris. Pouvez-vous répéter ?"
                    _log_decision_out(call_id, session, "reply", response_text)
                    return _vapi_content_response(call_id, response_text)
            except LockTimeout:
                logger.warning("[CALL_LOCK_TIMEOUT] tenant_id=%s call_id=%s", resolved_tenant_id, call_id[:20])
                try:
                    from backend.engine import _persist_ivr_event
                    _persist_ivr_event(
                        ENGINE.session_store.get_or_create(call_id),
                        "call_lock_timeout",
                        reason="concurrent_webhook",
                    )
                except Exception:
                    pass
                return Response(status_code=204)
            except Exception as e:
                logger.warning("[CALL_LOCK_WARN] err=%s", e, exc_info=True)
                session = ENGINE.session_store.get_or_create(call_id)
                session.channel = "vocal"
                session.tenant_id = resolved_tenant_id
        else:
            session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
            session.channel = "vocal"
            session.tenant_id = resolved_tenant_id

        # Garde-fou Phase 2: session déjà terminée → ne pas rouvrir
        if session.state in ("TRANSFERRED", "CONFIRMED"):
            return _vapi_content_response(call_id, prompts.VOCAL_RESUME_ALREADY_TERMINATED)

        # Partial => HTTP 204 No Content (vrai no-op, pas de tour)
        if transcript_type == "partial":
            logger.debug("partial transcript, skipping")
            _norm_len = len(normalize_transcript(raw_text or ""))
            logger.info(
                "decision_in",
                extra={
                    "call_id": call_id,
                    "state_before": getattr(session, "state", ""),
                    "transcript_type": transcript_type or "unknown",
                    "confidence": confidence,
                    "raw_len": len(raw_text or ""),
                    "normalized_len": _norm_len,
                    "stt_class": "PARTIAL",
                    "noise_count": getattr(session, "noise_detected_count", 0),
                    "empty_count": getattr(session, "empty_message_count", 0),
                    "turn_count": getattr(session, "turn_count", 0),
                },
            )
            _log_decision_out(call_id, session, "http_204", "")
            return Response(status_code=204)

        t2 = log_timer("Message extracted", t1)
        kind, text_to_use = _classify_stt_input(
            raw_text, confidence, transcript_type, message_type=message_type
        )
        normalized = normalize_transcript(raw_text or "")

        logger.info(
            "decision_in",
            extra={
                "call_id": call_id,
                "state_before": getattr(session, "state", ""),
                "transcript_type": transcript_type or "unknown",
                "confidence": confidence,
                "raw_len": len(raw_text or ""),
                "normalized_len": len(normalized or ""),
                "stt_class": kind,
                "noise_count": getattr(session, "noise_detected_count", 0),
                "empty_count": getattr(session, "empty_message_count", 0),
                "turn_count": getattr(session, "turn_count", 0),
            },
        )

        if kind == "NOISE":
            events = ENGINE.handle_noise(session)
            if not events:
                _log_decision_out(call_id, session, "http_204", "")
                return Response(status_code=204)
            if hasattr(ENGINE.session_store, "save"):
                ENGINE.session_store.save(session)
                logger.info("[SESSION_SAVED] call_id=%s state=%s last_agent_len=%s", call_id[:20], getattr(session, "state", ""), len(getattr(session, "last_agent_message", "") or ""))
            total_ms = (time.time() - t_start) * 1000
            logger.info(
                "stt_noise_detected",
                extra={
                    "call_id": call_id,
                    "state": getattr(session, "state", ""),
                    "confidence": confidence,
                    "text_len": len(raw_text or ""),
                    "normalized_len": len(normalized or ""),
                    "noise_count": getattr(session, "noise_detected_count", 0),
                },
            )
            reply_text = events[0].text
            _action = "reply"
            if getattr(session, "state", "") == "INTENT_ROUTER":
                _action = "router"
            elif getattr(session, "state", "") == "TRANSFERRED":
                _action = "transfer"
            elif getattr(session, "state", "") == "CONFIRMED":
                _action = "confirmed"
            _log_decision_out(call_id, session, _action, reply_text)
            print(f"✅ NOISE response: {total_ms:.0f}ms | '{reply_text[:50]}...'")
            return _vapi_content_response(call_id, reply_text)

        if kind == "SILENCE":
            events = _get_engine(call_id).handle_message(call_id, "")
            _maybe_reset_noise_on_terminal(session, events)
            if hasattr(ENGINE.session_store, "save"):
                ENGINE.session_store.save(session)
                logger.info("[SESSION_SAVED] call_id=%s state=%s last_agent_len=%s", call_id[:20], getattr(session, "state", ""), len(getattr(session, "last_agent_message", "") or ""))
            response_text = events[0].text if events else "Je n'ai pas compris"
            _action = "reply"
            if "INTENT_ROUTER" in getattr(session, "state", ""):
                _action = "router"
            elif getattr(session, "state", "") == "TRANSFERRED":
                _action = "transfer"
            elif getattr(session, "state", "") == "CONFIRMED":
                _action = "confirmed"
            _log_decision_out(call_id, session, _action, response_text)
            total_ms = (time.time() - t_start) * 1000
            print(f"✅ SILENCE response: {total_ms:.0f}ms | '{response_text[:50]}...'")
            return _vapi_content_response(call_id, response_text)

        # TEXT
        if text_to_use and text_to_use.strip():
            print(f"💬 User: '{text_to_use}'")
            # P1: consent_obtained au premier message (consentement implicite uniquement)
            from backend.tenant_config import get_consent_mode
            if not getattr(session, "_consent_obtained_persisted", False) and get_consent_mode(getattr(session, "tenant_id", None)) == "implicit":
                try:
                    from backend.engine import persist_consent_obtained
                    persist_consent_obtained(session, channel="vocal")
                    session._consent_obtained_persisted = True
                except Exception:
                    pass
            t3 = log_timer("Session loaded", t2)
            events = _get_engine(call_id).handle_message(call_id, text_to_use)
            _maybe_reset_noise_on_terminal(session, events)
            if hasattr(ENGINE.session_store, "save"):
                ENGINE.session_store.save(session)
            t4 = log_timer("ENGINE processed", t3)
            response_text = events[0].text if events else "Je n'ai pas compris"
            _action = "reply"
            if "INTENT_ROUTER" in getattr(session, "state", ""):
                _action = "router"
            elif getattr(session, "state", "") == "TRANSFERRED":
                _action = "transfer"
            elif getattr(session, "state", "") == "CONFIRMED":
                _action = "confirmed"
            _log_decision_out(call_id, session, _action, response_text)
            if hasattr(ENGINE.session_store, "save"):
                ENGINE.session_store.save(session)
                logger.info("[SESSION_SAVED] call_id=%s state=%s last_agent_len=%s", call_id[:20], getattr(session, "state", ""), len(getattr(session, "last_agent_message", "") or ""))
            total_ms = (time.time() - t_start) * 1000
            print(f"✅ TOTAL: {total_ms:.0f}ms | Response: '{response_text[:50]}...'")
            return _vapi_content_response(call_id, response_text)

        # Pas de texte utilisable après classification → traiter comme silence (évite "plus ne se passe" après accueil)
        print("⚠️ No user text after classification, treating as silence")
        events = _get_engine(call_id).handle_message(call_id, "")
        _maybe_reset_noise_on_terminal(session, events)
        if hasattr(ENGINE.session_store, "save"):
            ENGINE.session_store.save(session)
            logger.info("[SESSION_SAVED] call_id=%s state=%s last_agent_len=%s", call_id[:20], getattr(session, "state", ""), len(getattr(session, "last_agent_message", "") or ""))
        response_text = events[0].text if events else "Je n'ai pas bien compris. Pouvez-vous répéter ?"
        _log_decision_out(call_id, session, "reply", response_text)
        return _vapi_content_response(call_id, response_text)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        _err_call_id = "unknown"
        try:
            _err_call_id = (payload.get("call") or {}).get("id") or "unknown"
        except NameError:
            pass
        return _vapi_content_response(_err_call_id, "Désolé, une erreur est survenue.")


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
                logger.warning("[CALL_LOCK_TIMEOUT] tenant_id=%s call_id=%s", resolved_tenant_id, call_id[:20])
                try:
                    from backend.engine import _persist_ivr_event
                    _persist_ivr_event(
                        ENGINE.session_store.get_or_create(call_id),
                        "call_lock_timeout",
                        reason="concurrent_webhook",
                    )
                except Exception:
                    pass
                return Response(status_code=204)
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
    from fastapi.responses import StreamingResponse

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
        
        # Vapi envoie un tableau de messages
        messages = payload.get("messages", [])
        is_streaming = payload.get("stream", False)
        
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
        logger.debug("user message: %r", (user_message or "")[:80])
        
        if not user_message:
            # Premier message ou pas de message user
            response_text = prompts.get_vocal_greeting(config.BUSINESS_NAME)
        else:
            # Traiter via ENGINE
            overlap_handled = False
            response_text = ""
            action_taken = ""

            # Phase 2: PG-first read — recharger depuis PG si session absente (restart/multi-instance)
            # Phase 2.1: lock chat/completions — lock court sur get_or_resume uniquement
            # (journal appelle pg_add_message qui UPDATE call_sessions → on ne peut pas tenir le lock pendant)
            state_before_turn = "START"
            if _pg_lock_ok():
                try:
                    from backend.session_pg import pg_lock_call_session, LockTimeout
                    _call_journal_ensure(resolved_tenant_id, call_id)
                    with pg_lock_call_session(resolved_tenant_id, call_id, timeout_seconds=2):
                        session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
                        state_before_turn = getattr(session, "state", "START")
                except LockTimeout:
                    logger.warning("[CALL_LOCK_TIMEOUT] tenant_id=%s call_id=%s", resolved_tenant_id, call_id[:20])
                    try:
                        from backend.engine import _persist_ivr_event
                        s = ENGINE.session_store.get_or_create(call_id)
                        s.tenant_id = resolved_tenant_id
                        _persist_ivr_event(s, "call_lock_timeout", reason="concurrent_webhook")
                    except Exception:
                        pass
                    return Response(status_code=204)
                except Exception as e:
                    logger.warning("[CALL_LOCK_WARN] err=%s", e, exc_info=True)
                    session = _get_or_resume_voice_session(resolved_tenant_id, call_id)
                    state_before_turn = getattr(session, "state", "START")
            else:
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
        
        # Format OpenAI-compatible (non-streaming)
        return {
            "id": f"chatcmpl-{call_id}",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }]
        }
        
    except Exception as e:
        print(f"❌ Custom LLM error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Désolé, une erreur est survenue."
                }
            }]
        }


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
