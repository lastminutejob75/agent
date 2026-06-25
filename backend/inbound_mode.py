"""Mode de réception des appels entrants (agent vocal vs ligne du praticien).

Quand ``inbound_mode == "practitioner"``, le praticien a « repris la main » :
les appels arrivant sur la ligne UWI sont transférés directement vers sa ligne
personnelle, sans que l'agent vocal ne décroche. Sinon (``"agent"``, défaut),
l'assistant vocal répond normalement.
"""
from __future__ import annotations

from typing import Any, Dict

from backend.vapi_live_transfer import normalize_transfer_destination_phone

INBOUND_MODE_AGENT = "agent"
INBOUND_MODE_PRACTITIONER = "practitioner"
_VALID_MODES = {INBOUND_MODE_AGENT, INBOUND_MODE_PRACTITIONER}


def normalize_inbound_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in _VALID_MODES else INBOUND_MODE_AGENT


def get_inbound_mode(params: Dict[str, Any]) -> str:
    return normalize_inbound_mode((params or {}).get("inbound_mode"))


def resolve_inbound_forward_number(params: Dict[str, Any]) -> str:
    """Numéro vers lequel renvoyer les appels quand le praticien reprend la main.

    Priorité : ligne praticien dédiée, puis numéro de transfert configuré, puis
    numéro du cabinet. Renvoie une chaîne E.164 valide ou "".
    """
    params = params or {}
    for key in ("transfer_practitioner_phone", "transfer_number", "transfer_assistant_phone", "phone_number"):
        normalized = normalize_transfer_destination_phone(params.get(key))
        if normalized:
            return normalized
    return ""
