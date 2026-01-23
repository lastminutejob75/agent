# backend/routes/voice.py
"""
Route pour le canal Voix (Vapi)
"""

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
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
    Webhook Vapi - Teste plusieurs formats de réponse
    """
    try:
        payload = await request.json()
        
        print(f"🔔 WEBHOOK APPELÉ")
        print(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        message = payload.get("message", {})
        message_type = message.get("type", "")
        call_id = payload.get("call", {}).get("id", "unknown")
        
        print(f"📍 Type: {message_type}, Call: {call_id}")
        
        # assistant-request
        if message_type == "assistant-request":
            print("✅ Assistant request - returning {}")
            return {}
        
        # conversation-start
        if message_type in ["conversation-start", "call-start"]:
            response_text = prompts.MSG_WELCOME
            print(f"✅ Call started: {response_text}")
            return _build_response(response_text)
        
        # user-message / transcript
        if message_type in ["user-message", "transcript"]:
            user_text = message.get("content", "") or message.get("transcript", "")
            print(f"📝 User: '{user_text}'")
            
            if not user_text:
                return _build_response("Je n'ai pas compris. Pouvez-vous répéter ?")
            
            session = ENGINE.session_store.get_or_create(call_id)
            session.channel = "vocal"
            
            events = ENGINE.handle_message(call_id, user_text)
            
            if events and len(events) > 0:
                response_text = events[0].text
                print(f"✅ Response: {response_text}")
                return _build_response(response_text)
            
            return _build_response("Je n'ai pas compris.")
        
        print(f"❓ Unknown type: {message_type}")
        return {}
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return _build_response("Désolé, une erreur est survenue.")


def _build_response(text: str) -> dict:
    """
    Construit la réponse dans TOUS les formats possibles
    pour que Vapi trouve le contenu.
    """
    response = {
        # Format 1: content (Custom LLM)
        "content": text,
        # Format 2: message (Chat completion style)
        "message": text,
        # Format 3: text (Simple)
        "text": text,
        # Format 4: response
        "response": text,
        # Format 5: output
        "output": text,
        # Format 6: assistant message (OpenAI style)
        "choices": [{
            "message": {
                "role": "assistant",
                "content": text
            }
        }],
        # Format 7: results (Vapi actions)
        "results": [{
            "type": "say",
            "text": text
        }]
    }
    print(f"📤 Sending response with all formats")
    return response


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
