# backend/cabinet_data.py
"""
Ground truth data for the cabinet (business).
Single source of truth for business information.

Used by conversational engine to inject verified data via placeholders.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class CabinetData:
    """
    Ground truth business data.

    FAQ_IDS_MAP maps placeholders to FAQ IDs.
    The actual answers are retrieved from FaqStore at runtime.
    """
    business_name: str = "Cabinet Dupont"
    business_type: str = "cabinet médical"

    # Mapping placeholder -> FAQ ID
    # The conversational engine uses this to know which placeholders are valid
    faq_ids_map: Dict[str, str] = field(default_factory=lambda: {
        "{FAQ_HORAIRES}": "FAQ_HORAIRES",
        "{FAQ_ADRESSE}": "FAQ_ADRESSE",
        "{FAQ_TARIFS}": "FAQ_TARIFS",
        "{FAQ_ACCES}": "FAQ_ACCES",
        "{FAQ_CONTACT}": "FAQ_CONTACT",
        "{FAQ_PAIEMENT}": "FAQ_PAIEMENT",
        "{FAQ_ANNULATION}": "FAQ_ANNULATION",
        "{FAQ_DUREE}": "FAQ_DUREE",
    })


# Default instance for use across the application
DEFAULT_CABINET_DATA = CabinetData()


def get_allowed_placeholders() -> set[str]:
    """Returns set of all allowed placeholder tokens."""
    return set(DEFAULT_CABINET_DATA.faq_ids_map.keys())


def get_faq_id_for_placeholder(placeholder: str) -> str | None:
    """Returns the FAQ ID for a given placeholder, or None if invalid."""
    return DEFAULT_CABINET_DATA.faq_ids_map.get(placeholder)
