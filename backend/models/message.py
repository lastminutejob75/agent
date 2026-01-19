# backend/models/message.py
"""
Modèles de messages unifiés pour tous les canaux.
Permet de normaliser les entrées/sorties entre Voice, WhatsApp, Web, etc.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime


class ChannelType(Enum):
    """Types de canaux supportés"""
    VOICE = "voice"
    WHATSAPP = "whatsapp"
    WEB = "web"
    SMS = "sms"


@dataclass
class ChannelMessage:
    """
    Message entrant normalisé depuis n'importe quel canal.
    
    Attributes:
        channel: Type de canal (voice, whatsapp, web, sms)
        session_id: Identifiant unique de session/conversation
        text: Texte du message utilisateur
        sender_id: Identifiant de l'expéditeur (numéro tel, user_id, etc.)
        raw_payload: Payload brut du canal (pour debug/audit)
        timestamp: Horodatage du message
        metadata: Données supplémentaires spécifiques au canal
    """
    channel: ChannelType
    session_id: str
    text: str
    sender_id: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelResponse:
    """
    Réponse normalisée à envoyer vers n'importe quel canal.
    
    Attributes:
        text: Texte de la réponse
        action: Action à effectuer (say, transfer, end_call, etc.)
        session_id: Identifiant de session
        metadata: Données supplémentaires pour le canal
        end_conversation: Si True, termine la conversation
    """
    text: str
    action: str = "say"  # say, transfer, end_call
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    end_conversation: bool = False
    
    def to_vapi_format(self) -> Dict[str, Any]:
        """Convertit en format Vapi"""
        if self.action == "transfer":
            return {
                "results": [{
                    "type": "transfer",
                    "destination": self.metadata.get("destination", "")
                }]
            }
        return {
            "results": [{
                "type": "say",
                "text": self.text
            }]
        }
    
    def to_whatsapp_format(self) -> Dict[str, Any]:
        """Convertit en format WhatsApp (Twilio/Meta)"""
        return {
            "body": self.text,
            "to": self.metadata.get("to", ""),
            "from": self.metadata.get("from", "")
        }
