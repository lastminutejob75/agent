# backend/session_codec.py
"""
P0 Option B: Sérialisation Session <-> dict pour checkpoints.
Aucun secret dans state_json (token, credentials).
Fix #9: recovery sérialisé pour cohérence Postgres (partial_phone_digits, contact_mode).
"""
from __future__ import annotations

from typing import Any, Dict

from backend.session import Session, QualifData
from backend.recovery import migrate_recovery_from_legacy


def session_to_dict(session: Session) -> Dict[str, Any]:
    """
    Convertit une Session en dict pour stockage checkpoint.
    Inclut uniquement ce qui est nécessaire pour reprendre le flow.
    Exclut: messages (déjà dans call_messages), secrets.
    """
    q = session.qualif_data
    return {
        "state": session.state,
        "channel": getattr(session, "channel", "web"),
        "qualif_step": getattr(session, "qualif_step", "name"),
        "qualif_data": {
            "name": q.name,
            "motif": q.motif,
            "pref": q.pref,
            "contact": q.contact,
            "contact_type": q.contact_type,
        },
        "pending_slots_display": getattr(session, "pending_slots_display", None) or [],
        "pending_slot_choice": getattr(session, "pending_slot_choice", None),
        "pending_slots": _serialize_pending_slots(getattr(session, "pending_slots", None)),
        "awaiting_confirmation": getattr(session, "awaiting_confirmation", None),
        "rejected_slot_starts": getattr(session, "rejected_slot_starts", None) or [],
        "rejected_day_periods": getattr(session, "rejected_day_periods", None) or [],
        "slot_offer_index": getattr(session, "slot_offer_index", 0),
        "slot_proposal_sequential": getattr(session, "slot_proposal_sequential", False),
        "transfer_budget_remaining": getattr(session, "transfer_budget_remaining", 2),
        "time_constraint_type": getattr(session, "time_constraint_type", "") or "",
        "time_constraint_minute": getattr(session, "time_constraint_minute", -1),
        # Counters
        "no_match_turns": getattr(session, "no_match_turns", 0),
        "confirm_retry_count": getattr(session, "confirm_retry_count", 0),
        "contact_retry_count": getattr(session, "contact_retry_count", 0),
        "contact_fails": getattr(session, "contact_fails", 0),
        "slot_choice_fails": getattr(session, "slot_choice_fails", 0),
        "name_fails": getattr(session, "name_fails", 0),
        "phone_fails": getattr(session, "phone_fails", 0),
        "preference_fails": getattr(session, "preference_fails", 0),
        "contact_confirm_fails": getattr(session, "contact_confirm_fails", 0),
        "turn_count": getattr(session, "turn_count", 0),
        "intent_router_visits": getattr(session, "intent_router_visits", 0),
        "extracted_name": getattr(session, "extracted_name", False),
        "extracted_motif": getattr(session, "extracted_motif", False),
        "extracted_pref": getattr(session, "extracted_pref", False),
        "pending_cancel_slot": getattr(session, "pending_cancel_slot", None),
        # Fix #9: recovery (Postgres-friendly, inclut phone.partial / contact.mode)
        "recovery": getattr(session, "recovery", None) or {},
    }


def _deserialize_pending_slots(data: Any) -> list:
    """Désérialise pending_slots depuis le checkpoint. Fix 3: retourne format canonique (list of dicts)."""
    if not data or not isinstance(data, list):
        return []
    from backend import tools_booking
    return tools_booking.to_canonical_slots(data)


def _serialize_pending_slots(slots: Any) -> list:
    """Sérialise pending_slots en format canonique (list de dicts). Fix 3."""
    if not slots:
        return []
    from backend import tools_booking
    return tools_booking.to_canonical_slots(slots)


def session_from_dict(conv_id: str, d: Dict[str, Any]) -> Session:
    """
    Reconstruit une Session minimale depuis un checkpoint.
    Phase 2: utilisé par load_session_pg_first.
    """
    session = Session(conv_id=conv_id)
    if not d:
        return session
    session.state = d.get("state", "START")
    session.channel = d.get("channel", "web")
    session.qualif_step = d.get("qualif_step", "name")
    qd = d.get("qualif_data") or {}
    session.qualif_data = QualifData(
        name=qd.get("name"),
        motif=qd.get("motif"),
        pref=qd.get("pref"),
        contact=qd.get("contact"),
        contact_type=qd.get("contact_type"),
    )
    session.pending_slot_choice = d.get("pending_slot_choice")
    session.pending_slots = _deserialize_pending_slots(d.get("pending_slots") or d.get("pending_slots_display"))
    session.awaiting_confirmation = d.get("awaiting_confirmation")
    session.rejected_slot_starts = d.get("rejected_slot_starts") or []
    session.rejected_day_periods = d.get("rejected_day_periods") or []
    session.slot_offer_index = d.get("slot_offer_index", 0)
    session.slot_proposal_sequential = d.get("slot_proposal_sequential", False)
    session.transfer_budget_remaining = d.get("transfer_budget_remaining", 2)
    session.time_constraint_type = d.get("time_constraint_type", "") or ""
    session.time_constraint_minute = d.get("time_constraint_minute", -1)
    session.no_match_turns = d.get("no_match_turns", 0)
    session.confirm_retry_count = d.get("confirm_retry_count", 0)
    session.contact_retry_count = d.get("contact_retry_count", 0)
    session.contact_fails = d.get("contact_fails", 0)
    session.slot_choice_fails = d.get("slot_choice_fails", 0)
    session.name_fails = d.get("name_fails", 0)
    session.phone_fails = d.get("phone_fails", 0)
    session.preference_fails = d.get("preference_fails", 0)
    session.contact_confirm_fails = d.get("contact_confirm_fails", 0)
    session.turn_count = d.get("turn_count", 0)
    session.intent_router_visits = d.get("intent_router_visits", 0)
    session.extracted_name = d.get("extracted_name", False)
    session.extracted_motif = d.get("extracted_motif", False)
    session.extracted_pref = d.get("extracted_pref", False)
    session.pending_cancel_slot = d.get("pending_cancel_slot")
    # Fix #9: recovery (nouveaux checkpoints) ; sinon migration legacy ci-dessous
    session.recovery = d.get("recovery") or {}
    migrate_recovery_from_legacy(session)
    return session
