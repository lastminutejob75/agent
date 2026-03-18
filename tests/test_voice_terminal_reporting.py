from typing import Optional

from backend.session import QualifData, Session
from backend.routes.voice import _resolve_terminal_reporting


def _make_session(state: str, outcome_event: Optional[str] = None) -> Session:
    session = Session(conv_id="call-1")
    session.state = state
    session.qualif_data = QualifData(name="Marie", motif="Controle")
    if outcome_event is not None:
        setattr(session, "last_outcome_event", outcome_event)
    return session


def test_terminal_reporting_uses_cancel_outcome_marker():
    session = _make_session("CONFIRMED", "cancel_done")

    reporting = _resolve_terminal_reporting(session)

    assert reporting == {"intent": "CANCEL", "outcome": "confirmed", "record_booking": False}


def test_terminal_reporting_uses_modify_outcome_marker():
    session = _make_session("CONFIRMED", "modify_done")

    reporting = _resolve_terminal_reporting(session)

    assert reporting == {"intent": "MODIFY", "outcome": "confirmed", "record_booking": False}


def test_terminal_reporting_falls_back_to_booking_for_regular_confirmation():
    session = _make_session("CONFIRMED")

    reporting = _resolve_terminal_reporting(session)

    assert reporting == {"intent": "BOOKING", "outcome": "confirmed", "record_booking": True}
