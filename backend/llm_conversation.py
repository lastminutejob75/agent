# backend/llm_conversation.py
"""
Mode conversationnel LLM (START uniquement) : réponse naturelle avec placeholders,
validation stricte, fallback FSM. Le LLM ne doit jamais écrire de faits en clair.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from backend.cabinet_data import CabinetData
from backend.placeholders import ALLOWED_PLACEHOLDERS
from backend.response_validator import validate_conv_result, validate_llm_json

logger = logging.getLogger(__name__)

CONV_CONFIDENCE_THRESHOLD = 0.75
CONV_RESPONSE_MAX_LEN = 280


@dataclass
class ConvResult:
    response_text: str
    next_mode: str  # "FSM_BOOKING" | "FSM_FAQ" | "FSM_TRANSFER" | "FSM_FALLBACK"
    extracted: Dict[str, Any]  # {name?, pref?, contact?} optionnel
    confidence: float


class LLMConvClient(Protocol):
    """Interface injectable pour complétion conversationnelle (JSON strict)."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Retourne une chaîne JSON brute (une seule ligne, pas de markdown)."""
        ...


class StubLLMConvClient:
    """Stub pour tests : retourne un JSON fixe ou configurable."""

    def __init__(self, fixed_response: Optional[str] = None):
        self.fixed_response = fixed_response

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if self.fixed_response is not None:
            return self.fixed_response
        return json.dumps({
            "response_text": "Bonjour ! Je peux vous aider pour un rendez-vous ou une question. Souhaitez-vous prendre rendez-vous ?",
            "next_mode": "FSM_BOOKING",
            "extracted": {},
            "confidence": 0.9,
        }, ensure_ascii=False)


def _build_system_prompt(cabinet_data: CabinetData) -> str:
    placeholders_list = ", ".join(sorted(ALLOWED_PLACEHOLDERS))
    return f"""You are a friendly receptionist for {cabinet_data.business_name} ({cabinet_data.business_type}).
You answer in French, naturally and concisely (max {CONV_RESPONSE_MAX_LEN} characters for voice).

CRITICAL OUTPUT CONSTRAINTS:
- response_text MUST NOT contain any digits (0-9), currency symbols (€, $), or specific times/prices/addresses.
- If factual info is needed, use placeholders ONLY: {placeholders_list}
- NEVER promise availability. If user asks availability: ask to take an appointment via FSM.
- NEVER give medical advice. If asked: refuse politely and propose booking or transfer.

Output format: Return ONLY valid JSON. No markdown. No extra text. Single line.

Example:
{{"response_text": "Bonjour ! Je peux vous aider. {{FAQ_HORAIRES}} Souhaitez-vous prendre rendez-vous ?", "next_mode": "FSM_FAQ", "extracted": {{}}, "confidence": 0.86}}

Allowed next_mode: FSM_BOOKING, FSM_FAQ, FSM_TRANSFER, FSM_FALLBACK.
extracted: optional {{"name": "...", "pref": "...", "contact": "..."}} if you can infer from user message."""


def _build_user_prompt(
    state: str,
    user_text: str,
    history: List[Dict[str, str]],
) -> str:
    lines = [f"state: {state}", f"user: {user_text}"]
    if history:
        lines.append("recent turns:")
        for h in history[-6:]:
            lines.append(f"  {h.get('role', '?')}: {h.get('text', '')[:100]}")
    return "\n".join(lines)


def complete_conversation(
    cabinet_data: CabinetData,
    state: str,
    user_text: str,
    history: List[Dict[str, str]],
    client: LLMConvClient,
) -> Optional[ConvResult]:
    """
    Appelle le LLM, parse le JSON, valide ConvResult.
    Retourne ConvResult si valide, None sinon (fallback FSM).
    """
    system = _build_system_prompt(cabinet_data)
    user = _build_user_prompt(state, user_text, history)
    try:
        raw = client.complete(system, user)
    except Exception as e:
        logger.warning("llm_conversation complete error: %s", e)
        return None
    data = validate_llm_json(raw)
    if not data:
        logger.info("llm_conversation: invalid JSON, fallback FSM")
        return None
    if not validate_conv_result(data):
        logger.info("llm_conversation: validation failed (digits/forbidden/placeholder), fallback FSM")
        return None
    extracted = data.get("extracted") or {}
    if not isinstance(extracted, dict):
        extracted = {}
    return ConvResult(
        response_text=data["response_text"],
        next_mode=data["next_mode"],
        extracted=extracted,
        confidence=float(data["confidence"]),
    )
