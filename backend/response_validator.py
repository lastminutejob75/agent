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
    "FSM_FAQ",
    "FSM_TRANSFER",
    "FSM_FALLBACK",
})

# Maximum response length (vocal constraint)
MAX_RESPONSE_LENGTH = 280

# Minimum confidence threshold
MIN_CONFIDENCE = 0.75

# Forbidden words that indicate factual claims
FORBIDDEN_WORDS = frozenset([
    "ouvert", "fermé", "horaire", "heures",
    "prix", "tarif", "euro", "euros", "coûte", "coute", "rembourse", "remboursé",
    "rue", "avenue", "boulevard", "adresse", "métro", "metro", "arrondissement",
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


def validate_llm_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse and validate raw LLM output as strict JSON.
    Returns parsed dict if valid JSON, None otherwise.
    """
    if not raw_text:
        return None

    text = raw_text.strip()

    # Reject markdown code blocks
    if text.startswith("```"):
        return None

    # Must start with { and end with }
    if not text.startswith("{") or not text.endswith("}"):
        return None

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return data
    except json.JSONDecodeError:
        return None


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

    # Check for digits (STRICT - no times, prices, numbers)
    if DIGIT_PATTERN.search(response_text):
        return False

    # Check for currency symbols
    if CURRENCY_PATTERN.search(response_text):
        return False

    # Validate placeholders - only allowed ones (check first, before stripping)
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
