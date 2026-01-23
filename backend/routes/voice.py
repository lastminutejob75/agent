# backend/routes/voice.py
"""
Route pour le canal Voix (Vapi) - DEBUG COMPLET
"""

from fastapi import APIRouter, Request
import logging
import json

from backend.engine import ENGINE
from backend import prompts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vapi", tags=["voice"])


@router.post("/webhook")
async def vapi_webhook(request: Request):
    """
    Webhook Vapi - DEBUG COMPLET
    """
    try:
        payload = await request.json()
        
        # LOG COMPLET
        print(f"🔔🔔🔔 WEBHOOK REÇU 🔔🔔🔔")
        print(f"📦 FULL PAYLOAD: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        message = payload.get("message", {})
        message_type = message.get("type", "NO_TYPE")
        call_id = payload.get("call", {}).get("id", "unknown")
        
        print(f"📩 Message type: '{message_type}'")
        print(f"📞 Call ID: {call_id}")
        print(f"💬 Content: {message.get('content', 'N/A')}")
        print(f"💬 Transcript: {message.get('transcript', 'N/A')}")
        
        # assistant-request
        if message_type == "assistant-request":
            print("✅ Returning {} for assistant-request")
            return {}
        
        # ACCEPTE TOUS LES MESSAGES AVEC DU TEXTE
        user_text = message.get("content") or message.get("transcript") or ""
        
        print(f"🎯 User text extracted: '{user_text}'")
        
        if user_text and user_text.strip():
            print(f"✅ Processing message...")
            
            session = ENGINE.session_store.get_or_create(call_id)
            session.channel = "vocal"
            
            events = ENGINE.handle_message(call_id, user_text)
            response_text = events[0].text if events else "Je n'ai pas compris"
            
            print(f"✅ ENGINE response: '{response_text}'")
            
            # FORMAT SIMPLE
            response = {"content": response_text}
            print(f"📤 Returning: {json.dumps(response, ensure_ascii=False)}")
            return response
        
        print(f"⚠️ No user text found, returning empty")
        return {}
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
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
