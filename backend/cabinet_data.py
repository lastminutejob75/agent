# backend/cabinet_data.py
"""
Données cabinet (ground truth) — noms de placeholders autorisés pour le mode conversationnel.
Les réponses brutes restent dans FAQ store / prompts.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

FAQ_IDS_MAP_DEFAULT: Dict[str, str] = {
    "{FAQ_HORAIRES}": "FAQ_HORAIRES",
    "{FAQ_ADRESSE}": "FAQ_ADRESSE",
    "{FAQ_TARIFS}": "FAQ_TARIFS",
    "{FAQ_ACCES}": "FAQ_ACCES",
    "{FAQ_CONTACT}": "FAQ_CONTACT",
}


@dataclass(frozen=True)
class CabinetData:
    business_name: str
    business_type: str  # "cabinet medical"
    faq_ids_map: Dict[str, str]  # placeholder -> faq_id

    @classmethod
    def default(cls, business_name: str = "Cabinet Dupont") -> "CabinetData":
        return cls(
            business_name=business_name,
            business_type="cabinet medical",
            faq_ids_map=dict(FAQ_IDS_MAP_DEFAULT),
        )
