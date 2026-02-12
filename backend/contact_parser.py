# backend/contact_parser.py
"""
Extracteurs unifiés pour contact vocal (téléphone/email).
P0: dictée robuste, double/triple, canal, confidence.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from backend import guards


def normalize_stt_text(text: str) -> str:
    """Normalisation avant parsing (espaces, accents courants)."""
    if not text:
        return ""
    t = (text or "").strip().lower()
    t = re.sub(r"[^\w\s@.\-]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _parse_phone_with_double_triple(text: str) -> str:
    """
    Parse téléphone vocal avec support double/triple.
    "double six" → "66", "triple zéro" → "000".
    """
    t = text.lower().strip()
    # Nettoyer fillers
    for w in ["c'est", "le", "mon numéro", "numéro", "téléphone", "alors", "euh", "ben", "donc", "oui", "voilà"]:
        t = t.replace(w, " ")
    t = " ".join(t.split())

    result = []
    words = t.split()
    i = 0
    while i < len(words):
        w = words[i]
        # double/triple
        if w in ("double", "doubles"):
            if i + 1 < len(words):
                digit = guards.parse_vocal_phone(words[i + 1])
                if digit and len(digit) == 1:
                    result.append(digit + digit)
                    i += 2
                    continue
        if w in ("triple", "triples"):
            if i + 1 < len(words):
                digit = guards.parse_vocal_phone(words[i + 1])
                if digit and len(digit) == 1:
                    result.append(digit * 3)
                    i += 2
                    continue
        # Mot normal
        parsed = guards.parse_vocal_phone(w)
        if parsed:
            result.append(parsed)
        i += 1

    return "".join(c for c in "".join(result) if c.isdigit())


def extract_phone_digits_vocal(text: str) -> Tuple[str, float, bool]:
    """
    Extrait les chiffres du téléphone depuis une dictée vocale.
    Returns: (digits, confidence, is_partial)
    - digits: chaîne de chiffres (0-9)
    - confidence: 0.0-1.0 (1.0 si 10 digits valides, 0.8 si 9, 0.5 si 6-8, 0.3 si partiel)
    - is_partial: True si < 10 digits mais extraction plausible
    """
    if not text or not text.strip():
        return ("", 0.0, False)

    t = normalize_stt_text(text)
    # Essayer double/triple d'abord
    digits = _parse_phone_with_double_triple(text)
    if not digits:
        digits = guards.parse_vocal_phone(text)
    digits = "".join(c for c in digits if c.isdigit())

    if not digits:
        return ("", 0.0, False)

    n = len(digits)
    normalized = guards.normalize_phone_fr(digits)

    if normalized and len(normalized) == 10:
        return (normalized, 1.0, False)
    if n >= 9 and normalized:
        return (normalized, 0.95, False)
    if n >= 6:
        return (digits, 0.6, True)
    if n >= 4:
        return (digits, 0.5, True)
    return (digits, 0.3, True)


def extract_email_vocal(text: str) -> Tuple[Optional[str], float]:
    """
    Reconstruit un email depuis une dictée vocale.
    "prenom point nom arobase gmail point com" → "prenom.nom@gmail.com"
    Returns: (email, confidence) - (None, 0.0) si invalide.
    """
    if not text or not text.strip():
        return (None, 0.0)

    t = text.lower().strip()
    # Remplacer arobase/at/point
    t = t.replace(" arobase ", "@").replace(" at ", "@")
    t = t.replace(" point ", ".").replace(" dot ", ".")
    t = t.replace(" tiret ", "-").replace(" underscore ", "_")
    t = t.replace(" moins ", "-")

    # Supprimer espaces restants
    email = t.replace(" ", "")

    if not guards.validate_email(email):
        return (None, 0.0)
    if "@" not in email or "." not in email.split("@")[-1]:
        return (None, 0.0)

    # Confidence selon structure
    if "@" in email and len(email.split("@")) == 2:
        local, domain = email.split("@")
        if local and domain and "." in domain:
            return (email, 0.95)
    return (email, 0.7)


def detect_contact_channel(text: str) -> Optional[str]:
    """
    Détecte le canal souhaité (phone vs email) depuis la phrase.
    "envoyez-moi un mail" → "email"
    "appelez-moi" → "phone"
    Si digits >= 9 et pas @ → "phone"
    Si contient @ ou pattern email → "email"
    """
    if not text or not text.strip():
        return None
    t = text.strip().lower()

    # Intentions explicites
    if any(p in t for p in ["mail", "email", "courriel", "mel", "mèl", "mél", "envoyez", "écrivez"]):
        return "email"
    if any(p in t for p in ["téléphone", "telephone", "tel", "phone", "appelez", "rappelez", "numéro"]):
        return "phone"

    # Heuristique: digits >= 9 sans @ → phone
    digits = "".join(c for c in t if c.isdigit())
    if len(digits) >= 9 and "@" not in t:
        return "phone"
    if "@" in t or guards.looks_like_dictated_email(text):
        return "email"

    return None
