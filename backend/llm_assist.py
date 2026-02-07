# backend/llm_assist.py
"""
LLM Assist classification (Option A minimale).
Zone grise START uniquement. JSON strict, FSM garde la main.
Aucune string user-facing générée par le LLM.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssistResult:
    """Résultat classification LLM strict."""
    intent: str  # BOOKING|FAQ|CANCEL|MODIFY|TRANSFER|ABANDON|UNCLEAR
    confidence: float  # 0.0-1.0
    faq_bucket: Optional[str]  # HORAIRES|ADRESSE|TARIFS|ACCES|CONTACT|AUTRE|None
    should_clarify: bool
    rationale: str  # Debug only, max 80 chars


ALLOWED_INTENTS = frozenset({
    "BOOKING", "FAQ", "CANCEL", "MODIFY", "TRANSFER", "ABANDON", "UNCLEAR",
})
ALLOWED_FAQ_BUCKETS = frozenset({
    "HORAIRES", "ADRESSE", "TARIFS", "ACCES", "CONTACT", "AUTRE",
})

# Config (default OFF)
LLM_ASSIST_ENABLED = os.getenv("LLM_ASSIST_ENABLED", "false").lower() == "true"
LLM_ASSIST_TIMEOUT_MS = int(os.getenv("LLM_ASSIST_TIMEOUT_MS", "900"))
LLM_ASSIST_MIN_CONFIDENCE = float(os.getenv("LLM_ASSIST_MIN_CONFIDENCE", "0.70"))
LLM_ASSIST_MAX_TEXT_LEN = int(os.getenv("LLM_ASSIST_MAX_TEXT_LEN", "120"))

SYSTEM_PROMPT = """You are a strict classification module for a voice receptionist.
Return ONLY valid JSON matching the schema. No extra text. No markdown. No code blocks.
You never invent facts. You never generate user-facing replies.
If uncertain, choose intent=UNCLEAR with low confidence."""

USER_PROMPT_TEMPLATE = """Classify the user's last utterance.

Context:
- channel: {channel}
- state: {state}
- user_utterance: "{text}"

Rules:
- If user asks to speak to a human/person => TRANSFER
- If user mentions cancel/annuler => CANCEL
- If user mentions déplacer/modifier/changer => MODIFY
- If user says goodbye/au revoir/stop => ABANDON
- If user is asking info => FAQ with faq_bucket:
  * HORAIRES: heures ouverture, quand ouvert
  * ADRESSE: où, localisation, comment venir
  * TARIFS: prix, coût, remboursement
  * ACCES: handicap, ascenseur, accessibilité
  * CONTACT: email, téléphone, joindre
  * AUTRE: autres questions factuelles
- If user wants appointment (even implicit) => BOOKING
- If user is unclear, hesitant, or too vague => UNCLEAR and should_clarify=true

IMPORTANT:
- If intent is FAQ, faq_bucket MUST be one of HORAIRES|ADRESSE|TARIFS|ACCES|CONTACT|AUTRE and MUST NOT be null.
- If intent is not FAQ, faq_bucket MUST be null.

Output JSON schema (fields required):
{{
  "intent": "BOOKING|FAQ|CANCEL|MODIFY|TRANSFER|ABANDON|UNCLEAR",
  "confidence": 0.0-1.0,
  "faq_bucket": "HORAIRES|ADRESSE|TARIFS|ACCES|CONTACT|AUTRE|null",
  "should_clarify": true/false,
  "rationale": "max 12 words explanation"
}}

Return ONLY JSON. No text before or after."""


class LLMClient(Protocol):
    """Interface injectable pour le client LLM."""

    def complete(self, system: str, user: str, timeout_ms: int) -> str:
        ...


class StubLLMClient:
    """Stub quand aucun client n'est configuré."""

    def complete(self, system: str, user: str, timeout_ms: int) -> str:
        raise NotImplementedError("LLM client not configured")


def _looks_like_pure_json(text: str) -> bool:
    """JSON strict : une seule ligne, { au début, } à la fin. Rejette markdown et pretty-print."""
    if not text:
        return False
    if "\n" in text or "\r" in text or "\t" in text:
        return False
    s = text.strip()
    if not s or len(s) < 2:
        return False
    if s[0] != "{" or s[-1] != "}":
        return False
    if "```" in s:
        return False
    return True


def _validate_assist_result(data: dict) -> bool:
    """Validation stricte : intent, confidence, faq_bucket si FAQ, should_clarify."""
    try:
        required = {"intent", "confidence", "faq_bucket", "should_clarify", "rationale"}
        if not required.issubset(data.keys()):
            return False

        intent = data["intent"]
        if intent not in ALLOWED_INTENTS:
            return False

        conf = float(data["confidence"])
        if not (0 <= conf <= 1):
            return False

        bucket = data["faq_bucket"]
        if intent == "FAQ":
            if bucket is None or (isinstance(bucket, str) and bucket.lower() == "null"):
                return False
            if bucket not in ALLOWED_FAQ_BUCKETS:
                return False
        else:
            if bucket is not None and (not isinstance(bucket, str) or bucket.lower() != "null"):
                return False

        if not isinstance(data["should_clarify"], bool):
            return False

        return True
    except Exception:
        return False


def llm_assist_classify(
    text: str,
    state: str,
    channel: str,
    client: Optional[LLMClient] = None,
    timeout_ms: Optional[int] = None,
) -> Optional[AssistResult]:
    """
    Classification zone grise START. Retourne None si désactivé, client absent,
    timeout, JSON invalide ou validation échouée.
    """
    if not LLM_ASSIST_ENABLED:
        return None
    if client is None:
        return None
    if len(text) > LLM_ASSIST_MAX_TEXT_LEN:
        return None

    timeout = timeout_ms or LLM_ASSIST_TIMEOUT_MS

    try:
        user_prompt = USER_PROMPT_TEMPLATE.format(
            channel=channel, state=state, text=text.replace('"', "'")[:LLM_ASSIST_MAX_TEXT_LEN]
        )
        raw = client.complete(system=SYSTEM_PROMPT, user=user_prompt, timeout_ms=timeout)

        if not _looks_like_pure_json(raw):
            logger.warning("llm_assist_reject_nonjson")
            return None

        data = json.loads(raw.strip())
        if not _validate_assist_result(data):
            logger.warning("llm_assist_validation_failed")
            return None

        bucket = data["faq_bucket"]
        if bucket in (None, "null") or (isinstance(bucket, str) and bucket.lower() == "null"):
            bucket = None
        return AssistResult(
            intent=data["intent"],
            confidence=float(data["confidence"]),
            faq_bucket=bucket,
            should_clarify=bool(data["should_clarify"]),
            rationale=str(data.get("rationale", ""))[:80],
        )
    except TimeoutError:
        logger.warning("llm_assist_timeout")
        return None
    except json.JSONDecodeError:
        logger.warning("llm_assist_json_error")
        return None
    except Exception as e:
        logger.error("llm_assist_error: %s", e)
        return None
