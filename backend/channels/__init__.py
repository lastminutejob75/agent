"""Channels package - Gestion multi-canal (Voice, WhatsApp, etc.)"""

from backend.channels.base import BaseChannel, ChannelError
from backend.channels.voice import VoiceChannel, voice_channel
from backend.channels.whatsapp import WhatsAppChannel, whatsapp_channel

__all__ = [
    "BaseChannel",
    "ChannelError",
    "VoiceChannel", 
    "voice_channel",
    "WhatsAppChannel", 
    "whatsapp_channel"
]
