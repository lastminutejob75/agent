# backend/fsm2/handlers/booking.py — QUALIF_NAME et WAIT_CONFIRM (délégation engine)

from __future__ import annotations
from typing import TYPE_CHECKING, List, Any

if TYPE_CHECKING:
    from backend.session import Session
    from backend.fsm2.events import InputEvent


def handle_qualif_name(session: "Session", event: "InputEvent", engine: Any) -> List[Any]:
    """
    État QUALIF_NAME : qualification nom.
    Délègue à engine._handle_qualification (même logique, zéro régression).
    """
    return engine._handle_qualification(session, event.text)


def handle_wait_confirm(session: "Session", event: "InputEvent", engine: Any) -> List[Any]:
    """
    État WAIT_CONFIRM : choix créneau 1/2/3, early commit, barge-in.
    Délègue à engine._handle_booking_confirm.
    """
    return engine._handle_booking_confirm(session, event.text)
