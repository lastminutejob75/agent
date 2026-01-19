# backend/models/message.py
"""
Modèles de messages partagés entre tous les canaux.
Ces dataclasses permettent de normaliser la communication entre
les channels et l'engine core.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class ChannelMessage:
    """
    Message normalisé reçu d'un canal de communication.
    
    Tous les channels (vocal, WhatsApp, web, etc.) convertissent
    leur format spécifique en cette structure unifiée.
    """
    channel: str                    # "vocal", "whatsapp", "google_business", "web"
    conversation_id: str            # ID unique de la conversation
    user_text: str                  # Message utilisateur (transcrit si vocal)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validation basique"""
        if not self.channel:
            raise ValueError("channel is required")
        if not self.conversation_id:
            raise ValueError("conversation_id is required")
        
        # Normaliser le texte
        self.user_text = self.user_text.strip()


@dataclass
class AgentResponse:
    """
    Réponse de l'agent à envoyer au client.
    
    L'engine génère des AgentResponse, puis chaque channel
    les transforme dans son format spécifique (Vapi, WhatsApp, SSE, etc.)
    """
    text: str                       # Texte de la réponse
    conversation_id: str            # ID de la conversation
    state: str                      # État de la conversation (START, CONFIRMED, etc.)
    event_type: str = "final"       # "partial", "final", "transfer", "error"
    
    # Metadata optionnelle
    transfer_reason: Optional[str] = None
    silent: bool = False
    slots: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_terminal(self) -> bool:
        """True si c'est un état terminal (conversation terminée)"""
        return self.state in ["CONFIRMED", "TRANSFERRED"]
    
    @property
    def is_transfer(self) -> bool:
        """True si c'est un transfert vers humain"""
        return self.event_type == "transfer" or self.state == "TRANSFERRED"


@dataclass 
class ChannelConfig:
    """
    Configuration spécifique à un canal pour un business.
    Permet de personnaliser le comportement par client.
    """
    channel: str
    enabled: bool = True
    
    # Config spécifique au canal
    phone_number: Optional[str] = None      # Pour vocal/WhatsApp
    webhook_secret: Optional[str] = None    # Pour validation webhooks
    
    # Pricing
    cost_per_message: float = 0.0
    cost_per_minute: float = 0.0
    
    # Limites
    max_messages_per_day: Optional[int] = None
    
    # Features
    enable_voice_mail: bool = False
    enable_attachments: bool = True
    
    metadata: Dict[str, Any] = field(default_factory=dict)
