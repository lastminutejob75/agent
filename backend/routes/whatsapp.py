# backend/routes/whatsapp.py
"""
Routes API pour le canal WhatsApp (Twilio).
Résolution tenant par numéro destinataire (To) → tenant_routing channel=whatsapp.
"""

from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
import logging

from backend.channels.whatsapp import whatsapp_channel
from backend.channels.base import ChannelError
from backend.models.message import AgentResponse
from backend.engine import ENGINE
from backend.tenant_routing import resolve_tenant_from_whatsapp, current_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.post("/webhook")
async def whatsapp_webhook(request: Request):
    """
    Webhook pour Twilio WhatsApp.
    
    Reçoit les messages WhatsApp et retourne du TwiML.
    """
    try:
        # Valider le webhook (optionnel si TWILIO_AUTH_TOKEN configuré)
        if not await whatsapp_channel.validate_webhook(request):
            logger.warning("WhatsApp webhook validation failed")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        # Parser le message entrant
        message = await whatsapp_channel.parse_incoming(request)
        
        # Si None, c'est un message à ignorer (média uniquement, etc.)
        if message is None:
            return Response(
                content=whatsapp_channel.get_media_response()["twiml"],
                media_type="application/xml"
            )
        
        # Vérifier si c'est un message avec médias
        if message.metadata.get("num_media", 0) > 0 and not message.user_text:
            return Response(
                content=whatsapp_channel.get_media_response()["twiml"],
                media_type="application/xml"
            )
        
        # Résolution tenant par numéro destinataire (To = WhatsApp Business)
        to_number = message.metadata.get("to_number") or ""
        try:
            tenant_id = resolve_tenant_from_whatsapp(to_number)
        except HTTPException:
            raise
        session = ENGINE.session_store.get(message.conversation_id)
        if session is not None:
            session.tenant_id = tenant_id
        request.state.tenant_id = tenant_id
        current_tenant_id.set(str(tenant_id))
        
        # Traiter via l'engine
        events = ENGINE.handle_message(message.conversation_id, message.user_text)
        
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
                text="Je n'ai pas compris. Pouvez-vous reformuler ?",
                conversation_id=message.conversation_id,
                state="START"
            )
        
        # Formater pour TwiML
        formatted = await whatsapp_channel.format_response(response)
        
        return Response(
            content=formatted["twiml"],
            media_type="application/xml"
        )
        
    except ChannelError as e:
        logger.error(f"WhatsApp channel error: {e.message}")
        return Response(
            content=whatsapp_channel.get_error_response()["twiml"],
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}", exc_info=True)
        return Response(
            content=whatsapp_channel.get_error_response()["twiml"],
            media_type="application/xml"
        )


@router.get("/health")
async def whatsapp_health():
    """Health check pour le canal WhatsApp"""
    return {
        "status": "ok",
        "service": "whatsapp",
        "channel": "twilio",
        "message": "WhatsApp webhook is ready"
    }


@router.get("/test")
async def whatsapp_test():
    """
    Endpoint de test pour vérifier la configuration.
    """
    import os
    return {
        "status": "ok",
        "channel": whatsapp_channel.channel_name,
        "engine": "ready",
        "twilio_configured": bool(os.getenv("TWILIO_AUTH_TOKEN")),
        "endpoints": {
            "webhook": "/api/whatsapp/webhook",
            "health": "/api/whatsapp/health"
        }
    }
