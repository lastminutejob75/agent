# backend/channels/voice.py
"""
Canal Voice pour Vapi.
Gère les appels téléphoniques via l'intégration Vapi.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import logging

from backend.channels.base import BaseChannel
from backend.models.message import ChannelMessage, ChannelResponse, ChannelType
from backend.engine import ENGINE
from backend import prompts

logger = logging.getLogger(__name__)


class VoiceChannel(BaseChannel):
    """
    Implémentation du canal Voice (Vapi).
    
    Gère :
    - assistant-request : retourne {} pour utiliser l'assistant Vapi
    - user-message : traite via ENGINE et retourne la réponse
    - autres types : ignore
    """
    
    channel_type = ChannelType.VOICE
    
    def parse_incoming(self, raw_payload: Dict[str, Any]) -> Optional[ChannelMessage]:
        """
        Parse un payload Vapi vers ChannelMessage.
        
        Formats supportés :
        - message.type = "user-message" + message.content
        - message.type = "assistant-request" → retourne None (ignoré)
        """
        message = raw_payload.get("message", {})
        message_type = message.get("type", "")
        call = raw_payload.get("call", {})
        call_id = call.get("id", "")
        
        logger.info(f"VoiceChannel: type={message_type}, call_id={call_id}")
        
        # assistant-request : on ne traite pas, juste signal pour Vapi
        if message_type == "assistant-request":
            return None
        
        # user-message : extraire le transcript
        if message_type == "user-message":
            transcript = message.get("content", "")
            
            if not transcript or not call_id:
                logger.warning(f"VoiceChannel: Missing transcript or call_id")
                return None
            
            # Marquer la session comme vocale
            session = ENGINE.session_store.get_or_create(call_id)
            session.channel = "vocal"
            
            return ChannelMessage(
                channel=self.channel_type,
                session_id=call_id,
                text=transcript,
                sender_id=call.get("from"),
                raw_payload=raw_payload
            )
        
        # Autres types (status-update, conversation-update, etc.) → ignorer
        logger.debug(f"VoiceChannel: Ignoring message type {message_type}")
        return None
    
    def format_response(self, response: ChannelResponse) -> Dict[str, Any]:
        """
        Formate une réponse pour Vapi.
        
        Format Vapi :
        {
            "results": [{"type": "say", "text": "..."}]
        }
        """
        return response.to_vapi_format()
    
    def get_ignore_response(self) -> Dict[str, Any]:
        """Réponse pour les messages ignorés (assistant-request, etc.)"""
        return {}
    
    def get_error_response(self) -> Dict[str, Any]:
        """Réponse en cas d'erreur"""
        return {
            "results": [{
                "type": "say",
                "text": prompts.MSG_VAPI_ERROR
            }]
        }
    
    def get_fallback_response(self) -> Dict[str, Any]:
        """Réponse fallback si pas de réponse de l'engine"""
        return {
            "results": [{
                "type": "say",
                "text": prompts.MSG_VAPI_NO_UNDERSTANDING
            }]
        }


# Instance singleton pour utilisation dans les routes
voice_channel = VoiceChannel()
