# backend/transfer_policy.py
"""
Fix #6: politique TRANSFER unifiée.
- Demande courte (mot seul / ≤14 car.) → CLARIFY (menu), pas de transfert direct.
- Demande explicite (phrase avec verbe/action) → TRANSFER direct.
Sans LLM, cohérent partout (START, FAQ, WAIT_CONFIRM, CLARIFY).
"""
from __future__ import annotations

import re
from typing import Literal

from backend.intent_parser import normalize_stt_text

# Mots normalisés (normalize_stt_text : accents → ascii, apostrophe → espace)
SHORT_KEYWORDS = {
    "humain",
    "transfert",
    "transfer",
    "conseiller",
    "operateur",
    "agent",
    "standard",
    "quelquun",
    "quelqu un",
    "personne",
    "serviceclient",
    "service client",
}

# Patterns explicites (verbes + action) — texte normalisé (lower, accents → ascii, espaces)
EXPLICIT_PATTERNS = [
    r"\b(parler|avoir|joindre|contacter)\b.*\b(quelqu un|une personne|un conseiller|un agent|le secretariat)\b",
    r"\b(mettez|mets|mettre)\b.*\b(en relation|en contact|au standard)\b",
    r"\b(passez|passer)\b.*\b(quelqu un|un conseiller|un agent|au standard)\b",
    r"\b(transferez|transfere|transferer)\b",
    r"\bje veux\b.*\b(un humain|parler|quelqu un|un conseiller|un agent)\b",
]


def classify_transfer_request(text: str) -> Literal["SHORT", "EXPLICIT", "NONE"]:
    """
    Classifie une demande de transfert humain.
    Returns: "SHORT" → clarify (menu), "EXPLICIT" → transfert direct, "NONE" → laisser le routeur décider.
    """
    raw = (text or "").strip()
    if not raw:
        return "NONE"
    t = normalize_stt_text(raw).lower().strip()
    t_compact = re.sub(r"[^a-z0-9\s]", " ", t)
    t_compact = re.sub(r"\s+", " ", t_compact).strip()

    # Explicite d'abord
    for pat in EXPLICIT_PATTERNS:
        if re.search(pat, t_compact):
            return "EXPLICIT"

    # Courte / mot seul
    if len(t_compact) <= 14:
        if t_compact in SHORT_KEYWORDS:
            return "SHORT"
        toks = t_compact.split()
        if len(toks) <= 2 and any(tok in SHORT_KEYWORDS for tok in toks):
            return "SHORT"

    return "NONE"
