# backend/fsm2/states.py — Énumération des états (inventaire docs/FSM_STATES.md)

from __future__ import annotations
from enum import Enum


class States(str, Enum):
    """Tous les états utilisés dans engine (dispatch ou assignation)."""
    START = "START"
    FAQ_ANSWERED = "FAQ_ANSWERED"
    QUALIF_NAME = "QUALIF_NAME"
    QUALIF_MOTIF = "QUALIF_MOTIF"
    QUALIF_PREF = "QUALIF_PREF"
    QUALIF_CONTACT = "QUALIF_CONTACT"
    PREFERENCE_CONFIRM = "PREFERENCE_CONFIRM"
    AIDE_CONTACT = "AIDE_CONTACT"
    AIDE_MOTIF = "AIDE_MOTIF"
    WAIT_CONFIRM = "WAIT_CONFIRM"
    CONTACT_CONFIRM = "CONTACT_CONFIRM"
    CONFIRMED = "CONFIRMED"
    TRANSFERRED = "TRANSFERRED"
    INTENT_ROUTER = "INTENT_ROUTER"
    CLARIFY = "CLARIFY"
    CANCEL_NAME = "CANCEL_NAME"
    CANCEL_NO_RDV = "CANCEL_NO_RDV"
    CANCEL_CONFIRM = "CANCEL_CONFIRM"
    MODIFY_NAME = "MODIFY_NAME"
    MODIFY_NO_RDV = "MODIFY_NO_RDV"
    MODIFY_CONFIRM = "MODIFY_CONFIRM"
    ORDONNANCE_CHOICE = "ORDONNANCE_CHOICE"
    ORDONNANCE_MESSAGE = "ORDONNANCE_MESSAGE"
    ORDONNANCE_PHONE_CONFIRM = "ORDONNANCE_PHONE_CONFIRM"


# États gérés par FSM2 en phase 1 (dispatcher délègue au handler)
FSM2_HANDLED_STATES = {States.QUALIF_NAME, States.WAIT_CONFIRM}


def is_fsm2_handled(state: str) -> bool:
    """True si l'état est pris en charge par le dispatcher FSM2 (phase 1)."""
    try:
        return States(state) in FSM2_HANDLED_STATES
    except ValueError:
        return False
