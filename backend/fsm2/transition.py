# backend/fsm2/transition.py — Centralisation des transitions (P2.1 Étape 4)

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.session import Session


def transition(session: "Session", new_state: str) -> None:
    """
    Unique point de mise à jour de session.state dans FSM2.
    Interdit d'écrire session.state = "..." directement dans les handlers.
    """
    session.state = new_state
