# backend/channels/whatsapp.py
"""
Canal WhatsApp via Twilio ou Meta API.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import logging
import os
import hmac
import hashlib
from urllib.parse import parse_qs

from fastapi import Request

from backend.channels.base import BaseChannel, ChannelError
from backend.models.message import ChannelMessage, AgentResponse
from backend.engine import ENGINE

logger = logging.getLogger(__name__)


class WhatsAppChannel(BaseChannel):
    """
    Implémentation du canal WhatsApp via Twilio.
    
    Supporte :
    - Twilio WhatsApp API
    - Meta WhatsApp Business API (futur)
    """
    
    def __init__(self):
        super().__init__("whatsapp")
    
    async def parse_incoming(self, request: Request) -> Optional[ChannelMessage]:
        """
        Parse un webhook Twilio WhatsApp.
        
        Format Twilio (form-encoded) :
        - Body: texte du message
        - From: whatsapp:+33612345678
        - To: whatsapp:+33939240575
        - MessageSid: identifiant unique
        - NumMedia: nombre de médias attachés
        """
        try:
            # Twilio envoie en form-urlencoded
            body_bytes = await request.body()
            form_data = parse_qs(body_bytes.decode("utf-8"))
            
            # Extraire les valeurs (parse_qs retourne des listes)
            raw_payload = {k: v[0] if v else "" for k, v in form_data.items()}
        except Exception as e:
            logger.error(f"WhatsAppChannel: Failed to parse form data: {e}")
            raise ChannelError("Invalid form data", self.channel_name)
        
        # Extraire les données
        body = raw_payload.get("Body", "")
        from_number = raw_payload.get("From", "").replace("whatsapp:", "")
        to_number = raw_payload.get("To", "").replace("whatsapp:", "")
        message_sid = raw_payload.get("MessageSid", "")
        num_media = int(raw_payload.get("NumMedia", "0"))
        
        # Ignorer les messages avec médias uniquement
        if num_media > 0 and not body:
            logger.info(f"WhatsAppChannel: Ignoring media-only message from {from_number}")
            return None
        
        if not body or not from_number:
            logger.warning("WhatsAppChannel: Missing body or from_number")
            return None
        
        # Utiliser le numéro comme conversation_id
        conversation_id = f"wa_{from_number}"
        
        logger.info(f"WhatsAppChannel: from={from_number}, body={body[:50]}...")
        
        # Marquer la session comme WhatsApp
        session = ENGINE.session_store.get_or_create(conversation_id)
        session.channel = "whatsapp"
        
        return ChannelMessage(
            channel=self.channel_name,
            conversation_id=conversation_id,
            user_text=body,
            metadata={
                "from_number": from_number,
                "to_number": to_number,
                "message_sid": message_sid,
                "num_media": num_media,
                "raw_payload": raw_payload
            }
        )
    
    async def format_response(self, response: AgentResponse) -> Dict[str, Any]:
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
    
    async def validate_webhook(self, request: Request) -> bool:
        """
        Valide la signature Twilio.
        
        Twilio signe les webhooks avec le header X-Twilio-Signature.
        """
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        if not auth_token:
            # Pas de token configuré, accepter tout (dev mode)
            logger.warning("WhatsAppChannel: No TWILIO_AUTH_TOKEN, skipping validation")
            return True
        
        # Récupérer la signature
        signature = request.headers.get("X-Twilio-Signature", "")
        if not signature:
            logger.warning("WhatsAppChannel: Missing X-Twilio-Signature header")
            return False
        
        # Construire l'URL complète
        url = str(request.url)
        
        # Récupérer les params POST
        body_bytes = await request.body()
        params = parse_qs(body_bytes.decode("utf-8"))
        sorted_params = "".join(f"{k}{params[k][0]}" for k in sorted(params.keys()))
        
        # Calculer la signature attendue
        data = url + sorted_params
        expected_sig = hmac.new(
            auth_token.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha1
        ).digest()
        
        import base64
        expected_sig_b64 = base64.b64encode(expected_sig).decode("utf-8")
        
        return hmac.compare_digest(signature, expected_sig_b64)
    
    def get_conversation_id(self, request_payload: dict) -> str:
        """Extrait l'ID de conversation (numéro WhatsApp)"""
        from_number = request_payload.get("From", "").replace("whatsapp:", "")
        return f"wa_{from_number}"
    
    def get_error_response(self) -> Dict[str, Any]:
        """Réponse en cas d'erreur"""
        return {
            "twiml": '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Désolé, une erreur s'est produite. Veuillez réessayer.</Message>
</Response>''',
            "text": "Désolé, une erreur s'est produite."
        }
    
    def get_media_response(self) -> Dict[str, Any]:
        """Réponse pour les messages avec médias non supportés"""
        return {
            "twiml": '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Désolé, je ne peux pas traiter les images ou fichiers pour le moment. Envoyez-moi un message texte.</Message>
</Response>''',
            "text": "Désolé, je ne peux pas traiter les images."
        }


# Instance singleton
whatsapp_channel = WhatsAppChannel()
