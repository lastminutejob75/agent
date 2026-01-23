# backend/routes/voice.py
"""
Route complète pour le canal Voix (Vapi).

Ce fichier remplace l'ancien backend/vapi.py en utilisant
la nouvelle architecture multi-canal.
"""

from fastapi import APIRouter, Request, HTTPException
import logging

from backend.channels.voice import VoiceChannel, create_vapi_fallback_response
from backend.models.message import AgentResponse
from backend.engine import ENGINE
from backend import prompts

logger = logging.getLogger(__name__)

# Créer le router FastAPI
router = APIRouter(prefix="/api/vapi", tags=["voice"])

# Créer l'instance du VoiceChannel
voice_channel = VoiceChannel()


@router.post("/webhook")
async def vapi_webhook(request: Request):
    """
    Webhook Vapi - Point d'entrée pour tous les appels vocaux.
    
    Gère différents types de messages Vapi :
    - assistant-request : Vapi demande la config assistant → {}
    - conversation-start : Début d'appel → Message d'accueil
    - user-message / transcript : Message utilisateur → Traitement ENGINE
    - status-update, end-of-call-report : Ignorés
    """
    try:
        # Lire le payload
        try:
            payload = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return {"status": "error"}
        
        message = payload.get("message", {})
        message_type = message.get("type", "")
        call = payload.get("call", {})
        call_id = call.get("id", "unknown")
        
        logger.info(f"Vapi webhook: type={message_type}, call_id={call_id}")
        
        # ========================================
        # 1. assistant-request → Retourner {}
        # ========================================
        if message_type == "assistant-request":
            logger.info("Assistant request - using Vapi default assistant")
            return {}
        
        # ========================================
        # 2. conversation-start → Message d'accueil
        # ========================================
        if message_type in ["conversation-start", "call-start", "call_start"]:
            logger.info(f"Call started: {call_id}")
            return {
                "results": [{
                    "type": "say",
                    "text": prompts.MSG_WELCOME
                }]
            }
        
        # ========================================
        # 3. user-message / transcript → ENGINE
        # ========================================
        if message_type in ["user-message", "transcript", "user_message"]:
            # Extraire le texte utilisateur
            user_text = message.get("content", "") or message.get("transcript", "")
            
            if not user_text:
                logger.warning(f"Empty user message for call {call_id}")
                return {
                    "results": [{
                        "type": "say",
                        "text": "Je n'ai pas compris. Pouvez-vous répéter ?"
                    }]
                }
            
            logger.info(f"Processing: call_id={call_id}, text='{user_text}'")
            
            # Marquer session comme vocale
            session = ENGINE.session_store.get_or_create(call_id)
            session.channel = "vocal"
            
            # Traiter via ENGINE
            events = ENGINE.handle_message(call_id, user_text)
            
            if events and len(events) > 0:
                event = events[0]
                response_text = event.text
                
                logger.info(f"Response: '{response_text[:50]}...'")
                
                # Vérifier si transfert
                if event.transfer_reason:
                    return {
                        "results": [
                            {"type": "say", "text": response_text},
                            {"type": "transfer", "destination": "+33600000000"}
                        ]
                    }
                
                return {
                    "results": [{
                        "type": "say",
                        "text": response_text
                    }]
                }
            
            # Fallback
            logger.warning("No events from ENGINE")
            return {
                "results": [{
                    "type": "say",
                    "text": "Je n'ai pas compris. Pouvez-vous reformuler ?"
                }]
            }
        
        # ========================================
        # 4. Autres types → Ignorer
        # ========================================
        logger.debug(f"Ignoring message type: {message_type}")
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Vapi webhook error: {e}", exc_info=True)
        return {
            "results": [{
                "type": "say",
                "text": "Désolé, une erreur est survenue. Veuillez réessayer."
            }]
        }


@router.get("/health")
async def vapi_health():
    """Health check pour le canal Voice"""
    return {
        "status": "ok",
        "service": "voice",
        "channel": "vapi",
        "message": "Voice channel is ready"
    }


@router.get("/test")
async def vapi_test():
    """Test de l'engine"""
    try:
        events = ENGINE.handle_message("test_vapi", "bonjour")
        if events and len(events) > 0:
            return {
                "status": "ok",
                "test_input": "bonjour",
                "test_response": events[0].text,
                "message": "Voice channel is working"
            }
        return {"status": "error", "error": "No response"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/call-started")
async def vapi_call_started(request: Request):
    """Callback début d'appel"""
    try:
        payload = await request.json()
        call_id = payload.get("call", {}).get("id", "")
        logger.info(f"Call started: {call_id}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"status": "error"}


@router.post("/call-ended")
async def vapi_call_ended(request: Request):
    """Callback fin d'appel"""
    try:
        payload = await request.json()
        call_id = payload.get("call", {}).get("id", "")
        duration = payload.get("call", {}).get("duration", 0)
        logger.info(f"Call ended: {call_id}, duration={duration}s")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"status": "error"}


@router.get("/stats")
async def vapi_stats():
    """Statistiques vocales"""
    try:
        total = len(ENGINE.session_store.sessions)
        active = sum(
            1 for s in ENGINE.session_store.sessions.values()
            if s.channel == "vocal" and not s.is_expired()
        )
        return {"channel": "vocal", "total": total, "active": active, "status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
