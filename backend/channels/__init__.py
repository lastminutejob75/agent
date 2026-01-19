"""Channels package - Gestion multi-canal (Voice, WhatsApp, etc.)"""

from backend.channels.base import BaseChannel
from backend.channels.voice import VoiceChannel

__all__ = ["BaseChannel", "VoiceChannel"]
