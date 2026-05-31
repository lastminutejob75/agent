"""Classification motif demande de rappel (aligné page publique)."""
from __future__ import annotations

from typing import Tuple

from backend.intent_parser import normalize_stt_text

_VOCAL_REASON_PATTERNS = {
    "question_rdv": [
        "rendez vous",
        "rdv",
        "creneau",
        "deplacer",
        "annuler",
        "modifier",
        "reporter",
        "question sur un rendez",
    ],
    "admin": [
        "administratif",
        "admin",
        "horaire",
        "tarif",
        "acces",
        "adresse",
        "parking",
        "ouverture",
    ],
    "ordonnance": [
        "ordonnance",
        "document",
        "certificat",
        "renouvel",
        "prescription",
    ],
}

_SKIP_DETAIL = frozenset(
    {
        "autre",
        "autre chose",
        "rien",
        "pas de precision",
        "aucune",
        "ne sais pas",
        "je sais pas",
    }
)


def parse_vocal_callback_reason(user_text: str) -> Tuple[str, str]:
    """Retourne (reason_code, message_detail)."""
    raw = (user_text or "").strip()
    normalized = normalize_stt_text(raw)
    if normalized in _SKIP_DETAIL:
        return "other", ""
    for code, patterns in _VOCAL_REASON_PATTERNS.items():
        if any(pattern in normalized for pattern in patterns):
            detail = "" if normalized in _SKIP_DETAIL else raw[:500]
            return code, detail
    return "other", raw[:500] if raw else ""
