# backend/channels/whatsapp.py
"""
Canal WhatsApp via Twilio ou Meta API.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import logging

from backend.channels.base import BaseChannel
from backend.models.message import ChannelMessage, ChannelResponse, ChannelType
from backend.engine import ENGINE
from backend import prompts

logger = logging.getLogger(__name__)


class WhatsAppChannel(BaseChannel):
    """
    Implémentation du canal WhatsApp.
    
    Supporte :
    - Twilio WhatsApp API
    - Meta WhatsApp Business API (futur)
    """
    
    channel_type = ChannelType.WHATSAPP
    
    def parse_incoming(self, raw_payload: Dict[str, Any]) -> Optional[ChannelMessage]:
        """
        Parse un webhook Twilio WhatsApp.
        
        Format Twilio :
        - Body: texte du message
        - From: whatsapp:+33612345678
        - To: whatsapp:+33939240575
        - MessageSid: identifiant unique
        """
        # Extraire les données
        body = raw_payload.get("Body", "")
        from_number = raw_payload.get("From", "").replace("whatsapp:", "")
        to_number = raw_payload.get("To", "").replace("whatsapp:", "")
        message_sid = raw_payload.get("MessageSid", "")
        
        if not body or not from_number:
            logger.warning("WhatsAppChannel: Missing body or from_number")
            return None
        
        # Utiliser le numéro comme session_id
        session_id = f"wa_{from_number}"
        
        logger.info(f"WhatsAppChannel: from={from_number}, body={body[:50]}...")
        
        # Marquer la session comme WhatsApp
        session = ENGINE.session_store.get_or_create(session_id)
        session.channel = "whatsapp"
        
        return ChannelMessage(
            channel=self.channel_type,
            session_id=session_id,
            text=body,
            sender_id=from_number,
            raw_payload=raw_payload,
            metadata={
                "to": to_number,
                "message_sid": message_sid
            }
        )
    
    def format_response(self, response: ChannelResponse) -> Dict[str, Any]:
        """
        Formate pour TwiML (Twilio Messaging).
        
        Format TwiML :
        <?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Message>Texte de réponse</Message>
        </Response>
        """
        # Échapper les caractères spéciaux XML
        text = response.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{text}</Message>
</Response>'''
        
        return {"twiml": twiml, "text": response.text}
    
    def get_error_response(self) -> Dict[str, Any]:
        """Réponse en cas d'erreur"""
        return {
            "twiml": '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Désolé, une erreur s'est produite. Veuillez réessayer.</Message>
</Response>''',
            "text": "Désolé, une erreur s'est produite."
        }


# Instance singleton
whatsapp_channel = WhatsAppChannel()
