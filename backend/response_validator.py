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
from typing import Any, Dict, Optional, Tuple

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
# If LLM uses these, it's trying to answer factual questions directly
FORBIDDEN_WORDS = frozenset([
    # Time-related
    "ouvert",
    "fermé",
    "horaire",
    "heures",
    # Price-related
    "prix",
    "tarif",
    "euro",
    "euros",
    "coûte",
    "coute",
    "rembourse",
    "remboursé",
    # Location-related
    "rue",
    "avenue",
    "boulevard",
    "adresse",
    "métro",
    "metro",
    "arrondissement",
    # Misc
    "24/7",
])

# Medical advice markers - NEVER allow
MEDICAL_MARKERS = frozenset([
    "dose",
    "mg",
    "posologie",
    "diagnostic",
    "symptôme",
    "symptome",
    "traitement",
    "médicament",
    "medicament",
    "ordonnance",
    "prescription",
])

# Regex to detect digits
DIGIT_PATTERN = re.compile(r"\d")

# Regex to detect currency symbols
CURRENCY_PATTERN = re.compile(r"[€$£¥]")


def validate_llm_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse and validate raw LLM output as strict JSON.

    Args:
        raw_text: Raw text from LLM (should be pure JSON)

    Returns:
        Parsed dict if valid JSON, None otherwise

    Rejects:
        - Markdown code blocks
        - Text before/after JSON
        - Invalid JSON syntax
        - Newlines/tabs in weird places
    """
    if not raw_text:
        return None

    text = raw_text.strip()

    # Reject if wrapped in markdown code blocks
    if text.startswith("```"):
        return None

    # Reject if doesn't start with {
    if not text.startswith("{"):
        return None

    # Reject if doesn't end with }
    if not text.endswith("}"):
        return None

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return data
    except json.JSONDecodeError:
        return None


def validate_conv_result(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate a parsed ConvResult dict from LLM.

    Args:
        data: Parsed JSON dict

    Returns:
        Tuple of (is_valid, rejection_reason)
        rejection_reason is empty string if valid
    """
    # 1. Check required keys
    if "response_text" not in data:
        return False, "missing_response_text"

    if "next_mode" not in data:
        return False, "missing_next_mode"

    if "confidence" not in data:
        return False, "missing_confidence"

    response_text = data.get("response_text", "")
    next_mode = data.get("next_mode", "")
    confidence = data.get("confidence", 0)

    # 2. Validate types
    if not isinstance(response_text, str):
        return False, "response_text_not_string"

    if not isinstance(next_mode, str):
        return False, "next_mode_not_string"

    if not isinstance(confidence, (int, float)):
        return False, "confidence_not_number"

    # 3. Validate next_mode
    if next_mode not in VALID_NEXT_MODES:
        return False, f"invalid_next_mode:{next_mode}"

    # 4. Validate confidence range
    if not (0.0 <= confidence <= 1.0):
        return False, "confidence_out_of_range"

    # 5. Validate confidence threshold
    if confidence < MIN_CONFIDENCE:
        return False, f"low_confidence:{confidence}"

    # 6. Validate response length
    if len(response_text) > MAX_RESPONSE_LENGTH:
        return False, f"response_too_long:{len(response_text)}"

    # 7. Check for digits (STRICT - no times, prices, numbers)
    if DIGIT_PATTERN.search(response_text):
        return False, "contains_digits"

    # 8. Check for currency symbols
    if CURRENCY_PATTERN.search(response_text):
        return False, "contains_currency"

    # 9. Validate placeholders - only allowed ones (check first, before stripping)
    found_placeholders = find_placeholders(response_text)
    for placeholder in found_placeholders:
        if placeholder not in ALLOWED_PLACEHOLDERS:
            return False, f"unknown_placeholder:{placeholder}"

    # 10. Strip placeholders before checking for forbidden words
    # This prevents false positives like {FAQ_HORAIRES} triggering "horaire"
    text_without_placeholders = response_text
    for placeholder in found_placeholders:
        text_without_placeholders = text_without_placeholders.replace(placeholder, "")
    text_lower = text_without_placeholders.lower()

    # 11. Check for forbidden words (in text without placeholders)
    for word in FORBIDDEN_WORDS:
        if word in text_lower:
            return False, f"forbidden_word:{word}"

    # 12. Check for medical advice markers
    for marker in MEDICAL_MARKERS:
        if marker in text_lower:
            return False, f"medical_marker:{marker}"

    # All checks passed
    return True, ""


def validate_extracted_entities(extracted: Optional[Dict[str, Any]]) -> bool:
    """
    Validate optional extracted entities from LLM.

    Args:
        extracted: Optional dict with name, pref, contact fields

    Returns:
        True if valid or None, False if malformed
    """
    if extracted is None:
        return True

    if not isinstance(extracted, dict):
        return False

    # Only allow known keys
    allowed_keys = {"name", "pref", "contact", "motif"}
    for key in extracted.keys():
        if key not in allowed_keys:
            return False

    # Validate each value is string or None
    for value in extracted.values():
        if value is not None and not isinstance(value, str):
            return False

    return True


def full_validate(raw_llm_output: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Full validation pipeline for LLM output.

    Args:
        raw_llm_output: Raw text from LLM

    Returns:
        Tuple of (is_valid, parsed_data, rejection_reason)
        - is_valid: True if output passes all checks
        - parsed_data: Parsed dict if valid, None otherwise
        - rejection_reason: Why rejected (empty if valid)
    """
    # Step 1: Parse JSON
    data = validate_llm_json(raw_llm_output)
    if data is None:
        return False, None, "invalid_json"

    # Step 2: Validate ConvResult structure and content
    is_valid, reason = validate_conv_result(data)
    if not is_valid:
        return False, None, reason

    # Step 3: Validate extracted entities if present
    extracted = data.get("extracted")
    if not validate_extracted_entities(extracted):
        return False, None, "invalid_extracted_entities"

    return True, data, ""
