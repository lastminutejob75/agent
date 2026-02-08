# backend/placeholders.py
"""
Placeholders — source de vérité pour le mode conversationnel.
Remplacement des tokens par les réponses officielles (FAQ store) après validation.
"""
from __future__ import annotations

import re
from typing import Optional, Set

from backend.cabinet_data import CabinetData

ALLOWED_PLACEHOLDERS: Set[str] = {
    "{FAQ_HORAIRES}",
    "{FAQ_ADRESSE}",
    "{FAQ_TARIFS}",
    "{FAQ_ACCES}",
    "{FAQ_CONTACT}",
}

# Pattern pour détecter un placeholder {FAQ_XXX}
_PLACEHOLDER_PATTERN = re.compile(r"\{FAQ_[A-Z]+\}")


def replace_placeholders(
    text: str,
    faq_store,  # FaqStore (tools_faq)
    cabinet_data: CabinetData,
) -> str:
    """
    Remplace chaque placeholder présent et autorisé par la réponse officielle FAQ.
    Placeholder inconnu → supprimé (ou on pourrait reject en amont dans le validateur).
    """
    if not text:
        return text
    result = text
    for placeholder, faq_id in cabinet_data.faq_ids_map.items():
        if placeholder not in ALLOWED_PLACEHOLDERS:
            continue
        answer_tuple = faq_store.get_answer_by_faq_id(faq_id)
        if answer_tuple:
            answer, _ = answer_tuple
            result = result.replace(placeholder, answer)
        # Si faq_id inconnu dans le store, on laisse le placeholder (ou on remove)
        else:
            result = result.replace(placeholder, "[information non disponible]")
    # Retirer tout placeholder restant (non mappé / inconnu)
    for match in _PLACEHOLDER_PATTERN.findall(result):
        result = result.replace(match, "")
    return result.strip()


def contains_only_allowed_placeholders(text: str) -> bool:
    """True si tous les placeholders présents dans text sont dans ALLOWED_PLACEHOLDERS."""
    found = _PLACEHOLDER_PATTERN.findall(text)
    return all(p in ALLOWED_PLACEHOLDERS for p in found)
