# backend/fsm2/events.py — Entrée utilisateur normalisée pour le dispatcher

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class InputKind(str, Enum):
    """Type d'entrée utilisateur (vocal / STT)."""
    TEXT = "TEXT"
    SILENCE = "SILENCE"
    NOISE = "NOISE"
    UNCLEAR = "UNCLEAR"


@dataclass(frozen=True)
class InputEvent:
    """Événement d'entrée passé au dispatcher FSM2."""
    kind: InputKind
    text: str  # Texte brut (pour les handlers / engine)
    text_normalized: str = ""  # Optionnel : lower, stripped (pour routage)
    strong_intent: Optional[str] = None  # Ex: BOOKING, CANCEL, TRANSFER, YES, NO, FAQ, etc.
