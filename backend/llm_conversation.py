# backend/llm_conversation.py
"""
Mode conversationnel LLM (START uniquement) : réponse naturelle avec placeholders,
validation stricte, fallback FSM. Le LLM ne doit jamais écrire de faits en clair.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

from backend.cabinet_data import CabinetData
from backend.placeholders import ALLOWED_PLACEHOLDERS
from backend.response_validator import validate_conv_result, validate_llm_json

logger = logging.getLogger(__name__)

CONV_RESPONSE_MAX_LEN = 280

# NOTE:
# The confidence threshold is enforced by backend/conversational_engine.py via
# config.CONVERSATIONAL_MIN_CONFIDENCE (single source of truth).
# Keep llm_conversation.py free of rollout/confidence policy.


@dataclass
class ConvResult:
    """Result from conversational LLM."""
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


class AnthropicConvClient:
    """Client Anthropic (Claude) pour le mode conversationnel P0. Conforme à LLMConvClient."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514", timeout_sec: float = 15.0):
        self._api_key = (api_key or os.getenv("ANTHROPIC_API_KEY", "")).strip()
        self._model = model
        self._timeout_sec = timeout_sec

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY required for AnthropicConvClient")
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self._api_key)
            msg = client.messages.create(
                model=self._model,
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                timeout=self._timeout_sec,
            )
            out = ""
            for block in getattr(msg, "content", []):
                if getattr(block, "type", None) == "text":
                    out += getattr(block, "text", "") or ""
            return (out.strip() or "").replace("\n", " ").replace("\r", " ")
        except Exception as e:
            logger.warning("AnthropicConvClient complete error: %s", e)
            raise


def get_default_conv_llm_client():  # -> LLMConvClient
    """Retourne AnthropicConvClient si ANTHROPIC_API_KEY est défini, sinon StubLLMConvClient."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        try:
            return AnthropicConvClient(api_key=api_key)
        except Exception as e:
            logger.warning("get_default_conv_llm_client: fallback to stub: %s", e)
    return StubLLMConvClient()


def _build_system_prompt(cabinet_data: CabinetData) -> str:
    placeholders_list = ", ".join(sorted(ALLOWED_PLACEHOLDERS))
    return f"""You are a friendly receptionist for {cabinet_data.business_name} ({cabinet_data.business_type}).
You answer in French, naturally and concisely (max {CONV_RESPONSE_MAX_LEN} characters for voice).

CRITICAL OUTPUT CONSTRAINTS:
- response_text MUST NOT contain any digits (0-9), currency symbols (€, $), or specific times/prices/addresses.
- If factual info is needed, use placeholders ONLY: {placeholders_list}
- NEVER promise availability. If user asks availability: ask to take an appointment via FSM.
- NEVER give medical advice. If asked: refuse politely and propose booking or transfer.

ROUTING PRIORITY (MUST FOLLOW):
0) OFF-TOPIC FIRST: If the user message is clearly unrelated to the medical practice (e.g. pizza, car, weather, shopping, food order, random request), set next_mode="FSM_FALLBACK". Reply with a short polite redirect: you are the practice assistant, you can help with appointment or questions. Do NOT use FSM_FAQ and do NOT use any {{FAQ_...}} placeholder for off-topic messages (that would show wrong factual info like prices).
1) If the user message contains ANY appointment intent (rdv, rendez-vous, consulter, venir vous voir, prendre un créneau, réserver),
   then set next_mode="FSM_BOOKING" even if the message also contains off-topic content.
   In response_text: ignore the off-topic request, redirect politely to booking, and ask the next required booking question (usually the name).
2) If the user asks a factual cabinet question (hours/address/prices/payment/cancel/duration), set next_mode="FSM_FAQ"
   and use EXACTLY ONE placeholder {{FAQ_...}}. Do not add facts outside placeholders. Do NOT use FSM_FAQ for off-topic (see 0).
3) Use next_mode="FSM_FALLBACK" if you cannot produce a safe response under the constraints (no digits, no facts, no medical advice), or when the request is off-topic (see 0).

EXAMPLES:
- Off-topic (pizza only): User "je veux une pizza" → next_mode=FSM_FALLBACK. Example: {{"response_text":"Désolé, je suis l'assistant du cabinet. Je peux vous aider pour un rendez-vous ou une question. Que souhaitez-vous ?","next_mode":"FSM_FALLBACK","extracted":{{}},"confidence":0.9}}
- Mixed (pizza + rdv): User "je veux une pizza et un rendez-vous" → next_mode=FSM_BOOKING:
{{"response_text":"Je ne peux pas vous aider pour cela. En revanche, je peux vous aider à prendre rendez-vous. À quel nom, s'il vous plaît ?","next_mode":"FSM_BOOKING","extracted":{{}},"confidence":0.86}}

Output format: Return ONLY valid JSON. No markdown. No extra text. Single line.
Example (FAQ): {{"response_text": "Bonjour ! Je peux vous aider. """ + "{FAQ_HORAIRES}" + """ Souhaitez-vous prendre rendez-vous ?", "next_mode": "FSM_FAQ", "extracted": {{}}, "confidence": 0.86}}

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


# Raisons d'échec pour métriques canary (conv_p0_start reason)
FAIL_INVALID_JSON = "INVALID_JSON"
FAIL_VALIDATION_REJECTED = "VALIDATION_REJECTED"
FAIL_LLM_ERROR = "LLM_ERROR"


def complete_conversation(
    cabinet_data: CabinetData,
    state: str,
    user_text: str,
    history: List[Dict[str, str]],
    client: LLMConvClient,
) -> Tuple[Optional[ConvResult], Optional[str]]:
    """
    Appelle le LLM, parse le JSON, valide ConvResult.
    Retourne (ConvResult, None) si valide, (None, reason) sinon.
    reason in: INVALID_JSON, VALIDATION_REJECTED, LLM_ERROR.
    """
    system = _build_system_prompt(cabinet_data)
    user = _build_user_prompt(state, user_text, history)
    try:
        raw = client.complete(system, user)
    except Exception as e:
        logger.warning("llm_conversation complete error: %s", e)
        return (None, FAIL_LLM_ERROR)
    data = validate_llm_json(raw)
    if not data:
        logger.info("llm_conversation: invalid JSON, fallback FSM")
        return (None, FAIL_INVALID_JSON)
    if not validate_conv_result(data):
        logger.info("llm_conversation: validation failed (digits/forbidden/placeholder), fallback FSM")
        return (None, FAIL_VALIDATION_REJECTED)
    extracted = data.get("extracted") or {}
    if not isinstance(extracted, dict):
        extracted = {}
    return (
        ConvResult(
            response_text=data["response_text"],
            next_mode=data["next_mode"],
            extracted=extracted,
            confidence=float(data["confidence"]),
        ),
        None,
    )
