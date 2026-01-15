# backend/fsm.py
"""
FSM stricte (transition whitelist) pour l'Agent IA d'accueil.
Ajout de l'état AIDE_MOTIF (1 seule aide, puis transfert).
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, Set


class ConvState(str, Enum):
    START = "START"
    FAQ_ANSWERED = "FAQ_ANSWERED"

    QUALIF_NAME = "QUALIF_NAME"
    QUALIF_MOTIF = "QUALIF_MOTIF"
    AIDE_MOTIF = "AIDE_MOTIF"  # <-- NEW
    QUALIF_PREF = "QUALIF_PREF"
    QUALIF_CONTACT = "QUALIF_CONTACT"

    WAIT_CONFIRM = "WAIT_CONFIRM"
    CONFIRMED = "CONFIRMED"

    TRANSFERRED = "TRANSFERRED"  # terminal


TERMINAL_STATES: Set[ConvState] = {ConvState.CONFIRMED, ConvState.TRANSFERRED}

VALID_TRANSITIONS: Dict[ConvState, Set[ConvState]] = {
    ConvState.START: {ConvState.FAQ_ANSWERED, ConvState.QUALIF_NAME, ConvState.TRANSFERRED},

    ConvState.FAQ_ANSWERED: {ConvState.START, ConvState.TRANSFERRED},  # optionnel (si tu veux continuer)

    ConvState.QUALIF_NAME: {ConvState.QUALIF_MOTIF, ConvState.TRANSFERRED},

    # Motif : soit validé => PREF, soit invalide 1ère fois => AIDE_MOTIF, sinon => TRANSFERRED
    ConvState.QUALIF_MOTIF: {ConvState.QUALIF_PREF, ConvState.AIDE_MOTIF, ConvState.TRANSFERRED},
    ConvState.AIDE_MOTIF: {ConvState.QUALIF_PREF, ConvState.TRANSFERRED},

    ConvState.QUALIF_PREF: {ConvState.QUALIF_CONTACT, ConvState.TRANSFERRED},
    ConvState.QUALIF_CONTACT: {ConvState.WAIT_CONFIRM, ConvState.TRANSFERRED},

    ConvState.WAIT_CONFIRM: {ConvState.CONFIRMED, ConvState.TRANSFERRED},
    ConvState.CONFIRMED: set(),
    ConvState.TRANSFERRED: set(),
}


def validate_transition(from_state: str, to_state: str) -> bool:
    """Retourne True si transition autorisée (whitelist)."""
    try:
        f = ConvState(from_state)
        t = ConvState(to_state)
    except ValueError:
        return False
    return t in VALID_TRANSITIONS.get(f, set())


def is_terminal(state: str) -> bool:
    try:
        s = ConvState(state)
    except ValueError:
        return False
    return s in TERMINAL_STATES

