# backend/fsm2/handlers/cancel.py — Stub (non utilisé en phase 1)

from __future__ import annotations
from typing import TYPE_CHECKING, List, Any

if TYPE_CHECKING:
    from backend.session import Session
    from backend.fsm2.events import InputEvent


def handle_cancel(session: "Session", event: "InputEvent", engine: Any) -> List[Any]:
    """Stub : flow CANCEL reste en legacy engine pour l’instant."""
    return []
