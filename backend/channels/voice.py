# backend/channels/voice.py
"""
Channel pour la voix via Vapi.

Ce channel gère :
- Les webhooks Vapi (assistant-request, user-message, etc.)
- La transformation des transcripts en ChannelMessage
- Le formatage des réponses pour Vapi
"""

from typing import Optional, Dict, Any
import logging

from fastapi import Request, HTTPException

from backend.channels.base import BaseChannel, ChannelError
from backend.models.message import ChannelMessage, AgentResponse
from backend import prompts

logger = logging.getLogger(__name__)


class VoiceChannel(BaseChannel):
    """Channel pour les conversations vocales via Vapi"""
    
    def __init__(self):
        super().__init__(channel_name="vocal")
    
    async def parse_incoming(self, request: Request) -> Optional[ChannelMessage]:
        """
        Parse les webhooks Vapi.
        
        Vapi envoie plusieurs types de messages :
        - assistant-request : Demande de config assistant (on retourne {})
        - user-message : Message de l'utilisateur (on traite)
        - status-update, end-of-call-report, etc. (on ignore)
        
        Returns:
            ChannelMessage pour les user-message, None pour les autres types
        """
        try:
            payload = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse Vapi webhook: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        message = payload.get("message", {})
        message_type = message.get("type", "")
        call = payload.get("call", {})
        call_id = call.get("id", "")
        
        logger.info(f"Vapi webhook: type={message_type}, call_id={call_id}")
        
        # assistant-request : Vapi demande la config, on retourne {}
        if message_type == "assistant-request":
            logger.info("Assistant request - using default Vapi assistant")
            return None  # Signal pour retourner {} directement
        
        # user-message : Message utilisateur
        if message_type == "user-message":
            transcript = message.get("content", "")
            
            if not transcript or not call_id:
                logger.warning(f"Missing transcript or call_id: {payload}")
                return None
            
            logger.info(f"User message: call_id={call_id}, text='{transcript}'")
            
            return ChannelMessage(
                channel="vocal",
                conversation_id=call_id,
                user_text=transcript,
                metadata={
                    "call": call,
                    "message_type": message_type,
                    "raw_payload": payload
                }
            )
        
        # Autres types : on ignore (status-update, end-of-call-report, etc.)
        logger.debug(f"Ignoring Vapi message type: {message_type}")
        return None
    
    async def format_response(self, response: AgentResponse) -> Dict[str, Any]:
        """
        Formate la réponse pour Vapi.
        
        Vapi attend :
        {
            "results": [
                {"type": "say", "text": "..."}
            ]
        }
        
        Args:
            response: Réponse de l'agent
            
        Returns:
            Payload Vapi
        """
        # Si transfert silencieux, ne rien dire
        if response.silent:
            return {"results": []}
        
        # Réponse normale
        return {
            "results": [{
                "type": "say",
                "text": response.text
            }]
        }
    
    async def validate_webhook(self, request: Request) -> bool:
        """
        Valide que la requête provient de Vapi.
        
        Pour le MVP, on accepte toutes les requêtes.
        En production, on devrait :
        - Vérifier une signature HMAC
        - Valider l'IP source
        - Checker un secret partagé
        
        Returns:
            True (pour le MVP)
        """
        # TODO: Implémenter validation Vapi si nécessaire
        return True
    
    def get_conversation_id(self, request_payload: dict) -> str:
        """Extrait call_id comme conversation_id"""
        call = request_payload.get("call", {})
        return call.get("id", "")


def create_vapi_fallback_response(error_message: Optional[str] = None) -> Dict[str, Any]:
    """
    Crée une réponse de fallback en cas d'erreur.
    
    Args:
        error_message: Message d'erreur optionnel
        
    Returns:
        Payload Vapi avec message d'erreur
    """
    text = error_message or prompts.MSG_VAPI_ERROR
    
    return {
        "results": [{
            "type": "say",
            "text": text
        }]
    }
