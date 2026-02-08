# backend/response_validator.py
"""
Strict validation for LLM conversational responses.

SECURITY CRITICAL: This module ensures LLM output is safe before sending to users.
Rejects any response containing:
- Digits (times, prices, phone numbers)
- Currency symbols
- Forbidden words that indicate factual claims
- Medical advice markers
- Unknown placeholders
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from backend.placeholders import ALLOWED_PLACEHOLDERS, find_placeholders


# Valid next_mode values for routing
VALID_NEXT_MODES = frozenset({
    "FSM_BOOKING",
    "FSM_BOOKING_PRELUDE",  # phrase naturelle LLM puis FSM prend la main (QUALIF_NAME)
    "FSM_FAQ",
    "FSM_TRANSFER",
    "FSM_FALLBACK",
})

# Maximum response length (vocal constraint)
MAX_RESPONSE_LENGTH = 280

# NOTE: confidence threshold is enforced by caller (conversational_engine / llm_conversation),
# not here. This validator only checks shape/safety.

# Forbidden words: faits précis ou chiffrables (on autorise "horaires/adresse/tarifs" comme catégories)
FORBIDDEN_WORDS = frozenset([
    "euro", "euros", "coûte", "coute", "rembourse", "remboursé",
    "rue", "avenue", "boulevard", "métro", "metro", "arrondissement",
    "24/7",
])

# Medical advice markers - NEVER allow
MEDICAL_MARKERS = frozenset([
    "dose", "mg", "posologie", "diagnostic", "symptôme", "symptome",
    "traitement", "médicament", "medicament", "ordonnance", "prescription",
])

# Regex patterns
DIGIT_PATTERN = re.compile(r"\d")
CURRENCY_PATTERN = re.compile(r"[€$£¥]")


def validate_placeholder_policy(next_mode: str, response_text: str) -> bool:
    """
    P0: placeholders autorisés uniquement si next_mode == FSM_FAQ.
    FSM_FALLBACK = zéro placeholder (excuse + redirection, sans facts).
    FSM_FAQ = max 1 placeholder (vocal, charge cognitive).
    """
    placeholders = find_placeholders(response_text or "")

    if next_mode != "FSM_FAQ":
        return len(placeholders) == 0

    if len(placeholders) > 1:
        return False

    return True


def validate_llm_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse and validate raw LLM output as strict JSON.
    Returns parsed dict if valid JSON, None otherwise.
    STRICT: single-line JSON only, no markdown, no pretty-print.
    """
    if not raw_text:
        return None

    # STRICT: reject any multiline / pretty-printed / markdown / tabbed output.
    if ("\n" in raw_text) or ("\r" in raw_text) or ("\t" in raw_text):
        return None
    if "```" in raw_text:
        return None

    text = raw_text.strip()
    if not text.startswith("{") or not text.endswith("}"):
        return None

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def validate_conv_result(data: Dict[str, Any]) -> bool:
    """
    Validate a parsed ConvResult dict from LLM.
    Returns True if valid, False otherwise.
    """
    # Check required keys
    if "response_text" not in data:
        return False
    if "next_mode" not in data:
        return False
    if "confidence" not in data:
        return False

    response_text = data.get("response_text", "")
    next_mode = data.get("next_mode", "")
    confidence = data.get("confidence", 0)

    # Validate types
    if not isinstance(response_text, str):
        return False
    if not isinstance(next_mode, str):
        return False
    if not isinstance(confidence, (int, float)):
        return False

    # Validate next_mode
    if next_mode not in VALID_NEXT_MODES:
        return False

    # Validate confidence range
    if not (0.0 <= confidence <= 1.0):
        return False

    # Validate response length
    if len(response_text) > MAX_RESPONSE_LENGTH:
        return False

    # Anti double-braces: LLM must output {FAQ_XXX} not {{FAQ_XXX}} (replace would leave orphan braces)
    if "{{" in response_text or "}}" in response_text:
        return False

    # Check for digits (STRICT - no times, prices, numbers)
    if DIGIT_PATTERN.search(response_text):
        return False

    # Check for currency symbols
    if CURRENCY_PATTERN.search(response_text):
        return False

    if not validate_placeholder_policy(next_mode, response_text):
        return False

    found_placeholders = find_placeholders(response_text)
    for placeholder in found_placeholders:
        if placeholder not in ALLOWED_PLACEHOLDERS:
            return False

    # Strip placeholders before checking for forbidden words
    text_without_placeholders = response_text
    for placeholder in found_placeholders:
        text_without_placeholders = text_without_placeholders.replace(placeholder, "")
    text_lower = text_without_placeholders.lower()

    # Check for forbidden words (in text without placeholders)
    for word in FORBIDDEN_WORDS:
        if word in text_lower:
            return False

    # Check for medical advice markers
    for marker in MEDICAL_MARKERS:
        if marker in text_lower:
            return False

    return True


def validate_extracted_entities(extracted: Optional[Dict[str, Any]]) -> bool:
    """Validate optional extracted entities from LLM."""
    if extracted is None:
        return True
    if not isinstance(extracted, dict):
        return False

    allowed_keys = {"name", "pref", "contact", "motif"}
    for key in extracted.keys():
        if key not in allowed_keys:
            return False

    for value in extracted.values():
        if value is not None and not isinstance(value, str):
            return False

    return True
