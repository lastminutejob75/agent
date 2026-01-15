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
    Webhook Vapi - Gère différents types de messages Vapi.
    """
    try:
        payload = await request.json()
        message = payload.get("message", {})
        message_type = message.get("type", "")
        call = payload.get("call", {})
        call_id = call.get("id", "")
        
        logger.info(f"Vapi webhook received: type={message_type}, call_id={call_id}")
        
        # 1. Gérer les requêtes d'assistant (assistant-request)
        if message_type == "assistant-request":
            # Vapi demande un assistant - retourner une réponse vide
            # L'assistant est déjà configuré dans Vapi Dashboard
            logger.info("Assistant request - returning empty response")
            return {"assistant": None}
        
        # 2. Traiter uniquement les messages utilisateur avec transcript
        if message_type == "user-message":
            transcript = message.get("content", "")
            
            if not transcript or not call_id:
                logger.warning(f"Missing transcript or call_id in user-message: {payload}")
                return {"status": "no_content"}
            
            logger.info(f"Processing user-message: call_id={call_id}, transcript='{transcript}'")
            
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
        
        # 3. Ignorer les autres types de messages
        # (status-update, conversation-update, assistant.started, end-of-call-report, etc.)
        logger.debug(f"Ignoring message type: {message_type}")
        return {"status": "ok"}
    
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

