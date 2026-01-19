# backend/channels/base.py
"""
Classe de base abstraite pour tous les canaux.
Définit l'interface commune que chaque canal doit implémenter.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from backend.models.message import ChannelMessage, AgentResponse
from backend.engine import ENGINE


class BaseChannel(ABC):
    """
    Interface abstraite pour les canaux de communication.
    
    Chaque canal (Voice, WhatsApp, Web, SMS) doit hériter de cette classe
    et implémenter les méthodes abstraites.
    """
    
    channel_name: str  # "vocal", "whatsapp", "google_business", "web"
    
    @abstractmethod
    def parse_incoming(self, raw_payload: Dict[str, Any]) -> Optional[ChannelMessage]:
        """
        Parse le payload brut du canal vers un ChannelMessage normalisé.
        
        Args:
            raw_payload: Données brutes reçues du webhook/API
            
        Returns:
            ChannelMessage normalisé ou None si le message doit être ignoré
        """
        pass
    
    @abstractmethod
    def format_response(self, response: AgentResponse) -> Dict[str, Any]:
        """
        Formate une AgentResponse vers le format spécifique du canal.
        
        Args:
            response: Réponse normalisée à envoyer
            
        Returns:
            Payload formaté pour le canal
        """
        pass
    
    def process_message(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traite un message entrant et retourne la réponse formatée.
        
        Pipeline :
        1. Parse le payload brut → ChannelMessage
        2. Passe au moteur de conversation (ENGINE)
        3. Formate la réponse → format canal
        
        Args:
            raw_payload: Données brutes du webhook
            
        Returns:
            Réponse formatée pour le canal
        """
        # 1. Parser le message entrant
        message = self.parse_incoming(raw_payload)
        
        if message is None:
            # Message ignoré (status update, etc.)
            return self.get_ignore_response()
        
        # 2. Traiter via l'engine
        events = ENGINE.handle_message(message.conversation_id, message.user_text)
        
        # 3. Construire la réponse
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
        
        # 4. Formater pour le canal
        return self.format_response(response)
    
    def get_ignore_response(self) -> Dict[str, Any]:
        """Réponse par défaut pour les messages ignorés"""
        return {"status": "ok"}
