# backend/response_validator.py
"""
Validation stricte des réponses LLM conversationnel (JSON + contenu safe).
Reject si chiffres, €, infos factuelles, conseil médical → fallback FSM.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from backend.placeholders import ALLOWED_PLACEHOLDERS, contains_only_allowed_placeholders

# Réponse vocale : max 280 caractères (P0)
CONV_RESPONSE_MAX_LEN = 280

ALLOWED_NEXT_MODES = frozenset({"FSM_BOOKING", "FSM_FAQ", "FSM_TRANSFER", "FSM_FALLBACK"})

# Mots/interdits factuels (P0 strict)
FORBIDDEN_FACTUAL = [
    "ouvert", "fermé", "horaire", "prix", "tarif", "rue", "avenue",
    "rembourse", "€", "24/7", "euro", "euros",
]
# Marqueurs conseil médical (refus poli)
MEDICAL_ADVICE_MARKERS = ["dose", "mg", "posologie", "diagnostic", "symptôme", "symptome"]


def _looks_like_pure_json(text: str) -> bool:
    """JSON strict : une ligne, { ... }, pas de markdown."""
    if not text:
        return False
    if "\n" in text or "\r" in text or "\t" in text:
        return False
    s = text.strip()
    if len(s) < 2 or s[0] != "{" or s[-1] != "}":
        return False
    if "```" in s:
        return False
    return True


def validate_llm_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse JSON strict uniquement. Reject markdown, \\n/\\t.
    Returns parsed dict or None.
    """
    if not raw_text:
        return None
    if not _looks_like_pure_json(raw_text):
        return None
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        return None


def validate_conv_result(data: Dict[str, Any]) -> bool:
    """
    Validation ConvResult :
    - required keys: response_text, next_mode, confidence
    - confidence in [0, 1]
    - next_mode in allowlist
    - response_text length <= 280
    - response_text: only allowed placeholders (no unknown {FAQ_XXX})
    - reject digits, €, forbidden factual words, medical advice markers
    """
    try:
        if not isinstance(data, dict):
            return False
        required = {"response_text", "next_mode", "confidence"}
        if not required.issubset(data.keys()):
            return False

        conf = data["confidence"]
        try:
            conf_f = float(conf)
        except (TypeError, ValueError):
            return False
        if not (0 <= conf_f <= 1):
            return False

        if data["next_mode"] not in ALLOWED_NEXT_MODES:
            return False

        text = data.get("response_text")
        if not isinstance(text, str):
            return False
        if len(text) > CONV_RESPONSE_MAX_LEN:
            return False

        # Chiffres
        if any(c.isdigit() for c in text):
            return False
        if "€" in text or "$" in text:
            return False

        # Mots factuels interdits (hors placeholders autorisés)
        text_without_placeholders = text
        for p in ALLOWED_PLACEHOLDERS:
            text_without_placeholders = text_without_placeholders.replace(p, "")
        lower = text_without_placeholders.lower()
        for w in FORBIDDEN_FACTUAL:
            if w in lower:
                return False
        for w in MEDICAL_ADVICE_MARKERS:
            if w in lower:
                return False

        # Placeholders : uniquement autorisés
        if not contains_only_allowed_placeholders(text):
            return False

        return True
    except Exception:
        return False
