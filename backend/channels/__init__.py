"""Channels package - Gestion multi-canal (Voice, WhatsApp, etc.)"""

from backend.channels.base import BaseChannel, ChannelError
from backend.channels.voice import VoiceChannel, create_vapi_fallback_response
from backend.channels.whatsapp import WhatsAppChannel, whatsapp_channel

__all__ = [
    "BaseChannel",
    "ChannelError",
    "VoiceChannel", 
    "create_vapi_fallback_response",
    "WhatsAppChannel", 
    "whatsapp_channel"
]
