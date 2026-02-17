# backend/utils/phone.py
"""
Normalisation E.164 pour routing multi-tenant (vocal, WhatsApp, SMS).
"""
from __future__ import annotations

import re


def normalize_e164(number: str) -> str:
    """
    Normalise un numéro en format E.164 strict (+<country><number>).
    Gère les préfixes WhatsApp/Twilio (whatsapp:, tel:, sip:).
    Raise ValueError si format invalide.
    """
    if not number or not isinstance(number, str):
        raise ValueError("Invalid E.164 number: empty or not a string")
    cleaned = number.strip()
    for prefix in ("whatsapp:", "tel:", "sip:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    cleaned = re.sub(r"[\s\-\(\)\._]", "", cleaned)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if not cleaned.startswith("+"):
        raise ValueError(f"Invalid E.164 number: {number!r} (must start with +)")
    if not re.match(r"^\+\d{8,15}$", cleaned):
        raise ValueError(f"Invalid E.164 number: {number!r}")
    return cleaned
