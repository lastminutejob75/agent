# backend/fsm2/handlers/router.py — Stub (non utilisé en phase 1)

from __future__ import annotations
from typing import TYPE_CHECKING, List, Any

if TYPE_CHECKING:
    from backend.session import Session
    from backend.fsm2.events import InputEvent


def handle_intent_router(session: "Session", event: "InputEvent", engine: Any) -> List[Any]:
    """Stub : INTENT_ROUTER reste en legacy engine pour l’instant."""
    return []
