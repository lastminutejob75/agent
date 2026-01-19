# backend/routes/voice.py
"""
Routes API pour le canal Voice (Vapi).
"""

from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

from backend.channels.voice import VoiceChannel, create_vapi_fallback_response
from backend.channels.base import ChannelError
from backend.models.message import AgentResponse
from backend.engine import ENGINE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vapi", tags=["voice"])

# Instance du channel
voice_channel = VoiceChannel()


@router.post("/webhook")
async def voice_webhook(request: Request):
    """
    Webhook principal pour Vapi.
    
    Reçoit les événements Vapi et retourne les réponses.
    """
    try:
        # Valider le webhook
        if not await voice_channel.validate_webhook(request):
            logger.warning("Voice webhook validation failed")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        # Parser le message entrant
        message = await voice_channel.parse_incoming(request)
        
        # Si None, c'est un message à ignorer (assistant-request, etc.)
        if message is None:
            return JSONResponse(content={})
        
        # Traiter via l'engine
        events = ENGINE.handle_message(message.conversation_id, message.user_text)
        
        # Marquer la session comme vocale
        session = ENGINE.session_store.get_or_create(message.conversation_id)
        session.channel = "vocal"
        
        # Construire la réponse
        if events and len(events) > 0:
            event = events[0]
            response = AgentResponse(
                text=event.text,
                conversation_id=message.conversation_id,
                state=event.conv_state or "START",
                event_type=event.type,
                transfer_reason=event.transfer_reason,
                silent=event.silent
            )
        else:
            response = AgentResponse(
                text="Je n'ai pas compris. Pouvez-vous répéter ?",
                conversation_id=message.conversation_id,
                state="START"
            )
        
        # Formater pour Vapi
        formatted = await voice_channel.format_response(response)
        return JSONResponse(content=formatted)
        
    except HTTPException:
        raise
        
    except ChannelError as e:
        logger.error(f"Voice channel error: {e.message}")
        return JSONResponse(content=create_vapi_fallback_response())
        
    except Exception as e:
        logger.error(f"Voice webhook error: {e}", exc_info=True)
        return JSONResponse(content=create_vapi_fallback_response())


@router.get("/health")
async def voice_health():
    """Health check pour le canal Voice"""
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
    return {
        "status": "ok",
        "channel": voice_channel.channel_name,
        "engine": "ready",
        "endpoints": {
            "webhook": "/api/vapi/webhook",
            "health": "/api/vapi/health"
        }
    }
