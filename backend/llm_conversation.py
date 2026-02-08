# backend/llm_conversation.py
"""
LLM Client interface for conversational mode.

Provides an injectable interface for LLM completion.
Includes a stub implementation for testing.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from backend.cabinet_data import CabinetData, DEFAULT_CABINET_DATA
from backend.placeholders import ALLOWED_PLACEHOLDERS, get_placeholder_system_instructions


@dataclass
class ConvResult:
    """
    Result from conversational LLM.

    Attributes:
        response_text: Natural response (may contain placeholders)
        next_mode: Where to route next (FSM_BOOKING, FSM_FAQ, FSM_TRANSFER, FSM_FALLBACK)
        extracted: Optional extracted entities (name, pref, contact)
        confidence: Model's confidence in the response (0.0 to 1.0)
        raw_output: Raw LLM output for debugging
    """
    response_text: str
    next_mode: str
    extracted: Optional[Dict[str, str]]
    confidence: float
    raw_output: str = ""


class LLMClient(ABC):
    """
    Abstract interface for LLM completion.
    Allows dependency injection for testing.
    """

    @abstractmethod
    def complete(
        self,
        user_message: str,
        conversation_history: List[Tuple[str, str]],
        state: str,
        cabinet_data: CabinetData,
    ) -> str:
        """
        Generate a completion from the LLM.

        Args:
            user_message: Current user message
            conversation_history: List of (role, text) tuples (max 6 turns)
            state: Current conversation state (e.g., "START")
            cabinet_data: Business information

        Returns:
            Raw JSON string from LLM
        """
        pass


class StubLLMClient(LLMClient):
    """
    Stub LLM client for testing.
    Returns predefined responses based on input patterns.
    """

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        """
        Initialize with optional predefined responses.

        Args:
            responses: Dict mapping user message patterns to JSON responses
        """
        self._responses = responses or {}
        self._default_response = """{
  "response_text": "Bonjour ! Je suis l'assistant du {business_name}. Comment puis-je vous aider ?",
  "next_mode": "FSM_FALLBACK",
  "extracted": null,
  "confidence": 0.85
}"""

    def set_response(self, pattern: str, response: str) -> None:
        """Set a response for a message pattern."""
        self._responses[pattern] = response

    def set_default_response(self, response: str) -> None:
        """Set the default response."""
        self._default_response = response

    def complete(
        self,
        user_message: str,
        conversation_history: List[Tuple[str, str]],
        state: str,
        cabinet_data: CabinetData,
    ) -> str:
        """Return predefined response based on user message."""
        msg_lower = user_message.lower()

        # Check for pattern matches
        for pattern, response in self._responses.items():
            if pattern.lower() in msg_lower:
                return response

        return self._default_response


def build_system_prompt(cabinet_data: CabinetData, state: str) -> str:
    """
    Build the system prompt for conversational mode.

    Args:
        cabinet_data: Business information
        state: Current conversation state

    Returns:
        Complete system prompt string
    """
    placeholders_list = ", ".join(sorted(ALLOWED_PLACEHOLDERS))

    return f"""Tu es l'assistant vocal du {cabinet_data.business_name} ({cabinet_data.business_type}).

RÔLE:
- Accueillir chaleureusement les appelants
- Répondre aux questions simples via placeholders
- Orienter vers la prise de rendez-vous
- Transférer si hors scope

ÉTAT ACTUEL: {state}

{get_placeholder_system_instructions()}

FORMAT DE SORTIE (JSON STRICT):
Retourne UNIQUEMENT du JSON valide. Pas de markdown. Pas de texte avant/après.

{{
  "response_text": "Texte naturel avec {{FAQ_HORAIRES}} si besoin",
  "next_mode": "FSM_BOOKING" | "FSM_FAQ" | "FSM_TRANSFER" | "FSM_FALLBACK",
  "extracted": {{"name": "..."}},  // ou null
  "confidence": 0.85
}}

RÈGLES DE ROUTAGE (next_mode):
- FSM_BOOKING: Si l'utilisateur veut un rendez-vous
- FSM_FAQ: Si question simple répondue par placeholder
- FSM_TRANSFER: Si hors scope, médical, ou complexe
- FSM_FALLBACK: Si incertain

TON:
- Naturel, chaleureux, parisien
- Phrases courtes (max 280 caractères)
- Jamais de chiffres dans response_text
"""


def build_user_prompt(
    user_message: str,
    conversation_history: List[Tuple[str, str]],
    max_history: int = 6,
) -> str:
    """
    Build the user prompt including conversation history.

    Args:
        user_message: Current user message
        conversation_history: List of (role, text) tuples
        max_history: Maximum number of history turns to include

    Returns:
        User prompt string
    """
    parts = []

    # Add recent history
    recent = conversation_history[-max_history:] if len(conversation_history) > max_history else conversation_history
    if recent:
        parts.append("Historique récent:")
        for role, text in recent:
            speaker = "Utilisateur" if role == "user" else "Assistant"
            parts.append(f"- {speaker}: {text[:100]}...")
        parts.append("")

    parts.append(f"Message actuel: {user_message}")
    parts.append("")
    parts.append("Réponds en JSON uniquement.")

    return "\n".join(parts)
