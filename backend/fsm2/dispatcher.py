# backend/fsm2/dispatcher.py — Router par état (phase 1 : QUALIF_NAME, WAIT_CONFIRM)

from __future__ import annotations
from typing import Any, List, TYPE_CHECKING

from backend.fsm2.states import States, is_fsm2_handled
from backend.fsm2.events import InputEvent, InputKind
from backend.fsm2.handlers.booking import handle_qualif_name, handle_wait_confirm

if TYPE_CHECKING:
    from backend.session import Session


def handle(session: "Session", event: InputEvent, engine: Any) -> List[Any]:
    """
    Dispatcher FSM2 : route vers le handler selon session.state.
    Phase 1 : seuls QUALIF_NAME et WAIT_CONFIRM sont gérés ici ; le reste reste en legacy.
    Retourne une liste d’Event (même type que engine.Event) pour compatibilité.
    """
    state = session.state
    if not is_fsm2_handled(state):
        return []  # signaler au caller de faire le legacy

    try:
        s = States(state)
    except ValueError:
        return []

    if s == States.QUALIF_NAME:
        return handle_qualif_name(session, event, engine)
    if s == States.WAIT_CONFIRM:
        return handle_wait_confirm(session, event, engine)

    return []


def states_covered() -> set:
    """Ensemble des états qui ont un handler (pour test_fsm2_states_covered)."""
    return {States.QUALIF_NAME, States.WAIT_CONFIRM}
