# backend/routes/voice.py
"""
Route pour le canal Voix (Vapi) - DEBUG COMPLET + TIMERS
Avec mémoire client et stats pour rapports.
"""

from fastapi import APIRouter, Request
from fastapi.responses import Response
import logging
import json
import re
import time
import uuid
from typing import Optional

from backend.engine import ENGINE
from backend import prompts, config
from backend.client_memory import get_client_memory
from backend.reports import get_report_generator
from backend.stt_utils import normalize_transcript, is_filler_only
from backend.stt_common import classify_text_only, estimate_tts_duration, is_critical_overlap

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instances singleton
client_memory = get_client_memory()
report_generator = get_report_generator()


def _reconstruct_session_from_history(session, messages: list):
    """
    Reconstruit l'état de la session depuis l'historique des messages.
    Nécessaire si la session en mémoire a été perdue (redémarrage Railway).
    
    STRATÉGIE: Extraire TOUTES les données depuis l'historique
    """
    from backend.guards import clean_name_from_vocal
    
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
    
    print(f"🔄 Reconstructing session from {len(messages)} messages")
    
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
                            print(f"🔄 Name: '{potential_name}' → '{cleaned_name}'")
            
            # Extraire la préférence
            if any(p in content for p in patterns["QUALIF_PREF"]):
                if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                    potential_pref = messages[i + 1].get("content", "").strip()
                    if potential_pref and len(potential_pref) <= 50:
                        session.qualif_data.pref = potential_pref
                        print(f"🔄 Pref: {potential_pref}")
            
            # Extraire le contact
            if any(p in content for p in patterns["QUALIF_CONTACT"]):
                if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                    potential_contact = messages[i + 1].get("content", "").strip()
                    if potential_contact:
                        session.qualif_data.contact = potential_contact
                        print(f"🔄 Contact: {potential_contact}")
    
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
        print(f"🔄 State: {detected_state} (from: '{last_assistant_msg[:60]}...')")
        
        # Si WAIT_CONFIRM → on doit reproposer les créneaux (on ne peut pas les reconstruire)
        if detected_state == "WAIT_CONFIRM":
            print(f"⚠️ WAIT_CONFIRM detected - slots will be re-fetched on next handler call")
    else:
        print(f"⚠️ Could not detect state from: '{last_assistant_msg[:60]}...'")
    
    print(f"🔄 Reconstruction complete: state={session.state}, name={session.qualif_data.name}, pref={session.qualif_data.pref}")
    
    return session


def log_timer(label: str, start: float) -> float:
    """Log le temps écoulé et retourne le nouveau timestamp."""
    now = time.time()
    elapsed_ms = (now - start) * 1000
    print(f"⏱️ {label}: {elapsed_ms:.0f}ms")
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


# Tokens critiques : jamais NOISE même si confidence basse (confirmations, choix créneaux)
CRITICAL_TOKENS = frozenset({
    "oui", "non", "ok", "okay", "daccord", "d'accord",
    "1", "2", "3", "un", "deux", "trois",
    "premier", "deuxième", "troisième", "premiere", "deuxieme", "troisieme",
    "ouais", "ouaip",
    "le premier", "le deuxième", "le troisième",
    "la première", "la deuxième", "la troisième",
})


def _is_critical_token(text: str) -> bool:
    """
    Vérifie si le texte est un token critique (jamais classé NOISE).
    """
    if not text:
        return False
    t = text.strip().lower()
    t = re.sub(r"['']", "", t)  # d'accord → daccord
    t = "".join(ch for ch in t if ch.isalnum() or ch.isspace()).strip()
    if not t:
        return False
    if t in CRITICAL_TOKENS:
        return True
    parts = t.split()
    if len(parts) == 2:
        if parts[0] in {"oui", "ok", "non"} and parts[1] in {"1", "2", "3", "un", "deux", "trois"}:
            return True
    return False


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
    if _is_critical_token(normalized):
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

        # Garde : ne traiter que les messages user (transcripts utilisateur)
        if message_role is not None and message_role != "user":
            logger.warning(
                "non_user_message",
                extra={"role": message_role, "type": message_type, "call_id": (payload.get("call") or {}).get("id")},
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
        call_id = (payload.get("call") or {}).get("id") or "unknown"

        print(f"🔔 WEBHOOK | type={message_type} | transcriptType={transcript_type} | call={call_id}")

        if message_type == "assistant-request":
            print("✅ Returning {} for assistant-request")
            return {}

        session = ENGINE.session_store.get_or_create(call_id)
        session.channel = "vocal"

        # Partial => HTTP 204 No Content (vrai no-op, pas de tour)
        if transcript_type == "partial":
            print("⏭️ Partial transcript, skipping")
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
            return {"content": reply_text}

        if kind == "SILENCE":
            events = ENGINE.handle_message(call_id, "")
            _maybe_reset_noise_on_terminal(session, events)
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
            return {"content": response_text}

        # TEXT
        if text_to_use and text_to_use.strip():
            print(f"💬 User: '{text_to_use}'")
            t3 = log_timer("Session loaded", t2)
            events = ENGINE.handle_message(call_id, text_to_use)
            _maybe_reset_noise_on_terminal(session, events)
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
            total_ms = (time.time() - t_start) * 1000
            print(f"✅ TOTAL: {total_ms:.0f}ms | Response: '{response_text[:50]}...'")
            return {"content": response_text}

        print("⚠️ No user text after classification")
        _log_decision_out(call_id, session, "empty_reply", "")
        return {"content": ""}

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"content": "Désolé, une erreur est survenue."}


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
        
        # Session vocale
        session = ENGINE.session_store.get_or_create(call_id)
        session.channel = "vocal"
        
        # Traiter
        events = ENGINE.handle_message(call_id, user_message)
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
        print(f"💬 User: '{user_message}'")
        
        if not user_message:
            # Premier message ou pas de message user
            response_text = prompts.get_vocal_greeting(config.BUSINESS_NAME)
            print(f"✅ Welcome message")
        else:
            # Traiter via ENGINE
            session = ENGINE.session_store.get_or_create(call_id)
            session.channel = "vocal"
            
            # 🧠 Stocker le téléphone dans la session pour plus tard
            if customer_phone:
                session.customer_phone = customer_phone
            
            # 🔄 RECONSTRUCTION DE L'ÉTAT depuis l'historique des messages
            # NOTE: Avec SQLite, cette reconstruction ne devrait plus être nécessaire
            # On la garde en fallback si SQLite échoue
            if session.state == "START" and len(messages) > 1 and not session.qualif_data.name:
                print(f"⚠️ Session in START with history but no data → reconstruction needed")
                session = _reconstruct_session_from_history(session, messages)
                print(f"🔄 Session reconstructed: state={session.state}, name={session.qualif_data.name}")
            else:
                print(f"✅ Session loaded OK: state={session.state}, name={session.qualif_data.name}")
            
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
                                print(f"🧠 Returning client detected: {existing_client.name}")
                except Exception as e:
                    print(f"⚠️ Client memory error: {e}")
            
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
            overlap_handled = False
            response_text = ""
            action_taken = ""
            if _is_agent_speaking(session):
                # Interruption pendant énonciation des créneaux (WAIT_CONFIRM) : "un", "1", "deux" = choix valide → ne pas bloquer
                if session.state == "WAIT_CONFIRM" and _is_critical_token(normalized):
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
                            events = ENGINE.handle_message(call_id, "")
                            response_text = events[0].text if events else prompts.MSG_EMPTY_MESSAGE
                            action_taken = "silence"
                            _maybe_reset_noise_on_terminal(session, events or [])
                        elif kind == "TEXT":
                            events = ENGINE.handle_message(call_id, normalized)
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
                                slot_label = session.pending_slot_labels[0] if session.pending_slot_labels else "RDV"
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
                    events = await asyncio.to_thread(ENGINE.handle_message, call_id, user_message)
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
                                slot_label = session_after.pending_slot_labels[0] if session_after.pending_slot_labels else "RDV"
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
        events = ENGINE.handle_message("test", "bonjour")
        if events:
            return {"status": "ok", "response": events[0].text}
        return {"status": "error"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
