# backend/routes/voice.py
"""
Routes API pour le canal Voice (Vapi).
Utilise VoiceChannel pour traiter les webhooks.
"""

from __future__ import annotations
from fastapi import APIRouter, Request
import logging

from backend.channels.voice import voice_channel
from backend import prompts

logger = logging.getLogger(__name__)

# Router avec le même préfixe que l'ancien vapi.py pour rétrocompatibilité
router = APIRouter(prefix="/api/vapi", tags=["voice"])


@router.post("/webhook")
async def voice_webhook(request: Request):
    """
    Webhook principal pour Vapi.
    Délègue le traitement à VoiceChannel.
    """
    try:
        payload = await request.json()
        
        # Utiliser VoiceChannel pour traiter
        response = voice_channel.process_message(payload)
        
        return response
        
    except Exception as e:
        logger.error(f"Voice webhook error: {e}", exc_info=True)
        return voice_channel.get_error_response()


@router.get("/health")
async def voice_health():
    """Health check pour le canal Voice."""
    return {
        "status": "ok",
        "service": "voice",
        "channel": "vapi",
        "message": "Voice webhook is ready"
    }


@router.get("/test")
async def voice_test():
    """
    Endpoint de test pour vérifier la configuration.
    """
    try:
        from backend.engine import ENGINE
        
        # Tester que l'engine fonctionne
        test_session = ENGINE.session_store.get_or_create("test_voice")
        test_session.channel = "vocal"
        
        events = ENGINE.handle_message("test_voice", "bonjour")
        
        return {
            "status": "ok",
            "test_response": events[0].text if events else "No response",
            "message": "Voice channel is working correctly"
        }
    except Exception as e:
        logger.error(f"Voice test failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }
