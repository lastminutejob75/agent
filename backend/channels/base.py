# backend/channels/base.py
"""
Interface de base pour tous les canaux de communication.

Tous les channels (VoiceChannel, WhatsAppChannel, etc.) héritent
de cette classe et implémentent les méthodes abstraites.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from fastapi import Request

from backend.models.message import ChannelMessage, AgentResponse


class BaseChannel(ABC):
    """
    Classe de base pour tous les channels.
    
    Responsabilités :
    - Parser le format d'entrée du canal (Vapi, WhatsApp, etc.)
    - Normaliser en ChannelMessage
    - Transformer AgentResponse dans le format de sortie du canal
    """
    
    def __init__(self, channel_name: str):
        self.channel_name = channel_name
    
    @abstractmethod
    async def parse_incoming(self, request: Request) -> Optional[ChannelMessage]:
        """
        Parse une requête HTTP entrante et la transforme en ChannelMessage.
        
        Args:
            request: Requête FastAPI brute
            
        Returns:
            ChannelMessage si le message est valide, None sinon
            
        Raises:
            HTTPException si le format est invalide
        """
        pass
    
    @abstractmethod
    async def format_response(self, response: AgentResponse) -> Dict[str, Any]:
        """
        Transforme une AgentResponse dans le format attendu par le canal.
        
        Args:
            response: Réponse de l'agent
            
        Returns:
            Dict à retourner comme réponse HTTP (JSON)
        """
        pass
    
    @abstractmethod
    async def validate_webhook(self, request: Request) -> bool:
        """
        Valide que la requête provient bien du service (Vapi, WhatsApp, etc.)
        
        Args:
            request: Requête à valider
            
        Returns:
            True si valide, False sinon
        """
        pass
    
    def get_conversation_id(self, request_payload: dict) -> str:
        """
        Extrait l'ID de conversation depuis le payload.
        Peut être overridé par les sous-classes.
        
        Args:
            request_payload: Payload parsé de la requête
            
        Returns:
            ID de conversation (unique et stable pour cette conversation)
        """
        raise NotImplementedError("Subclass must implement get_conversation_id")


class ChannelError(Exception):
    """Exception levée par les channels en cas d'erreur"""
    
    def __init__(self, message: str, channel: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.channel = channel
        self.details = details or {}
        super().__init__(self.message)
