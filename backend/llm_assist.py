# backend/llm_assist.py
"""
LLM Assist classification (Option A minimale).
Zone grise START uniquement. JSON strict, FSM garde la main.
Une seule exception user-facing : out_of_scope_response (OUT_OF_SCOPE), validée stricte (pas factuel).
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
    intent: str  # BOOKING|FAQ|CANCEL|MODIFY|TRANSFER|ABANDON|UNCLEAR|OUT_OF_SCOPE
    confidence: float  # 0.0-1.0
    faq_bucket: Optional[str]  # HORAIRES|ADRESSE|TARIFS|ACCES|CONTACT|AUTRE|None
    should_clarify: bool
    rationale: str  # Debug only, max 80 chars (never logged)
    out_of_scope_response: Optional[str] = None  # Uniquement si intent=OUT_OF_SCOPE, validé (pas factuel)


ALLOWED_INTENTS = frozenset({
    "BOOKING", "FAQ", "CANCEL", "MODIFY", "TRANSFER", "ABANDON", "UNCLEAR", "OUT_OF_SCOPE",
})
ALLOWED_FAQ_BUCKETS = frozenset({
    "HORAIRES", "ADRESSE", "TARIFS", "ACCES", "CONTACT", "AUTRE",
})

# OUT_OF_SCOPE : mots/chiffres interdits dans la réponse générée (0 risque factuel)
OUT_OF_SCOPE_SENSITIVE_SUBSTRINGS = (
    "ouvert", "fermé", "heure", "heures", "h", "€", "tarif", "prix", "rembourse",
    "adresse", "rue", "avenue",
)
OUT_OF_SCOPE_MAX_LEN = 180

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
- If the request is unrelated to the business services (pizza, car, shopping, jokes, random), return intent=OUT_OF_SCOPE, should_clarify=true, and provide out_of_scope_response (see below). OUT_OF_SCOPE never uses faq_bucket (must be null).
- If user is unclear, hesitant, or too vague (but not off-topic) => UNCLEAR and should_clarify=true.

OUT_OF_SCOPE response (when intent=OUT_OF_SCOPE only):
- out_of_scope_response: 1 phrase max, ton poli, mentionne "cabinet médical", redirige vers rendez-vous / horaires / adresse / parler à quelqu'un.
- NE DONNE AUCUNE info factuelle: pas de chiffres, pas d'horaires précis, pas de prix, pas d'adresse. Max 180 caractères.
- If intent is not OUT_OF_SCOPE, out_of_scope_response MUST be null.

IMPORTANT:
- If intent is FAQ, faq_bucket MUST be one of HORAIRES|ADRESSE|TARIFS|ACCES|CONTACT|AUTRE and MUST NOT be null.
- If intent is not FAQ (including OUT_OF_SCOPE), faq_bucket MUST be null.

Output JSON schema:
- Required: intent, confidence, faq_bucket, should_clarify, rationale
- If intent=OUT_OF_SCOPE: out_of_scope_response required (string, max 180 chars, no factual info)
- If intent!=OUT_OF_SCOPE: out_of_scope_response must be null or absent

{{
  "intent": "BOOKING|FAQ|CANCEL|MODIFY|TRANSFER|ABANDON|UNCLEAR|OUT_OF_SCOPE",
  "confidence": 0.0-1.0,
  "faq_bucket": "HORAIRES|ADRESSE|TARIFS|ACCES|CONTACT|AUTRE|null",
  "should_clarify": true/false,
  "out_of_scope_response": "string only when intent=OUT_OF_SCOPE, else null",
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


def get_default_llm_client() -> Optional[LLMClient]:
    """Retourne un client LLM (Anthropic) si ANTHROPIC_API_KEY et LLM_ASSIST_ENABLED sont définis."""
    if not LLM_ASSIST_ENABLED:
        return None
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        return AnthropicLLMClient(api_key=api_key)
    except Exception as e:
        logger.warning("llm_assist_anthropic_init_failed: %s", e)
        return None


class AnthropicLLMClient:
    """Client Anthropic (Claude) pour LLM Assist. Conforme au protocole LLMClient."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._api_key = api_key
        self._model = model

    def complete(self, system: str, user: str, timeout_ms: int) -> str:
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=self._api_key)
            timeout_sec = timeout_ms / 1000.0 if timeout_ms else 30.0
            msg = client.messages.create(
                model=self._model,
                max_tokens=256,
                system=system,
                messages=[{"role": "user", "content": user}],
                timeout=timeout_sec,
            )
            # Réponse: content est une liste de blocs (text, etc.)
            out = ""
            for block in getattr(msg, "content", []):
                if getattr(block, "type", None) == "text":
                    out += getattr(block, "text", "") or ""
            return out.strip() or ""
        except Exception as e:
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                raise TimeoutError from e
            raise


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


def _validate_out_of_scope_response(value: str) -> bool:
    """Valide out_of_scope_response : non vide, <= 180 chars, pas de chiffres ni mots factuels."""
    if not value or not isinstance(value, str):
        return False
    s = value.strip()
    if len(s) > OUT_OF_SCOPE_MAX_LEN:
        return False
    if any(c.isdigit() for c in s):
        return False
    if "€" in s:
        return False
    lower = s.lower()
    for sub in OUT_OF_SCOPE_SENSITIVE_SUBSTRINGS:
        if sub and sub in lower:
            return False
    return True


def _validate_assist_result(data: dict) -> bool:
    """Validation stricte : intent, confidence, faq_bucket, should_clarify, rationale ; out_of_scope_response si OUT_OF_SCOPE."""
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

        # out_of_scope_response : si OUT_OF_SCOPE doit être présent (string non vide) ; si autre intent doit être null/absent
        oos_resp = data.get("out_of_scope_response")
        if intent == "OUT_OF_SCOPE":
            if oos_resp is None or not isinstance(oos_resp, str) or not oos_resp.strip():
                return False
        else:
            if oos_resp is not None and (not isinstance(oos_resp, str) or oos_resp.strip().lower() not in ("", "null")):
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
        oos_resp = data.get("out_of_scope_response")
        if data["intent"] == "OUT_OF_SCOPE" and isinstance(oos_resp, str) and oos_resp.strip():
            raw = oos_resp.strip()[:OUT_OF_SCOPE_MAX_LEN]
            oos_final = raw if _validate_out_of_scope_response(raw) else None
        else:
            oos_final = None
        return AssistResult(
            intent=data["intent"],
            confidence=float(data["confidence"]),
            faq_bucket=bucket,
            should_clarify=bool(data["should_clarify"]),
            rationale=str(data.get("rationale", ""))[:80],
            out_of_scope_response=oos_final,
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
