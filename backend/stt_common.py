# backend/stt_common.py
"""
Classification text-only pour Custom LLM (chat/completions).
Pas de partial/confidence : whitelist tokens critiques + détection garbage/anglais.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal, Tuple

from backend.stt_utils import normalize_transcript, is_filler_only

# Tokens critiques : jamais UNCLEAR/NOISE.
# Inclut aussi les préférences horaires courtes ("matin", "après-midi")
# pour éviter qu'elles soient rejetées en overlap pendant QUALIF_PREF.
# Source unique de vérité pour webhook + chat/completions
CRITICAL_TOKENS = frozenset({
    "oui", "non", "ok", "okay", "daccord", "d'accord",
    "1", "2", "3", "un", "deux", "trois",
    "premier", "deuxième", "troisième", "premiere", "deuxieme", "troisieme",
    "ouais", "ouaip",
    "le premier", "le deuxième", "le troisième",
    "la première", "la deuxième", "la troisième",
    "confirme", "je confirme", "oui je confirme",  # Réponse à "Vous confirmez ?"
    "matin", "matinee", "matinée",
    "apres midi", "après midi", "apres-midi", "après-midi", "aprem", "aprèm",
    "soir", "soiree", "soirée",
})

# Mots anglais fréquents (STT en anglais = garbage pour nous)
ENGLISH_STOPWORDS = frozenset({
    "the", "you", "would", "have", "won't", "wont", "even", "all", "this",
    "that", "with", "for", "are", "was", "were", "been", "being", "from",
    "they", "your", "what", "when", "where", "which", "who", "how", "why",
    "believe", "these", "those", "them", "their", "there", "then", "than",
    "will", "can", "could", "should", "might", "must", "may", "about",
    "into", "just", "more", "some", "only", "other", "over", "such",
    "very", "also", "back", "after", "before", "between", "through",
})


def _normalize_critical_text(text: str) -> str:
    """Normalise un token court pour matching critique (accents + tirets)."""
    t = (text or "").strip().lower()
    t = t.replace("-", " ")
    t = "".join(
        c for c in unicodedata.normalize("NFD", t)
        if unicodedata.category(c) != "Mn"
    )
    t = re.sub(r"['’]", "", t)
    t = "".join(ch for ch in t if ch.isalnum() or ch.isspace()).strip()
    return " ".join(t.split())


def is_critical_token(text: str) -> bool:
    """
    Vrai si le texte est un token critique (jamais classé UNCLEAR/NOISE).
    Utilisé par webhook (_classify_stt_input) et chat/completions (overlap).
    """
    if not text:
        return False
    t = _normalize_critical_text(text)
    if not t:
        return False
    if t in CRITICAL_TOKENS or t in CRITICAL_OVERLAP:
        return True
    parts = t.split()
    if len(parts) == 2:
        if parts[0] in {"oui", "ok", "non"} and parts[1] in {"1", "2", "3", "un", "deux", "trois"}:
            return True
    return False


def looks_like_garbage_or_wrong_language(text: str) -> bool:
    """
    Heuristique : texte majoritairement anglais/charabia => UNCLEAR.
    Pas de lib externe : mots anglais fréquents ou ratio tokens non-français.
    """
    if not text or not text.strip():
        return False
    t = text.strip().lower()
    tokens = re.findall(r"[a-zàâäéèêëïîôùûüç]+", t)
    if not tokens:
        # Que de la ponctuation / chiffres bizarres
        if len(text.strip()) > 3:
            return True
        return False
    # Comptage mots anglais
    english_count = sum(1 for w in tokens if w in ENGLISH_STOPWORDS)
    # Si >= 2 mots anglais ou ratio > 1/3 => garbage
    if english_count >= 2:
        return True
    if len(tokens) >= 3 and english_count / len(tokens) > 0.33:
        return True
    # Phrase typiquement anglaise (would have, won't even, etc.)
    combined = " ".join(tokens)
    if any(phrase in combined for phrase in ["would have", "won t", "wont", "you would", "believe you"]):
        return True
    return False


def estimate_tts_duration(text: str) -> float:
    """
    Estime la durée TTS en secondes.
    ~13 car/s en français ; min 0.8s, max 4.0s.
    """
    if not text or not text.strip():
        return 0.0
    chars_per_second = 13.0
    duration = len(text) / chars_per_second
    return max(0.8, min(4.0, duration))


# Mots qui passent même pendant overlap (semi-sourd / barge-in pendant lecture créneaux)
CRITICAL_OVERLAP = frozenset({
    "oui", "non", "ok", "okay",
    "1", "2", "3", "un", "deux", "trois",
    "premier", "deuxième", "troisième", "deuxieme", "troisieme",
    "le 1", "le 2", "le 3", "le premier", "le deuxième", "le troisième", "le dernier",
    "stop", "arrête", "arrêtez",
    "humain", "personne", "quelqu'un", "quelquun",
    "annuler", "annulation",
    "transfert", "transférer", "transfere",
    "confirme", "je confirme", "oui je confirme",  # Réponse à "Vous confirmez ?" pendant overlap
    "matin", "matinee", "matinée",
    "apres midi", "après midi", "apres-midi", "après-midi", "aprem", "aprèm",
    "soir", "soiree", "soirée",
})


def is_critical_overlap(text: str) -> bool:
    """True si le texte est un mot critique qui doit être traité même pendant que l'agent parle."""
    if not text:
        return False
    normalized = _normalize_critical_text(normalize_transcript(text or ""))
    if not normalized:
        return False
    return normalized in CRITICAL_OVERLAP


def looks_like_short_crosstalk(text: str) -> bool:
    """
    Court + garbage => probable crosstalk (user parle pendant TTS).
    Ne jamais considérer les tokens critiques comme crosstalk (ils sont déjà TEXT).
    """
    if not text or not text.strip():
        return False
    raw = (text or "").strip()
    if len(raw) >= 20:
        return False
    if is_critical_token(normalize_transcript(raw)):
        return False
    return looks_like_garbage_or_wrong_language(raw) or is_filler_only(raw)


def classify_text_only(text: str) -> Tuple[Literal["SILENCE", "UNCLEAR", "TEXT"], str]:
    """
    Classification text-only (sans partial/confidence).
    Returns: (kind, normalized) où kind in {"SILENCE", "UNCLEAR", "TEXT"}
    """
    raw = (text or "").strip()
    normalized = normalize_transcript(text or "")

    # Vide => SILENCE
    if not raw:
        return "SILENCE", ""

    # Tokens critiques => toujours TEXT
    if is_critical_token(normalized):
        return "TEXT", normalized

    # Filler seul (ex: "euh", "hum") => UNCLEAR (même si normalisé à "")
    if is_filler_only(raw) or is_filler_only(normalized):
        return "UNCLEAR", normalized

    # Normalisé vide mais raw non vide => filler-only déjà traité ; sinon SILENCE
    if not normalized or not normalized.strip():
        return "SILENCE", ""

    # Garbage / mauvaise langue => UNCLEAR
    if looks_like_garbage_or_wrong_language(raw):
        return "UNCLEAR", normalized

    return "TEXT", normalized
