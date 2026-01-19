# backend/channels/base.py
"""
Classe de base abstraite pour tous les canaux.
Définit l'interface commune que chaque canal doit implémenter.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from backend.models.message import ChannelMessage, ChannelResponse, ChannelType
from backend.engine import ENGINE


class BaseChannel(ABC):
    """
    Interface abstraite pour les canaux de communication.
    
    Chaque canal (Voice, WhatsApp, Web, SMS) doit hériter de cette classe
    et implémenter les méthodes abstraites.
    """
    
    channel_type: ChannelType
    
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
    def format_response(self, response: ChannelResponse) -> Dict[str, Any]:
        """
        Formate une ChannelResponse vers le format spécifique du canal.
        
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
        events = ENGINE.handle_message(message.session_id, message.text)
        
        # 3. Construire la réponse
        if events and len(events) > 0:
            response = ChannelResponse(
                text=events[0].text,
                action="transfer" if events[0].type == "transfer" else "say",
                session_id=message.session_id,
                end_conversation=events[0].conv_state in ["CONFIRMED", "TRANSFERRED"]
            )
        else:
            response = ChannelResponse(
                text="Je n'ai pas compris. Pouvez-vous répéter ?",
                session_id=message.session_id
            )
        
        # 4. Formater pour le canal
        return self.format_response(response)
    
    def get_ignore_response(self) -> Dict[str, Any]:
        """Réponse par défaut pour les messages ignorés"""
        return {"status": "ok"}
