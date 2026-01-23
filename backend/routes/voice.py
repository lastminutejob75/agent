# backend/routes/voice.py
"""
Route pour le canal Voix (Vapi).
Format de réponse : {"content": "..."} uniquement.
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
    Webhook Vapi - Retourne UNIQUEMENT le format {"content": "..."}
    """
    try:
        payload = await request.json()
        logger.info(f"📞 Webhook: {payload}")
        
        message = payload.get("message", {})
        message_type = message.get("type", "")
        call_id = payload.get("call", {}).get("id", "unknown")
        
        logger.info(f"Type: {message_type}, Call: {call_id}")
        
        # ========================================
        # assistant-request → {}
        # ========================================
        if message_type == "assistant-request":
            logger.info("✅ Assistant request")
            return {}
        
        # ========================================
        # conversation-start → Premier message
        # ========================================
        if message_type in ["conversation-start", "call-start"]:
            logger.info("✅ Call started")
            return {"content": prompts.MSG_WELCOME}
        
        # ========================================
        # user-message / transcript → ENGINE
        # ========================================
        if message_type in ["user-message", "transcript"]:
            user_text = message.get("content", "") or message.get("transcript", "")
            
            if not user_text:
                logger.warning("⚠️ Empty message")
                return {"content": "Je n'ai pas compris. Pouvez-vous répéter ?"}
            
            logger.info(f"📝 User: '{user_text}'")
            
            # Session vocale
            session = ENGINE.session_store.get_or_create(call_id)
            session.channel = "vocal"
            
            # Traiter
            events = ENGINE.handle_message(call_id, user_text)
            
            if events and len(events) > 0:
                response_text = events[0].text
                logger.info(f"✅ Response: '{response_text[:50]}...'")
                return {"content": response_text}
            
            logger.warning("⚠️ No events")
            return {"content": "Je n'ai pas compris. Pouvez-vous reformuler ?"}
        
        # ========================================
        # Autres → Ignorer
        # ========================================
        logger.debug(f"Ignoring: {message_type}")
        return {}
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return {"content": "Désolé, une erreur est survenue."}


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
