# backend/vapi.py

from fastapi import APIRouter, Request, HTTPException
from typing import Dict, List, Optional
import logging

from backend.engine import ENGINE
from backend.db import list_free_slots, book_slot_atomic
from backend.session import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vapi", tags=["vapi"])


@router.post("/webhook")
async def vapi_webhook(request: Request):
    """
    Webhook Vapi - Reçoit les transcripts et retourne les réponses.
    """
    try:
        payload = await request.json()
        logger.info(f"Vapi webhook received: {payload}")
        
        # Extraire le message
        message = payload.get("message", {})
        message_type = message.get("type", "")
        
        # Ignorer certains events techniques
        if message_type in ["speech-update", "function-call-result", "hang"]:
            return {"status": "ignored"}
        
        # Extraire transcript utilisateur
        transcript = message.get("content", "")
        call_id = payload.get("call", {}).get("id", "")
        
        if not transcript or not call_id:
            logger.warning(f"Missing transcript or call_id: {payload}")
            return {"status": "no_content"}
        
        logger.info(f"Processing call_id={call_id}, transcript='{transcript}'")
        
        # Récupérer ou créer session avec channel=vocal
        session = ENGINE.session_store.get_or_create(call_id)
        session.channel = "vocal"
        
        # Traiter le message via l'engine
        events = ENGINE.handle_message(call_id, transcript)
        
        # Formater réponse pour Vapi
        if events and len(events) > 0:
            # Prendre le texte du premier event
            response_text = events[0].text
            
            logger.info(f"Responding to Vapi: {response_text}")
            
            return {
                "results": [{
                    "type": "say",
                    "text": response_text
                }]
            }
        
        # Fallback si pas d'event
        return {
            "results": [{
                "type": "say",
                "text": "Je n'ai pas bien compris. Pouvez-vous répéter ?"
            }]
        }
    
    except Exception as e:
        logger.error(f"Vapi webhook error: {e}", exc_info=True)
        return {
            "results": [{
                "type": "say",
                "text": "Désolé, une erreur s'est produite. Je vous transfère."
            }]
        }


@router.get("/health")
async def vapi_health():
    """Health check pour vérifier que l'API Vapi fonctionne."""
    return {
        "status": "ok",
        "service": "vapi",
        "message": "Vapi webhook is ready"
    }


@router.get("/test")
async def vapi_test():
    """
    Endpoint de test pour vérifier la configuration.
    """
    try:
        # Tester que l'engine fonctionne
        test_session = ENGINE.session_store.get_or_create("test_vapi")
        test_session.channel = "vocal"
        
        events = ENGINE.handle_message("test_vapi", "bonjour")
        
        return {
            "status": "ok",
            "test_response": events[0].text if events else "No response",
            "message": "Vapi backend is working correctly"
        }
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }

