# backend/placeholders.py
"""
Placeholder replacement system.

Placeholders are tokens like {FAQ_HORAIRES} that the LLM can use in responses.
These are replaced at runtime by verified FAQ answers.

SECURITY: The LLM NEVER sees or outputs actual business data (hours, prices, etc).
           It only outputs placeholder tokens which are replaced post-validation.
"""

from __future__ import annotations
import re
from typing import Set, Tuple

from backend.cabinet_data import CabinetData, DEFAULT_CABINET_DATA
from backend.tools_faq import FaqStore


# Allowed placeholders - ONLY these can appear in LLM output
ALLOWED_PLACEHOLDERS: Set[str] = {
    "{FAQ_HORAIRES}",
    "{FAQ_ADRESSE}",
    "{FAQ_TARIFS}",
    "{FAQ_ACCES}",
    "{FAQ_CONTACT}",
    "{FAQ_PAIEMENT}",
    "{FAQ_ANNULATION}",
    "{FAQ_DUREE}",
}

# Regex to find any placeholder pattern
PLACEHOLDER_PATTERN = re.compile(r"\{[A-Z_]+\}")


def find_placeholders(text: str) -> Set[str]:
    """
    Find all placeholder tokens in the text.

    Returns:
        Set of placeholder strings found (e.g., {"{FAQ_HORAIRES}", "{FAQ_TARIFS}"})
    """
    return set(PLACEHOLDER_PATTERN.findall(text))


def validate_placeholders(text: str) -> Tuple[bool, Set[str]]:
    """
    Validate that all placeholders in text are allowed.

    Returns:
        Tuple of (is_valid, set_of_invalid_placeholders)
    """
    found = find_placeholders(text)
    invalid = found - ALLOWED_PLACEHOLDERS
    return len(invalid) == 0, invalid


def replace_placeholders(
    text: str,
    faq_store: FaqStore,
    cabinet_data: CabinetData = DEFAULT_CABINET_DATA,
) -> Tuple[str, bool]:
    """
    Replace all placeholders with actual FAQ answers.

    Args:
        text: Text containing placeholders like {FAQ_HORAIRES}
        faq_store: FAQ store to retrieve answers
        cabinet_data: Business data with placeholder->FAQ_ID mapping

    Returns:
        Tuple of (replaced_text, all_replaced_successfully)

    If a placeholder cannot be resolved (no matching FAQ),
    it is removed and the function returns (text, False).
    """
    found = find_placeholders(text)
    if not found:
        return text, True

    result = text
    all_ok = True

    for placeholder in found:
        faq_id = cabinet_data.faq_ids_map.get(placeholder)
        if not faq_id:
            # Unknown placeholder - remove it
            result = result.replace(placeholder, "")
            all_ok = False
            continue

        # Find the FAQ answer by searching for a query that matches this FAQ ID
        # We search using the FAQ ID itself as a heuristic query
        faq_result = faq_store.search(faq_id.replace("FAQ_", "").lower())

        if faq_result.match and faq_result.answer:
            result = result.replace(placeholder, faq_result.answer)
        else:
            # FAQ not found - remove placeholder
            result = result.replace(placeholder, "")
            all_ok = False

    # Clean up double spaces that might result from removals
    result = re.sub(r"\s+", " ", result).strip()

    return result, all_ok


def get_placeholder_system_instructions() -> str:
    """
    Returns the system prompt instructions for placeholder usage.
    To be included in the LLM system prompt.
    """
    placeholders_list = ", ".join(sorted(ALLOWED_PLACEHOLDERS))

    return f"""
CRITICAL OUTPUT CONSTRAINTS - MUST FOLLOW EXACTLY:

1. NEVER output digits (0-9), currency symbols, or specific data in response_text
2. NEVER output specific times, prices, addresses, or factual business information
3. If factual information is needed, use ONLY these placeholders: {placeholders_list}
4. NEVER promise availability or give medical advice
5. If asked about availability: direct to booking via FSM
6. If asked medical question: refuse politely and propose booking or transfer

PLACEHOLDERS ARE THE ONLY WAY TO INCLUDE FACTUAL DATA.
The app will replace them with verified answers.
"""
