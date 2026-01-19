# backend/routes/whatsapp.py
"""
Routes API pour le canal WhatsApp (Twilio).
"""

from __future__ import annotations
from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
import logging

from backend.channels.whatsapp import whatsapp_channel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.post("/webhook")
async def whatsapp_webhook(
    Body: str = Form(""),
    From: str = Form(""),
    To: str = Form(""),
    MessageSid: str = Form(""),
    AccountSid: str = Form(""),
    NumMedia: str = Form("0")
):
    """
    Webhook pour Twilio WhatsApp.
    Reçoit les messages et répond en TwiML.
    """
    try:
        payload = {
            "Body": Body,
            "From": From,
            "To": To,
            "MessageSid": MessageSid,
            "AccountSid": AccountSid,
            "NumMedia": NumMedia
        }
        
        logger.info(f"WhatsApp webhook received: from={From}")
        
        # Ignorer les messages média pour l'instant
        if int(NumMedia) > 0:
            return Response(
                content='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Désolé, je ne peux pas traiter les images ou fichiers pour le moment. Envoyez-moi un message texte.</Message>
</Response>''',
                media_type="application/xml"
            )
        
        # Traiter le message
        response = whatsapp_channel.process_message(payload)
        
        # Retourner TwiML
        return Response(
            content=response.get("twiml", ""),
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}", exc_info=True)
        return Response(
            content='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Désolé, une erreur s'est produite. Veuillez réessayer.</Message>
</Response>''',
            media_type="application/xml"
        )


@router.get("/health")
async def whatsapp_health():
    """Health check pour WhatsApp."""
    return {
        "status": "ok",
        "service": "whatsapp",
        "channel": "twilio",
        "message": "WhatsApp webhook is ready"
    }
