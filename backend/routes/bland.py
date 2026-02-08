# backend/routes/bland.py
"""
Route pour Bland.ai - Voice Agent simplifié
"""

from fastapi import APIRouter, Request
import logging
import json

from backend.engine import ENGINE
from backend import prompts, config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bland", tags=["bland"])


@router.post("/webhook")
async def bland_webhook(request: Request):
    """
    Webhook Bland.ai - Reçoit les messages et retourne les réponses.
    Format simple : Bland envoie le transcript, on retourne la réponse.
    """
    try:
        payload = await request.json()
        
        print(f"🔔 BLAND WEBHOOK")
        print(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        # Extraire les données
        # Bland peut envoyer différents formats, on gère les plus courants
        user_text = (
            payload.get("transcript") or 
            payload.get("input") or 
            payload.get("message") or 
            payload.get("text") or
            ""
        )
        call_id = payload.get("call_id") or payload.get("id") or "bland_unknown"
        
        print(f"📝 User: '{user_text}'")
        print(f"📞 Call ID: {call_id}")
        
        # Si c'est le début de l'appel (pas de texte)
        if not user_text or not user_text.strip():
            response = prompts.get_vocal_greeting(config.BUSINESS_NAME)
            print(f"✅ Welcome: {response}")
            return {"response": response, "text": response}
        
        # Session vocale
        session = ENGINE.session_store.get_or_create(call_id)
        session.channel = "vocal"
        
        # Traiter via ENGINE
        events = ENGINE.handle_message(call_id, user_text)
        
        if events and len(events) > 0:
            response = events[0].text
        else:
            response = "Je n'ai pas compris. Pouvez-vous répéter ?"
        
        print(f"✅ Response: {response}")
        
        # Retourner dans plusieurs formats pour compatibilité
        return {
            "response": response,
            "text": response,
            "message": response
        }
        
    except Exception as e:
        print(f"❌ Bland error: {e}")
        import traceback
        traceback.print_exc()
        return {"response": "Désolé, une erreur est survenue."}


@router.get("/health")
async def bland_health():
    return {"status": "ok", "service": "bland"}
