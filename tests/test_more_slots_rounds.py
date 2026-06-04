# tests/test_more_slots_rounds.py
"""Voir d'autres créneaux : exclusion + demande de préférences après 2 tours."""

from datetime import datetime, timedelta

import pytest

from backend import prompts
from backend.engine import Engine
from backend.session import Session, SessionStore
from backend.tools_booking import (
    append_rejected_slots_from_pending,
    get_slots_for_display,
    normalize_slot_start_key,
    session_has_booking_preferences,
    to_canonical_slots,
)
from backend.tools_faq import default_faq_store


def _make_slot(label: str, start_iso: str, slot_id=1):
    from backend import prompts as p

    dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    return p.SlotDisplay(
        idx=1,
        label=label,
        slot_id=slot_id,
        start=start_iso,
        day="jeudi",
        hour=dt.hour,
        label_vocal=label,
        source="sqlite",
    )


def test_append_rejected_uses_normalized_keys():
    session = Session(conv_id="t-reject")
    session.pending_slots = to_canonical_slots(
        [_make_slot("jeudi 9h", "2026-06-04T09:00:00", 101)],
        source="sqlite",
    )
    append_rejected_slots_from_pending(session)
    assert "2026-06-04T09:00:00" in session.rejected_slot_starts
    assert "101" in session.rejected_slot_ids or "2026-06-04T09:00:00" in session.rejected_slot_ids


def test_session_has_booking_preferences():
    session = Session(conv_id="t-pref")
    assert session_has_booking_preferences(session) is False
    session.qualif_data.pref = "matin"
    assert session_has_booking_preferences(session) is True


def test_filter_excludes_rejected_slots():
    base = datetime(2026, 6, 4, 9, 0)
    pool = [
        _make_slot("a", (base).isoformat(), 1),
        _make_slot("b", (base + timedelta(hours=2)).isoformat(), 2),
        _make_slot("c", (base + timedelta(days=1)).isoformat(), 3),
    ]
    rejected = [normalize_slot_start_key(pool[0].start)]
    from backend.tools_booking import _filter_slots_exclude_exact

    out = _filter_slots_exclude_exact(pool, rejected, [])
    assert len(out) == 2
    assert normalize_slot_start_key(out[0].start) != rejected[0]


def test_more_slots_second_round_asks_preferences_web():
    engine = Engine(session_store=SessionStore(), faq_store=default_faq_store())
    session = Session(conv_id="t-more-2")
    session.channel = "web"
    session.state = "WAIT_CONFIRM"
    session.tenant_id = 1
    session.pending_slots = to_canonical_slots(
        [
            _make_slot("jeudi 9h", "2026-06-04T09:00:00", 1),
            _make_slot("jeudi 11h", "2026-06-04T11:00:00", 2),
            _make_slot("vendredi 9h", "2026-06-05T09:00:00", 3),
        ],
        source="sqlite",
    )
    session.more_slots_round_count = 1

    events = engine._reject_pending_and_repropose_slots(session)

    assert session.more_slots_round_count == 2
    assert events[0].text == prompts.MSG_WEB_MORE_SLOTS_ASK_PREF
    assert "préférences" in events[0].text.lower() or "preferences" in events[0].text.lower()
