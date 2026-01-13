# backend/tools_booking.py
from __future__ import annotations

from typing import List, Optional

from backend import prompts
from backend.db import list_free_slots, book_slot_atomic


def get_slots_for_display(limit: int = 3) -> List[prompts.SlotDisplay]:
    raw = list_free_slots(limit=limit)
    out: List[prompts.SlotDisplay] = []
    for i, r in enumerate(raw, start=1):
        label = f"{r['date']} - {r['time']}"
        out.append(prompts.SlotDisplay(idx=i, label=label, slot_id=int(r["id"])))
    return out


def store_pending_slots(session, slots: List[prompts.SlotDisplay]) -> None:
    session.pending_slot_ids = [s.slot_id for s in slots]
    session.pending_slot_labels = [s.label for s in slots]


def book_slot_from_session(session, choice_index_1based: int) -> bool:
    """
    Book le slot choisi.
    """
    idx = choice_index_1based - 1
    if idx < 0 or idx >= len(session.pending_slot_ids):
        return False

    slot_id = session.pending_slot_ids[idx]

    return book_slot_atomic(
        slot_id=slot_id,
        name=session.qualif_data.name or "",
        contact=session.qualif_data.contact or "",
        contact_type=session.qualif_data.contact_type or "",
        motif=session.qualif_data.motif or "",
    )


def get_label_for_choice(session, choice_index_1based: int) -> Optional[str]:
    idx = choice_index_1based - 1
    if idx < 0 or idx >= len(session.pending_slot_labels):
        return None
    return session.pending_slot_labels[idx]
