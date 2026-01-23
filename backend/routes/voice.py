# backend/routes/voice.py
"""
Route pour le canal Voix (Vapi) - AVEC LOGS DÉTAILLÉS
"""

from fastapi import APIRouter, Request
import logging
import json

from backend.engine import ENGINE
from backend import prompts

# Configuration logging pour voir dans Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vapi", tags=["voice"])


@router.post("/webhook")
async def vapi_webhook(request: Request):
    """
    Webhook Vapi - LOGS DÉTAILLÉS POUR DEBUG
    """
    try:
        payload = await request.json()
        
        # ===== LOGS DÉTAILLÉS =====
        print(f"🔔🔔🔔 WEBHOOK APPELÉ 🔔🔔🔔")
        print(f"📦 Payload complet: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        message = payload.get("message", {})
        message_type = message.get("type", "UNKNOWN")
        call_id = payload.get("call", {}).get("id", "unknown")
        
        print(f"📍 Type: {message_type}")
        print(f"📍 Call ID: {call_id}")
        print(f"📍 Message content: {message.get('content', 'N/A')}")
        
        logger.info(f"🔔 WEBHOOK: type={message_type}, call={call_id}")
        
        # ========================================
        # assistant-request → {}
        # ========================================
        if message_type == "assistant-request":
            print("✅ Returning {} for assistant-request")
            return {}
        
        # ========================================
        # conversation-start → Premier message
        # ========================================
        if message_type in ["conversation-start", "call-start"]:
            response = {"content": prompts.MSG_WELCOME}
            print(f"✅ Conversation start, returning: {response}")
            return response
        
        # ========================================
        # user-message / transcript → ENGINE
        # ========================================
        if message_type in ["user-message", "transcript"]:
            user_text = message.get("content", "") or message.get("transcript", "")
            print(f"📝 User text: '{user_text}'")
            
            if not user_text:
                response = {"content": "Je n'ai pas compris. Pouvez-vous répéter ?"}
                print(f"⚠️ Empty text, returning: {response}")
                return response
            
            # Session vocale
            session = ENGINE.session_store.get_or_create(call_id)
            session.channel = "vocal"
            
            # Traiter
            events = ENGINE.handle_message(call_id, user_text)
            
            if events and len(events) > 0:
                response_text = events[0].text
                response = {"content": response_text}
                print(f"✅ ENGINE response: {response}")
                return response
            
            response = {"content": "Je n'ai pas compris. Pouvez-vous reformuler ?"}
            print(f"⚠️ No events, returning: {response}")
            return response
        
        # ========================================
        # Autres types → Log et ignorer
        # ========================================
        print(f"❓ Unknown type: {message_type}, returning {{}}")
        return {}
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        logger.error(f"❌ Error: {e}", exc_info=True)
        return {"content": "Désolé, une erreur est survenue."}


@router.get("/health")
async def vapi_health():
    return {"status": "ok", "service": "voice", "logging": "enabled"}


@router.get("/test")
async def vapi_test():
    print("🧪 Test endpoint called")
    try:
        events = ENGINE.handle_message("test", "bonjour")
        if events:
            return {"status": "ok", "response": events[0].text}
        return {"status": "error"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
