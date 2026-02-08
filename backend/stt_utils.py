# backend/stt_utils.py
"""
Utilitaires STT pour nova-2-phonecall.
- Normalisation des transcripts (fillers, ponctuation seule)
- Classification bruit / silence / texte (utilisée par le webhook Vapi).
"""

from __future__ import annotations

import re
from typing import Literal

# Liste restrictive : ne PAS inclure "ok", "oui", "non" (intents critiques / YES)
FILLER_WORDS = frozenset({
    "euh", "heu", "hum", "hmm", "mmh", "mmm",
    "ben", "bah", "donc", "alors", "voilà", "voila",
    "...", "..", ".", ",", "?", "!",
})

# Alias pour compat
FILLERS = FILLER_WORDS


def normalize_transcript(text: str) -> str:
    """
    Nettoie le transcript : trim + suppression fillers début/fin uniquement.
    Garde le contenu central intact. "ok" et "oui" ne sont jamais supprimés.
    """
    if not text or not isinstance(text, str):
        return ""
    t = text.strip()
    if not t:
        return ""
    t = re.sub(r"\s+", " ", t)
    words = t.split()
    # Retirer fillers au DÉBUT seulement
    while words and words[0].lower().strip(".,;:?!") in FILLER_WORDS:
        words = words[1:]
    # Retirer fillers à la FIN seulement
    while words and words[-1].lower().strip(".,;:?!") in FILLER_WORDS:
        words = words[:-1]
    t = " ".join(words).strip()
    t = t.strip(".,;:?!…")
    return t.strip()


def is_filler_only(text: str) -> bool:
    """True si le texte ne contient que des fillers / vide (pas "ok" ni "oui")."""
    n = normalize_transcript(text)
    return len(n) < 2 or (n.lower() in FILLER_WORDS)
