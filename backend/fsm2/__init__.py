# backend/fsm2 — FSM explicite (P2.1, migration progressive)
# Usage : USE_FSM2=True pour router QUALIF_NAME / WAIT_CONFIRM via dispatcher.

from backend.fsm2.states import States, is_fsm2_handled
from backend.fsm2.events import InputEvent, InputKind
from backend.fsm2.dispatcher import handle as dispatch_handle

__all__ = ["States", "InputEvent", "InputKind", "dispatch_handle", "is_fsm2_handled"]
