# backend/routes/voice.py
"""
Route complète pour le canal Voix (Vapi).
"""

from fastapi import APIRouter, Request
import logging

from backend.engine import ENGINE
from backend import prompts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vapi", tags=["voice"])


@router.post("/webhook")
async def vapi_webhook(request: Request):
    """
    Webhook Vapi - Point d'entrée pour tous les appels vocaux.
    
    Supporte les deux formats de réponse Vapi :
    - {"content": "..."} - Format simple (Custom LLM)
    - {"results": [{"type": "say", "text": "..."}]} - Format actions
    """
    try:
        payload = await request.json()
        logger.info(f"📞 Vapi webhook received: {payload}")
        
        message = payload.get("message", {})
        message_type = message.get("type", "")
        call = payload.get("call", {})
        call_id = call.get("id", "unknown")
        
        logger.info(f"Type: {message_type}, Call: {call_id}")
        
        # ========================================
        # assistant-request → Retourner {}
        # ========================================
        if message_type == "assistant-request":
            logger.info("✅ Assistant request - returning {}")
            return {}
        
        # ========================================
        # conversation-start → Message d'accueil
        # ========================================
        if message_type in ["conversation-start", "call-start", "call_start"]:
            logger.info("✅ Call started - sending welcome")
            return _format_response(prompts.MSG_WELCOME)
        
        # ========================================
        # user-message / transcript → ENGINE
        # ========================================
        if message_type in ["user-message", "transcript", "user_message"]:
            user_text = message.get("content", "") or message.get("transcript", "")
            
            if not user_text:
                logger.warning("⚠️ Empty user message")
                return _format_response("Je n'ai pas compris. Pouvez-vous répéter ?")
            
            logger.info(f"📝 User said: '{user_text}'")
            
            # Marquer session comme vocale
            session = ENGINE.session_store.get_or_create(call_id)
            session.channel = "vocal"
            
            # Traiter via ENGINE
            events = ENGINE.handle_message(call_id, user_text)
            
            if events and len(events) > 0:
                response_text = events[0].text
                logger.info(f"✅ Response: '{response_text[:50]}...'")
                return _format_response(response_text)
            
            logger.warning("⚠️ No events from ENGINE")
            return _format_response("Je n'ai pas compris. Pouvez-vous reformuler ?")
        
        # ========================================
        # Autres types → Ignorer
        # ========================================
        logger.debug(f"Ignoring type: {message_type}")
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return _format_response("Désolé, une erreur est survenue.")


def _format_response(text: str) -> dict:
    """
    Formate la réponse pour Vapi.
    Retourne les deux formats pour compatibilité.
    """
    return {
        # Format simple (Custom LLM / certains modes)
        "content": text,
        # Format actions (Server URL mode)
        "results": [{
            "type": "say",
            "text": text
        }]
    }


@router.get("/health")
async def vapi_health():
    return {"status": "ok", "service": "voice", "channel": "vapi"}


@router.get("/test")
async def vapi_test():
    try:
        events = ENGINE.handle_message("test_vapi", "bonjour")
        if events:
            return {"status": "ok", "response": events[0].text}
        return {"status": "error", "error": "No response"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/call-started")
async def vapi_call_started(request: Request):
    payload = await request.json()
    logger.info(f"📞 Call started: {payload.get('call', {}).get('id')}")
    return {"status": "ok"}


@router.post("/call-ended")
async def vapi_call_ended(request: Request):
    payload = await request.json()
    logger.info(f"📞 Call ended: {payload.get('call', {}).get('id')}")
    return {"status": "ok"}
