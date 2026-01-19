# backend/channels/voice.py
"""
Canal Voice pour Vapi.
Gère les appels téléphoniques via l'intégration Vapi.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import logging
import os

from fastapi import Request

from backend.channels.base import BaseChannel, ChannelError
from backend.models.message import ChannelMessage, AgentResponse
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
    
    def __init__(self):
        super().__init__("vocal")
    
    async def parse_incoming(self, request: Request) -> Optional[ChannelMessage]:
        """
        Parse un payload Vapi vers ChannelMessage.
        
        Formats supportés :
        - message.type = "user-message" + message.content
        - message.type = "assistant-request" → retourne None (ignoré)
        """
        try:
            raw_payload = await request.json()
        except Exception as e:
            logger.error(f"VoiceChannel: Failed to parse JSON: {e}")
            raise ChannelError("Invalid JSON payload", self.channel_name)
        
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
                channel=self.channel_name,
                conversation_id=call_id,
                user_text=transcript,
                metadata={
                    "from_number": call.get("from"),
                    "to_number": call.get("to"),
                    "raw_type": message_type,
                    "raw_payload": raw_payload
                }
            )
        
        # Autres types (status-update, conversation-update, etc.) → ignorer
        logger.debug(f"VoiceChannel: Ignoring message type {message_type}")
        return None
    
    async def format_response(self, response: AgentResponse) -> Dict[str, Any]:
        """
        Formate une réponse pour Vapi.
        
        Format Vapi :
        {
            "results": [{"type": "say", "text": "..."}]
        }
        """
        if response.is_transfer:
            return {
                "results": [{
                    "type": "transfer",
                    "destination": response.metadata.get("destination", "")
                }]
            }
        
        return {
            "results": [{
                "type": "say",
                "text": response.text
            }]
        }
    
    async def validate_webhook(self, request: Request) -> bool:
        """
        Valide le webhook Vapi.
        
        Pour l'instant, accepte tout. En production, vérifier :
        - Header X-Vapi-Secret
        - Signature HMAC
        """
        # TODO: Implémenter validation avec VAPI_WEBHOOK_SECRET
        secret = os.getenv("VAPI_WEBHOOK_SECRET")
        if not secret:
            # Pas de secret configuré, accepter tout
            return True
        
        # Vérifier le header
        request_secret = request.headers.get("X-Vapi-Secret", "")
        return request_secret == secret
    
    def get_conversation_id(self, request_payload: dict) -> str:
        """Extrait l'ID de conversation Vapi (call.id)"""
        return request_payload.get("call", {}).get("id", "")
    
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
