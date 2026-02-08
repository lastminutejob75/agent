# backend/placeholders.py
"""
Placeholders — source de vérité pour le mode conversationnel.
Remplacement des tokens par les réponses officielles (FAQ store) après validation.

SECURITY: Le LLM ne voit/génère jamais de données factuelles.
          Il utilise uniquement des placeholders qui sont remplacés post-validation.
"""
from __future__ import annotations

import re
from typing import Set

from backend.cabinet_data import CabinetData

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

# Pattern pour détecter un placeholder {FAQ_XXX}
_PLACEHOLDER_PATTERN = re.compile(r"\{FAQ_[A-Z_]+\}")


def find_placeholders(text: str) -> Set[str]:
    """Find all placeholder tokens in the text."""
    return set(_PLACEHOLDER_PATTERN.findall(text))


def contains_only_allowed_placeholders(text: str) -> bool:
    """True si tous les placeholders présents dans text sont dans ALLOWED_PLACEHOLDERS."""
    found = _PLACEHOLDER_PATTERN.findall(text)
    return all(p in ALLOWED_PLACEHOLDERS for p in found)


def replace_placeholders(
    text: str,
    faq_store,  # FaqStore (tools_faq)
    cabinet_data: CabinetData,
) -> str:
    """
    Remplace chaque placeholder présent et autorisé par la réponse officielle FAQ.
    Placeholder inconnu → supprimé.
    """
    if not text:
        return text
    result = text
    for placeholder, faq_id in cabinet_data.faq_ids_map.items():
        if placeholder not in ALLOWED_PLACEHOLDERS:
            continue
        if placeholder not in result:
            continue
        # Utiliser get_answer_by_faq_id si disponible, sinon search
        if hasattr(faq_store, 'get_answer_by_faq_id'):
            answer_tuple = faq_store.get_answer_by_faq_id(faq_id)
            if answer_tuple:
                answer, _ = answer_tuple
                result = result.replace(placeholder, answer)
            else:
                result = result.replace(placeholder, "[information non disponible]")
        else:
            # Fallback: search avec le nom du FAQ
            faq_result = faq_store.search(faq_id.replace("FAQ_", "").lower())
            if faq_result.match and faq_result.answer:
                result = result.replace(placeholder, faq_result.answer)
            else:
                result = result.replace(placeholder, "")

    # Retirer tout placeholder restant (non mappé / inconnu)
    for match in _PLACEHOLDER_PATTERN.findall(result):
        result = result.replace(match, "")
    return result.strip()


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
