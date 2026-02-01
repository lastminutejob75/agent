# tests/test_recovery_counters.py
"""
Tests des compteurs recovery par contexte (AJOUT_COMPTEURS_RECOVERY.md).
"""
import pytest
from backend.session import Session
from backend.engine import (
    increment_recovery_counter,
    should_escalate_recovery,
)


def test_increment_recovery_counter_slot_choice():
    """increment_recovery_counter('slot_choice') incrémente bien slot_choice_fails."""
    session = Session(conv_id="test_rec_slot")
    assert getattr(session, "slot_choice_fails", 0) == 0
    n = increment_recovery_counter(session, "slot_choice")
    assert n == 1
    assert session.slot_choice_fails == 1
    n = increment_recovery_counter(session, "slot_choice")
    assert n == 2
    assert session.slot_choice_fails == 2


def test_should_escalate_recovery_after_3_fails():
    """should_escalate_recovery retourne True après 3 échecs sur un contexte."""
    session = Session(conv_id="test_rec_esc")
    assert should_escalate_recovery(session, "name") is False
    increment_recovery_counter(session, "name")
    assert should_escalate_recovery(session, "name") is False
    increment_recovery_counter(session, "name")
    assert should_escalate_recovery(session, "name") is False
    increment_recovery_counter(session, "name")
    assert should_escalate_recovery(session, "name") is True


def test_counters_independent():
    """3 échecs sur 'name' ne déclenche pas escalade pour 'slot_choice'."""
    session = Session(conv_id="test_rec_indep")
    for _ in range(3):
        increment_recovery_counter(session, "name")
    assert should_escalate_recovery(session, "name") is True
    assert should_escalate_recovery(session, "slot_choice") is False
    assert session.name_fails == 3
    assert getattr(session, "slot_choice_fails", 0) == 0
